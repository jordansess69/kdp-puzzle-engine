"""Phase B M3 tests: additive database foundation for online integrations.

Proves the migration never loses data from older catalog schemas, that
automation writes NEVER touch the human-owned status column or its audit
trail, and that integration log details are sanitized.
"""

import json
import sqlite3

import pytest

from publishing.database import MARKETPLACES, PublishingDatabase


@pytest.fixture()
def db(tmp_path):
    return PublishingDatabase(tmp_path / "catalog.db")


def _add_book(db, book_id="book-1"):
    db.upsert_book(book_id, f"theme:{book_id}", {"title": "Test Book"})


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------


def test_fresh_schema_has_integration_columns_and_log(db):
    with sqlite3.connect(db.db_path) as raw:
        columns = {row[1] for row in raw.execute("PRAGMA table_info(marketplace_status)")}
        tables = {row[0] for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"integration_state", "external_sku", "idempotency_key", "last_synced_at"} <= columns
    assert "integration_log" in tables


def test_legacy_schema_migrates_without_data_loss(tmp_path):
    """A pre-release catalog (no error_message column at all) upgrades in place."""
    path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(path)
    legacy.executescript("""
        CREATE TABLE books (book_id TEXT PRIMARY KEY, source_key TEXT UNIQUE NOT NULL, metadata_json TEXT NOT NULL,
                            metadata_locked INTEGER NOT NULL DEFAULT 0, package_path TEXT,
                            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE marketplace_status (book_id TEXT NOT NULL, marketplace TEXT NOT NULL,
                                         status TEXT NOT NULL DEFAULT 'Not Prepared', external_id TEXT DEFAULT '',
                                         url TEXT DEFAULT '', updated_at TEXT NOT NULL,
                                         PRIMARY KEY (book_id, marketplace));
        CREATE TABLE isbns (isbn TEXT PRIMARY KEY, book_id TEXT, title TEXT, format TEXT, source TEXT, assigned_at TEXT);
    """)
    legacy.execute(
        "INSERT INTO books VALUES('old-1', 'theme:old', ?, 1, '', '2025-01-01T00:00:00', '2025-01-01T00:00:00')",
        (json.dumps({"title": "Legacy Book"}),))
    legacy.execute(
        "INSERT INTO marketplace_status VALUES('old-1', 'etsy', 'Ready', '777', 'https://example.com/listing', '2025-01-02T00:00:00')")
    legacy.commit(); legacy.close()

    migrated = PublishingDatabase(path)  # opening performs the additive migration
    with sqlite3.connect(path) as raw:
        raw.row_factory = sqlite3.Row
        columns = {row[1] for row in raw.execute("PRAGMA table_info(marketplace_status)")}
        row = raw.execute("SELECT * FROM marketplace_status WHERE book_id='old-1' AND marketplace='etsy'").fetchone()
    assert {"error_message", "integration_state", "external_sku", "idempotency_key", "last_synced_at"} <= columns
    assert row["status"] == "Ready"                      # confirmed value preserved
    assert row["external_id"] == "777"                   # identifier preserved
    assert migrated.get_book("old-1")["metadata"]["title"] == "Legacy Book"


# ---------------------------------------------------------------------------
# Automation accessors never touch the human-owned columns
# ---------------------------------------------------------------------------


def test_set_integration_state_leaves_status_and_audit_untouched(db):
    _add_book(db)
    db.transition_status("book-1", "etsy", "Ready", source="prepare")
    audit_before = db.audit_history("book-1")

    record = db.set_integration_state("book-1", "etsy", "files_uploaded",
                                      external_sku="printable.pdf", idempotency_key="abc123")
    assert record["integration_state"] == "files_uploaded"
    assert record["external_sku"] == "printable.pdf"
    assert record["last_synced_at"]

    fresh = db.marketplace_records("book-1")["etsy"]
    assert fresh["status"] == "Ready"
    assert fresh["external_id"] == ""
    assert fresh["integration_state"] == "files_uploaded"
    assert db.audit_history("book-1") == audit_before  # separate log stream


def test_clear_integration_state_resets_only_automation_columns(db):
    _add_book(db)
    db.set_integration_state("book-1", "etsy", "complete", external_sku="x.pdf", idempotency_key="k1")
    db.clear_integration_state("book-1", "etsy")
    assert db.integration_record("book-1", "etsy") == {
        "integration_state": "", "external_sku": "", "idempotency_key": "", "last_synced_at": ""}


def test_integration_record_defaults_for_missing_row(db):
    _add_book(db)
    assert db.integration_record("book-1", "amazon") == {
        "integration_state": "", "external_sku": "", "idempotency_key": "", "last_synced_at": ""}


def test_unknown_marketplace_refused(db):
    _add_book(db)
    with pytest.raises(ValueError):
        db.set_integration_state("book-1", "not_real", "draft_created")


# ---------------------------------------------------------------------------
# Integration log: append-only, newest first, sanitized
# ---------------------------------------------------------------------------


def test_integration_events_are_newest_first_and_scoped_to_book(db):
    _add_book(db); _add_book(db, "book-2")
    db.record_integration_event("book-1", "etsy", "draft_created", "listing 111")
    db.record_integration_event("book-1", "etsy", "file_uploaded", "printable.pdf")
    history = db.integration_history("book-1")
    assert [entry["event"] for entry in history] == ["file_uploaded", "draft_created"]
    assert all(entry["book_id"] == "book-1" for entry in history)
    assert db.integration_history("book-2") == []


def test_integration_log_masks_token_shaped_details(db):
    _add_book(db)
    db.record_integration_event(
        "book-1", "etsy", "failed",
        detail="Authorization Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 rejected")
    entry = db.integration_history("book-1")[0]
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in entry["detail"]
    assert "[REDACTED]" in entry["detail"]
    assert entry["event"] == "failed"


def test_marketplace_records_include_integration_fields(db):
    _add_book(db)
    db.set_integration_state("book-1", "etsy", "draft_created", external_sku="printable.pdf")
    records = db.marketplace_records("book-1")
    assert set(records) == set(MARKETPLACES)
    for marketplace, record in records.items():
        assert "integration_state" in record and "last_synced_at" in record
    assert records["etsy"]["integration_state"] == "draft_created"
    assert records["amazon"]["integration_state"] == ""
