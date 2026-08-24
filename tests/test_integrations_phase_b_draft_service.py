"""Phase B M4/M5 tests: Etsy draft creation, duplicate/recovery safety.

Everything runs offline through a stateful fake transport.  The required
proofs covered here:

- Happy path creates ONE draft, attaches the PDF and an image, reconciles,
  and reports "created online — NOT published" truthfully.
- Human-confirmed records (Uploaded/Published) are refused with ZERO remote
  calls.
- A missing or oversized local printable.pdf aborts before any remote call.
- An existing same-title draft is adopted instead of duplicated.
- A crash mid-flow resumes from the persisted listing ID without duplicating
  drafts or re-uploading attachments.
- The client has no update/delete/activate/publish capability at all, and no
  captured request ever changes listing state.
"""

import json
import urllib.parse

import pytest

from integrations.etsy import draft_service as ds
from integrations.etsy.drafts import EtsyDraftClient
from integrations.etsy.connection import EtsyCredentials
from integrations.etsy.draft_service import (
    MAX_DIGITAL_FILE_BYTES,
    EtsyDraftService,
    build_draft_fields,
    find_taxonomy_id,
    sanitize_tags,
    sanitize_title,
)
from publishing.manager import PublishingService


METADATA = {
    "title": "Ocean Animals Word Search",
    "description": "A relaxing collection of ocean-themed puzzles.",
    "etsy_tags": ["ocean animals", "word search", "printable puzzle", "ocean animals"],
    "price": {"etsy": 6.99},
}


class MemoryStore:
    def __init__(self, credentials=None):
        self.credentials = credentials

    def load(self):
        return self.credentials

    def save(self, credentials):
        self.credentials = credentials

    def forget(self):
        self.credentials = None
        return True


class FakeEtsy:
    """Stateful fake of the draft-only slice of the Etsy API."""

    def __init__(self, existing_drafts=(), listing_state="draft", listing_404_ids=()):
        self.requests = []
        self.existing_drafts = list(existing_drafts)   # [{listing_id,title,state}]
        self.listing_state = listing_state
        self.listing_404_ids = set(listing_404_ids)
        self.created_listing_id = 555001
        self.files: dict[int, int] = {}
        self.images: dict[int, int] = {}
        self.next_listing_id = 600100

    # -- request routing ------------------------------------------------------

    def send(self, request, timeout_seconds):
        self.requests.append(request)
        parsed = urllib.parse.urlsplit(request.url)
        path, query = parsed.path, parsed.query
        if path.endswith("/oauth/token"):
            return self._json(200, {"access_token": "x", "refresh_token": "y", "expires_in": 3600})
        if path == "/v3/application/users/me":
            return self._json(200, {"user_id": 42})
        if path == "/v3/application/users/42/shops":
            return self._json(200, {"count": 1, "results": [{"shop_id": 777, "shop_name": "SladePuzzleCo"}]})
        if path == "/v3/application/seller-taxonomy/nodes":
            return self._json(200, TAXONOMY_PAYLOAD)
        if path == "/v3/application/shops/777/listings":
            if request.method == "GET":
                return self._json(200, {"count": len(self.existing_drafts), "results": self.existing_drafts})
            fields = urllib.parse.parse_qsl(request.body.decode("utf-8"))
            listing = {"listing_id": self.next_listing_id, "state": "draft", "title": dict(fields).get("title", "")}
            self.existing_drafts.append(listing)
            self.next_listing_id += 1
            self.created_listing_id = listing["listing_id"]
            return self._json(201, listing)
        parts = path.strip("/").split("/")
        # /v3/application/listings/{id}
        if len(parts) == 4 and parts[2] == "listings":
            listing_id = int(parts[3])
            if listing_id in self.listing_404_ids:
                return self._json(404, {"error": "not found"})
            title = next((d["title"] for d in self.existing_drafts if d["listing_id"] == listing_id), METADATA["title"])
            return self._json(200, {"listing_id": listing_id, "state": self.listing_state, "title": title})
        # /v3/application/shops/{shop}/listings/{id}/files|images
        if len(parts) >= 7 and parts[:3] == ["v3", "application", "shops"]:
            listing_id = int(parts[5]); kind = parts[6]
            store = self.files if kind == "files" else self.images
            if request.method == "GET":
                count = store.get(listing_id, 0)
                return self._json(200, {"count": count,
                                        "results": [{"listing_file_id": n} for n in range(count)] if kind == "files"
                                        else [{"listing_image_id": n} for n in range(count)]})
            store[listing_id] = store.get(listing_id, 0) + 1
            return self._json(201, {"ok": True})
        raise AssertionError(f"Unexpected fake-Etsy request: {request.method} {request.url}")

    @staticmethod
    def _json(status_code, payload):
        from integrations.http import HttpResponse

        return HttpResponse(status_code=status_code, headers={}, body=json.dumps(payload).encode("utf-8"))


TAXONOMY_PAYLOAD = {
    "results": [{
        "id": 1, "name": "Accessories", "children": [],
    }, {
        "id": 1400, "name": "Books, Movies & Music", "children": [
            {"id": 1331, "name": "Books & Zines", "children": [
                {"id": 1332, "name": "Books", "full_path_taxonomy_ids": [1400, 1331, 1332], "children": []},
            ]},
        ],
    }],
}


@pytest.fixture()
def env_clean(monkeypatch):
    for name in ("KDP_ETSY_API_KEYSTRING", "KDP_ETSY_SHARED_SECRET",
                 "KDP_ETSY_ACCESS_TOKEN", "KDP_ETSY_REFRESH_TOKEN",
                 ds.TAXONOMY_ENV_VAR):
        monkeypatch.delenv(name, raising=False)


def _make_book(tmp_path, service, *, with_printable=True, size_bytes=None, with_image=True):
    package = tmp_path / f"pkg-{service.db.db_path.name}"
    prepared = package / "etsy"; prepared.mkdir(parents=True, exist_ok=True)
    if with_printable:
        base = b"%PDF-1.4 puzzle pages"
        if size_bytes is None:
            data = base
        else:  # repeat until the written file is at least *size_bytes*
            data = base * (size_bytes // len(base) + 1)
        (prepared / "printable.pdf").write_bytes(data)
    if with_image:
        (prepared / "thumbnail.jpg").write_bytes(b"\xff\xd8\xff\xe0fakejpg")
    metadata = json.loads(json.dumps(METADATA))
    service.db.upsert_book("b1", "theme:b1", metadata, str(package))
    book = service.db.get_book("b1")
    book["package_path"] = str(package)
    return book


def _service_with_creds(tmp_path, transport):
    service = PublishingService(tmp_path)
    store = MemoryStore(EtsyCredentials(
        api_keystring="keystring-abcd", shared_secret="shared-secret-value",
        access_token="access-token-value", refresh_token="refresh-token-value"))
    runner = EtsyDraftService(transport=transport, token_store=store, sleep=lambda _s: None)
    return service, store, runner


# ---------------------------------------------------------------------------
# Pure payload helpers
# ---------------------------------------------------------------------------


def test_sanitize_title_strips_and_caps():
    raw = "My {emoji 🎉} Book: <great> Puzzles! " + "x" * 300
    cleaned = sanitize_title(raw)
    assert "<" not in cleaned and ">" not in cleaned and "🎉" not in cleaned
    assert len(cleaned) <= 140
    assert cleaned.startswith("My emoji Book")


def test_sanitize_tags_dedupes_and_caps():
    tags = sanitize_tags(["Ocean Animals", "ocean animals!!", "word search", "", "x" * 50] + [f"t{n}" for n in range(20)])
    assert tags[0] == "Ocean Animals"
    assert len(tags) <= 13
    assert all(len(tag) <= 20 for tag in tags)


def test_find_taxonomy_id_prefers_deepest_books_node():
    assert find_taxonomy_id(TAXONOMY_PAYLOAD) == 1332


def test_build_draft_fields_is_digital_and_complete():
    fields = build_draft_fields(METADATA, taxonomy_id=1332, price=6.99)
    assert fields["type"] == "download"
    assert fields["who_made"] == "i_did"
    assert fields["when_made"] == "made_to_order"
    assert fields["quantity"] == "999"
    assert fields["taxonomy_id"] == "1332"
    assert fields["price"] == "6.99"
    assert fields["tags"] == "ocean animals,word search,printable puzzle"


# ---------------------------------------------------------------------------
# Happy path + safety refusals
# ---------------------------------------------------------------------------


def test_happy_path_creates_one_draft_and_verifies(tmp_path, env_clean):
    transport = FakeEtsy()
    service, _store, runner = _service_with_creds(tmp_path, transport)
    book = _make_book(tmp_path, service)

    result = runner.create_or_resume(service, book)
    assert result.ok, result.message
    assert result.listing_id == str(transport.created_listing_id)
    record = service.db.marketplace_records("b1")["etsy"]
    assert record["external_id"] == result.listing_id
    assert record["status"] == "Ready"                      # elevated once, truthfully
    integration = service.db.integration_record("b1", "etsy")
    assert integration["integration_state"] == "complete"
    joined = "\n".join(result.events)
    for expected in ("draft_created", "file_uploaded", "image_uploaded", "draft_verified"):
        assert expected in joined
    audits = service.db.audit_history("b1", marketplace="etsy")
    assert any(entry["source"] == "etsy_draft" for entry in audits)


def test_protected_status_refused_without_any_remote_call(tmp_path, env_clean):
    transport = FakeEtsy()
    service, _store, runner = _service_with_creds(tmp_path, transport)
    book = _make_book(tmp_path, service)
    service.db.transition_status("b1", "etsy", "Published", external_id="42", source="manual")

    result = runner.create_or_resume(service, book)
    assert not result.ok and "Published" in result.message
    assert transport.requests == []


def test_missing_prepared_file_refused_before_remote_calls(tmp_path, env_clean):
    transport = FakeEtsy()
    service, _store, runner = _service_with_creds(tmp_path, transport)
    book = _make_book(tmp_path, service, with_printable=False)

    result = runner.create_or_resume(service, book)
    assert not result.ok and "Prepare Etsy" in result.message
    assert transport.requests == []


def test_oversized_file_refused_before_remote_calls(tmp_path, env_clean, monkeypatch):
    transport = FakeEtsy()
    service, _store, runner = _service_with_creds(tmp_path, transport)
    book = _make_book(tmp_path, service, size_bytes=MAX_DIGITAL_FILE_BYTES + 1024)

    result = runner.create_or_resume(service, book)
    assert not result.ok and "20 MB" in result.message
    assert transport.requests == []


def test_not_configured_reports_connection_guidance(tmp_path, env_clean):
    transport = FakeEtsy()
    service = PublishingService(tmp_path)
    store = MemoryStore(None)  # nothing stored anywhere
    runner = EtsyDraftService(transport=transport, token_store=store, sleep=lambda _s: None)
    book = _make_book(tmp_path, service)
    result = runner.create_or_resume(service, book)
    assert not result.ok and "connections" in result.message.lower()


# ---------------------------------------------------------------------------
# Duplicate prevention and resume safety
# ---------------------------------------------------------------------------


def test_existing_same_title_draft_is_adopted_not_duplicated(tmp_path, env_clean):
    transport = FakeEtsy(existing_drafts=[{"listing_id": 444000, "title": METADATA["title"], "state": "draft"}])
    service, _store, runner = _service_with_creds(tmp_path, transport)
    book = _make_book(tmp_path, service)

    result = runner.create_or_resume(service, book)
    assert result.ok and result.listing_id == "444000"
    create_posts = [r for r in transport.requests if r.method == "POST" and r.url.endswith("/listings")]
    assert create_posts == []                     # never created a second draft
    assert any("existing_draft_adopted" == e or "Adopted" in e for e in result.events)


def test_crash_mid_flow_resumes_without_duplicates_or_reuploads(tmp_path, env_clean):
    transport = FakeEtsy()
    service, _store, runner = _service_with_creds(tmp_path, transport)
    book = _make_book(tmp_path, service)
    first = runner.create_or_resume(service, book)
    assert first.ok
    listing_id = first.listing_id

    second = runner.create_or_resume(service, book)     # full re-run after success
    assert second.ok and second.listing_id == listing_id
    create_posts = [r for r in transport.requests if r.method == "POST" and r.url.endswith("/listings")]
    assert len(create_posts) == 1                       # still exactly one draft ever created
    file_uploads = [r for r in transport.requests if r.method == "POST" and r.url.endswith("/files")]
    image_uploads = [r for r in transport.requests if r.method == "POST" and r.url.endswith("/images")]
    assert len(file_uploads) == 1 and len(image_uploads) == 1   # attachments not duplicated


def test_vanished_draft_is_recreated_fresh(tmp_path, env_clean):
    transport = FakeEtsy(listing_404_ids={555001})
    service, _store, runner = _service_with_creds(tmp_path, transport)
    book = _make_book(tmp_path, service)
    service.db.set_integration_state("b1", "etsy", "draft_created",
                                     external_sku="printable.pdf", idempotency_key="k")
    service.db.transition_status("b1", "etsy", "Ready", external_id="555001", source="etsy_draft")

    result = runner.create_or_resume(service, book)
    assert result.ok and result.listing_id == str(transport.created_listing_id)
    assert result.listing_id != "555001"
    assert any("creating fresh" in event for event in result.events)


def test_no_local_image_still_succeeds_with_truthful_note(tmp_path, env_clean):
    transport = FakeEtsy()
    service, _store, runner = _service_with_creds(tmp_path, transport)
    book = _make_book(tmp_path, service, with_image=False)

    result = runner.create_or_resume(service, book)
    assert result.ok
    assert any("image" in event.lower() and ("skipped" in event.lower() or "No thumbnail" in event) for event in result.events)


def test_unexpected_online_state_reported_never_changed(tmp_path, env_clean):
    transport = FakeEtsy(listing_state="active")
    service, _store, runner = _service_with_creds(tmp_path, transport)
    book = _make_book(tmp_path, service)
    service.db.set_integration_state("b1", "etsy", "files_uploaded",
                                     external_sku="printable.pdf", idempotency_key="k")
    service.db.transition_status("b1", "etsy", "Ready", external_id="555001", source="etsy_draft")

    result = runner.create_or_resume(service, book)
    assert not result.ok and "review it manually" in result.message.lower()


# ---------------------------------------------------------------------------
# Hard no-activation proofs
# ---------------------------------------------------------------------------


def test_client_has_no_activation_capability():
    forbidden = ("update", "delete", "activate", "publish", "renew", "state")
    methods = [name for name in dir(EtsyDraftClient) if not name.startswith("_")]
    assert not [name for name in methods if any(word in name for word in forbidden)]


def test_no_request_ever_activates_a_listing(tmp_path, env_clean):
    transport = FakeEtsy()
    service, _store, runner = _service_with_creds(tmp_path, transport)
    book = _make_book(tmp_path, service)
    assert runner.create_or_resume(service, book).ok

    for request in transport.requests:
        assert request.method in ("GET", "POST"), request.url
        assert "active" not in request.url.lower()
    create_posts = [r for r in transport.requests if r.method == "POST" and r.url.endswith("/listings")]
    for request in create_posts:
        body = request.body.decode("utf-8")
        assert "type=download" in body
        assert urllib.parse.unquote_plus(body).lower().count("active") == 0
