"""Phase B (Etsy Connection + Draft Automation) M1 tests: secure storage,
OAuth code exchange / refresh, the authenticated session pipeline, and the
multipart body builder.

Everything runs offline: transports are injected fakes and the Windows
Credential Manager is exercised only through monkeypatched module seams, so
the real user credential store is never touched by automation.
"""

import json
import sys
import urllib.parse

import pytest

from integrations import wincred
from integrations.errors import AuthError, NotConfiguredError
from integrations.http import HttpRequest, HttpResponse, build_multipart_body
from integrations.etsy import auth as etsy_auth
from integrations.etsy import session as etsy_session
from integrations.etsy.connection import EtsyCredentials


class MockTransport:
    """Scripted offline transport recording every request it was asked to send."""

    def __init__(self, handler):
        self.handler = handler
        self.requests = []

    def send(self, request, timeout_seconds):
        self.requests.append((request, timeout_seconds))
        return self.handler(len(self.requests), request)


def _json_response(status_code, payload):
    return HttpResponse(
        status_code=status_code,
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload).encode("utf-8"),
    )


TOKEN_PAYLOAD = {
    "access_token": "fresh-access-token-1234567890",
    "refresh_token": "rotated-refresh-token-0987654321",
    "expires_in": 3600,
    "token_type": "Bearer",
    "scope": "shops_r listings_r listings_w",
}


# ---------------------------------------------------------------------------
# Windows Credential Manager storage (mocked seams; never the real store)
# ---------------------------------------------------------------------------


class FakeCredStore:
    """In-memory stand-in for advapi32 CredWrite/Read/Delete."""

    def __init__(self):
        self.blobs = {}

    def write(self, target, user_name, secret_bytes):
        self.blobs[target] = (user_name, secret_bytes)

    def read(self, target):
        found = self.blobs.get(target)
        return None if found is None else wincred._CredBlob(found[0], found[1])

    def delete(self, target):
        return self.blobs.pop(target, None) is not None


@pytest.fixture()
def fake_cred(monkeypatch):
    store = FakeCredStore()
    monkeypatch.setattr(wincred, "_write_impl", store.write)
    monkeypatch.setattr(wincred, "_read_impl", store.read)
    monkeypatch.setattr(wincred, "_delete_impl", store.delete)
    return store


def test_wincred_round_trip(fake_cred):
    payload = {"api_keystring": "key123", "access_token": "tok456"}
    wincred.store_secret("Etsy", payload)
    assert wincred.load_secret("Etsy") == payload


def test_wincred_missing_returns_none_and_delete_false(fake_cred):
    assert wincred.load_secret("Etsy") is None
    assert wincred.delete_secret("Etsy") is False
    assert wincred.credential_target("Etsy") == "KDPuzzleEngine/Etsy"


def test_wincred_delete_removes_only_target_entry(fake_cred):
    wincred.store_secret("Etsy", {"a": 1})
    wincred.store_secret("Lulu", {"b": 2})
    assert wincred.delete_secret("Etsy") is True
    assert wincred.load_secret("Etsy") is None
    assert wincred.load_secret("Lulu") == {"b": 2}


def test_credentials_serialize_round_trip_ignores_unknown_keys():
    creds = EtsyCredentials(api_keystring="k", shared_secret="s", access_token="a")
    payload = etsy_session.serialize_credentials(creds)
    payload["harmless_extra"] = "ignored"
    rebuilt = etsy_session.deserialize_credentials(payload)
    assert rebuilt == creds


def test_load_credentials_env_complete_wins_over_store(monkeypatch, fake_cred):
    monkeypatch.setenv("KDP_ETSY_API_KEYSTRING", "env-key")
    monkeypatch.setenv("KDP_ETSY_ACCESS_TOKEN", "env-token")
    etsy_session.save_credentials(
        EtsyCredentials(api_keystring="stored-key", access_token="stored-token")
    )
    loaded = etsy_session.load_credentials(store=fake_cred and etsy_session.WinCredTokenStore())
    # The fixture patches the module seams, so WinCredTokenStore reads the fake.
    assert (loaded.api_keystring, loaded.access_token) == ("env-key", "env-token")


def test_load_credentials_merges_env_keystring_with_stored_tokens(monkeypatch, fake_cred):
    monkeypatch.delenv("KDP_ETSY_API_KEYSTRING", raising=False)
    monkeypatch.delenv("KDP_ETSY_SHARED_SECRET", raising=False)
    monkeypatch.delenv("KDP_ETSY_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("KDP_ETSY_REFRESH_TOKEN", raising=False)
    etsy_session.save_credentials(
        EtsyCredentials(
            api_keystring="stored-key",
            shared_secret="stored-secret",
            access_token="stored-token",
            refresh_token="stored-refresh",
        )
    )
    monkeypatch.setenv("KDP_ETSY_API_KEYSTRING", "env-key")
    loaded = etsy_session.load_credentials(store=etsy_session.WinCredTokenStore())
    assert loaded.api_keystring == "env-key"
    assert loaded.shared_secret == "stored-secret"
    assert loaded.access_token == "stored-token"
    assert loaded.refresh_token == "stored-refresh"


# ---------------------------------------------------------------------------
# OAuth code exchange and refresh execution
# ---------------------------------------------------------------------------


def _form_fields(request):
    return dict(urllib.parse.parse_qsl(request.body.decode("utf-8"), keep_blank_values=True))


def test_exchange_authorization_code_builds_correct_request():
    seen = {}

    def handler(_index, request):
        seen["request"] = request
        return _json_response(200, TOKEN_PAYLOAD)

    tokens = etsy_session.exchange_authorization_code(
        client_id="my-keystring",
        authorization_code="one-time-code-abcdef",
        code_verifier="verifier-value-abcdef-43-characters-long!!!!!",
        redirect_uri="https://example.com/callback",
        transport=MockTransport(handler),
    )
    request = seen["request"]
    assert request.method == "POST"
    assert request.url == etsy_auth.ETSY_TOKEN_URL
    fields = _form_fields(request)
    assert fields["grant_type"] == "authorization_code"
    assert fields["client_id"] == "my-keystring"
    assert fields["code"] == "one-time-code-abcdef"
    assert fields["code_verifier"] == "verifier-value-abcdef-43-characters-long!!!!!"
    assert tokens.access_token == TOKEN_PAYLOAD["access_token"]
    assert tokens.refresh_token == TOKEN_PAYLOAD["refresh_token"]
    assert set(tokens.scope.split()) == {"shops_r", "listings_r", "listings_w"}


def test_refresh_access_token_rotates_tokens():
    seen = {}

    def handler(_index, request):
        seen["request"] = request
        return _json_response(200, TOKEN_PAYLOAD)

    tokens = etsy_session.refresh_access_token(
        client_id="my-keystring",
        refresh_token="old-refresh-token-123456",
        transport=MockTransport(handler),
    )
    fields = _form_fields(seen["request"])
    assert fields["grant_type"] == "refresh_token"
    assert fields["client_id"] == "my-keystring"
    assert fields["refresh_token"] == "old-refresh-token-123456"
    assert tokens.has_refresh_token


def test_token_error_response_raises_auth_error():
    def handler(_index, _request):
        return _json_response(400, {"error": "invalid_grant", "error_description": "code expired"})

    with pytest.raises(AuthError):
        etsy_session.exchange_authorization_code(
            client_id="k",
            authorization_code="bad-one-time-code",
            code_verifier="v" * 43,
            transport=MockTransport(handler),
        )


def test_draft_scopes_constant_excludes_destructive_scope():
    assert "listings_w" in etsy_auth.DRAFT_SCOPES
    assert "listings_r" in etsy_auth.DRAFT_SCOPES
    assert "shops_r" in etsy_auth.DRAFT_SCOPES
    assert "listings_d" not in etsy_auth.DRAFT_SCOPES
    for scope in etsy_auth.READ_ONLY_SCOPES:
        assert scope in etsy_auth.DRAFT_SCOPES


# ---------------------------------------------------------------------------
# EtsySession authenticated request pipeline
# ---------------------------------------------------------------------------


def _creds(**overrides):
    base = {
        "api_keystring": "keystring-1234",
        "shared_secret": "shhhhh-secret",
        "access_token": "current-access-token-1",
        "refresh_token": "",
    }
    base.update(overrides)
    return EtsyCredentials(**base)


def test_session_injects_auth_headers_once():
    seen = {}

    def handler(_index, request):
        seen.setdefault("headers", dict(request.headers))
        return _json_response(200, {"ok": True})

    sess = etsy_session.EtsySession(lambda: _creds(), transport=MockTransport(handler))
    response = sess.send(HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me"))
    assert response.status_code == 200
    headers = {k.lower(): v for k, v in seen["headers"].items()}
    assert headers["authorization"].startswith("Bearer current-access-token-1")
    assert headers["x-api-key"] == "keystring-1234:shhhhh-secret"


def test_session_refreshes_once_on_auth_failure_and_persists_rotation():
    calls = {"n": 0}

    def handler(_index, request):
        calls["n"] += 1
        auth = request.headers.get("Authorization", "")
        if "fresh-access-token" not in auth:
            return HttpResponse(status_code=401, headers={}, body=b'{"error":"invalid_auth"}')
        return _json_response(200, {"ok": True})

    token_requests = []

    class DualTransport:
        def __init__(self):
            self.api = MockTransport(handler)

        def send(self, request, timeout_seconds):
            if request.url.startswith(etsy_auth.ETSY_TOKEN_URL):
                token_requests.append(request)
                return _json_response(200, TOKEN_PAYLOAD)
            return self.api.send(request, timeout_seconds)

    transport = DualTransport()

    class MemoryStore:
        def __init__(self):
            self.saved = None

        def load(self):
            return None

        def save(self, credentials):
            self.saved = credentials

        def forget(self):
            return True

    store = MemoryStore()
    sess = etsy_session.EtsySession(lambda: _creds(refresh_token="old-refresh-1234"), transport=transport, token_store=store)
    response = sess.send(HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me"))
    assert response.status_code == 200
    assert calls["n"] == 2  # one rejected attempt + one successful retry
    assert len(token_requests) == 1
    assert store.saved is not None
    assert store.saved.access_token == TOKEN_PAYLOAD["access_token"]
    assert store.saved.refresh_token == TOKEN_PAYLOAD["refresh_token"]


def test_session_without_refresh_token_reports_reconnect():
    def handler(_index, _request):
        return HttpResponse(status_code=403, headers={}, body=b"{}")

    sess = etsy_session.EtsySession(lambda: _creds(), transport=MockTransport(handler))
    with pytest.raises(AuthError) as excinfo:
        sess.send(HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me"))
    assert "Reconnect" in str(excinfo.value)


def test_session_requires_configuration_before_any_remote_call():
    sess = etsy_session.EtsySession(lambda: EtsyCredentials(), transport=None)
    with pytest.raises(NotConfiguredError):
        sess.send(HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me"))


def test_session_never_puts_secrets_into_urls():
    seen = {}

    def handler(_index, request):
        seen["url"] = request.url
        return _json_response(200, {})

    sess = etsy_session.EtsySession(lambda: _creds(), transport=MockTransport(handler))
    sess.send(HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me"))
    assert "current-access-token-1" not in seen["url"]
    assert "shhhhh-secret" not in seen["url"]


@pytest.mark.skipif(sys.platform != "win32", reason="availability check is Windows-specific")
def test_wincred_available_on_windows():
    assert isinstance(wincred.is_available(), bool)


# ---------------------------------------------------------------------------
# multipart/form-data builder (uploadListingFile / uploadListingImage)
# ---------------------------------------------------------------------------


def _parse_multipart(body: bytes, content_type: str):
    header = content_type.split("boundary=", 1)[1].strip()
    parts = []
    for chunk in body.split(f"--{header}".encode()):
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue
        raw_headers, _, payload = chunk.partition(b"\r\n\r\n")
        disposition = ""
        part_type = ""
        for line in raw_headers.decode("utf-8").split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                disposition = line
            elif line.lower().startswith("content-type:"):
                part_type = line.split(":", 1)[1].strip()
        name = disposition.split('name="', 1)[1].split('"', 1)[0] if 'name="' in disposition else ""
        filename = ""
        if 'filename="' in disposition:
            filename = disposition.split('filename="', 1)[1].split('"', 1)[0]
        parts.append({"name": name, "filename": filename, "type": part_type, "payload": payload})
    return parts


def test_multipart_body_round_trips_text_and_binary_parts():
    binary = bytes(range(256)) * 3
    body, content_type = build_multipart_body(
        fields={"name": "printable.pdf"},
        files=[("file", "printable.pdf", binary, "application/pdf")],
    )
    assert content_type.startswith("multipart/form-data; boundary=")
    parts = _parse_multipart(body, content_type)
    by_name = {part["name"]: part for part in parts}
    assert by_name["name"]["payload"] == b"printable.pdf"
    assert by_name["file"]["filename"] == "printable.pdf"
    assert by_name["file"]["type"] == "application/pdf"
    assert by_name["file"]["payload"] == binary  # byte-exact, binary safe


def test_multipart_body_unique_boundary_per_call():
    _, first = build_multipart_body(fields={"a": "1"})
    _, second = build_multipart_body(fields={"a": "1"})
    assert first != second
