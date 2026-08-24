"""Small SQLite store that can grow to a large catalog without changing theme files."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

MARKETPLACES = ("amazon", "etsy", "ingram", "website", "lulu", "bookvault", "barnes_noble")
# Confirmed upload/live states. Automated flows (prepare, local scans, future
# API/browser adapters) must never move a marketplace backwards from these or
# overwrite the identifiers the user confirmed; only explicit manual saves may.
PROTECTED_STATUSES = ("Uploaded", "Published")


class PublishingDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path; self.db_path.parent.mkdir(parents=True, exist_ok=True); self._setup()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path); connection.row_factory = sqlite3.Row; return connection

    def _setup(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS books (book_id TEXT PRIMARY KEY, source_key TEXT UNIQUE NOT NULL, metadata_json TEXT NOT NULL, metadata_locked INTEGER NOT NULL DEFAULT 0, package_path TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS marketplace_status (book_id TEXT NOT NULL, marketplace TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Not Prepared', external_id TEXT DEFAULT '', url TEXT DEFAULT '', updated_at TEXT NOT NULL, PRIMARY KEY (book_id, marketplace), FOREIGN KEY(book_id) REFERENCES books(book_id));
                CREATE TABLE IF NOT EXISTS isbns (isbn TEXT PRIMARY KEY, book_id TEXT, title TEXT, format TEXT, source TEXT, assigned_at TEXT);
                CREATE TABLE IF NOT EXISTS bundles (bundle_id TEXT PRIMARY KEY, title TEXT NOT NULL, book_ids_json TEXT NOT NULL, metadata_json TEXT NOT NULL, output_path TEXT NOT NULL, created_at TEXT NOT NULL);
            """)
            # Additive migration for older catalogs: the persisted preparation
            # error message arrived after the first release of this table.
            columns = {row[1] for row in db.execute("PRAGMA table_info(marketplace_status)")}
            if "error_message" not in columns:
                db.execute("ALTER TABLE marketplace_status ADD COLUMN error_message TEXT NOT NULL DEFAULT ''")
            # Additive migration for online integration state (Etsy draft
            # automation).  These columns live NEXT TO the confirmed human
            # status on purpose: automated flows write here, while the
            # buyer-facing ``status`` column and its Uploaded/Published guard
            # keep their exact existing semantics.
            if "integration_state" not in columns:
                db.execute("ALTER TABLE marketplace_status ADD COLUMN integration_state TEXT NOT NULL DEFAULT ''")
            if "external_sku" not in columns:
                db.execute("ALTER TABLE marketplace_status ADD COLUMN external_sku TEXT NOT NULL DEFAULT ''")
            if "idempotency_key" not in columns:
                db.execute("ALTER TABLE marketplace_status ADD COLUMN idempotency_key TEXT NOT NULL DEFAULT ''")
            if "last_synced_at" not in columns:
                db.execute("ALTER TABLE marketplace_status ADD COLUMN last_synced_at TEXT NOT NULL DEFAULT ''")
            # Append-only history of marketplace status changes. Rows are never
            # updated or deleted, so the publishing trail survives catalog prunes
            # and gives every screen one truthful answer to "what happened here?".
            db.executescript("""
                CREATE TABLE IF NOT EXISTS marketplace_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    marketplace TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT,
                    changed_at TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'manual',
                    external_id TEXT DEFAULT '',
                    listing_url TEXT DEFAULT '',
                    error_message TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_marketplace_audit_book ON marketplace_audit(book_id, changed_at);
                CREATE TABLE IF NOT EXISTS integration_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    marketplace TEXT NOT NULL,
                    event TEXT NOT NULL,
                    detail TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_integration_log_book ON integration_log(book_id, marketplace, created_at);
            """)

    def upsert_book(self, book_id: str, source_key: str, metadata: dict, package_path: str = "") -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            row = db.execute("SELECT metadata_locked, metadata_json FROM books WHERE book_id=?", (book_id,)).fetchone()
            stored = row["metadata_json"] if row and row["metadata_locked"] else json.dumps(metadata)
            db.execute("""INSERT INTO books(book_id,source_key,metadata_json,package_path,created_at,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(book_id) DO UPDATE SET source_key=excluded.source_key, metadata_json=?, package_path=excluded.package_path, updated_at=excluded.updated_at""", (book_id, source_key, stored, package_path, now, now, stored))
            for marketplace in MARKETPLACES: db.execute("INSERT OR IGNORE INTO marketplace_status(book_id,marketplace,status,updated_at) VALUES(?,?,?,?)", (book_id, marketplace, "Not Prepared", now))

    def list_books(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM books ORDER BY updated_at DESC").fetchall(); output = []
            for row in rows:
                item = dict(row); item["metadata"] = json.loads(item.pop("metadata_json")); item["statuses"] = self.statuses(item["book_id"]); output.append(item)
            return output

    def get_book(self, book_id: str) -> dict | None:
        return next((book for book in self.list_books() if book["book_id"] == book_id), None)

    def save_metadata(self, book_id: str, metadata: dict, locked: bool | None = None) -> None:
        with self._connect() as db:
            if locked is None: db.execute("UPDATE books SET metadata_json=?, updated_at=? WHERE book_id=?", (json.dumps(metadata), datetime.now().isoformat(timespec="seconds"), book_id))
            else: db.execute("UPDATE books SET metadata_json=?, metadata_locked=?, updated_at=? WHERE book_id=?", (json.dumps(metadata), int(locked), datetime.now().isoformat(timespec="seconds"), book_id))

    def statuses(self, book_id: str) -> dict[str, str]:
        with self._connect() as db: return {row["marketplace"]: row["status"] for row in db.execute("SELECT marketplace,status FROM marketplace_status WHERE book_id=?", (book_id,))}

    def marketplace_records(self, book_id: str) -> dict[str, dict]:
        """Return the full, buyer-facing publishing trail for one book."""
        with self._connect() as db:
            rows = db.execute("SELECT marketplace,status,external_id,url,updated_at,error_message,integration_state,last_synced_at FROM marketplace_status WHERE book_id=?", (book_id,)).fetchall()
        records = {row["marketplace"]: dict(row) for row in rows}
        for marketplace in MARKETPLACES:
            records.setdefault(marketplace, {"marketplace": marketplace, "status": "Not Prepared", "external_id": "", "url": "", "updated_at": "", "error_message": "", "integration_state": "", "last_synced_at": ""})
        return records

    def transition_status(self, book_id: str, marketplace: str, new_status: str, external_id: str | None = None,
                          url: str | None = None, source: str = "manual", error_message: str = "") -> dict:
        """The one guarded path for changing a marketplace status.

        - Confirmed ``Uploaded``/``Published`` records are protected: any
          non-manual source (prepare, local scans, future API/browser adapters)
          is refused without touching files or data.
        - Identifiers and links are preserved unless explicitly supplied.
        - Every actual change appends exactly one audit row; no-op calls write
          nothing at all.
        """
        if marketplace not in MARKETPLACES:
            raise ValueError("Unknown marketplace")
        prior = self.marketplace_records(book_id)[marketplace]
        if prior["status"] in PROTECTED_STATUSES and source != "manual":
            return {"changed": False, "protected": True,
                    "message": f"{marketplace} is already recorded as {prior['status']}; nothing was changed.",
                    "record": prior}
        final_external = prior["external_id"] if external_id is None else str(external_id).strip()
        final_url = prior["url"] if url is None else str(url).strip()
        final_error = "" if new_status != "Error" else str(error_message or "").strip()
        changed = (new_status != prior["status"] or final_external != prior["external_id"]
                   or final_url != prior["url"] or final_error != (prior.get("error_message") or ""))
        if not changed:
            return {"changed": False, "protected": False, "message": "", "record": prior}
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute("""INSERT INTO marketplace_status(book_id,marketplace,status,external_id,url,error_message,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(book_id,marketplace) DO UPDATE SET status=excluded.status, external_id=excluded.external_id, url=excluded.url, error_message=excluded.error_message, updated_at=excluded.updated_at""",
                       (book_id, marketplace, new_status, final_external, final_url, final_error, now))
            # Append-only trail: insert only, never update or delete.
            db.execute("""INSERT INTO marketplace_audit(book_id,marketplace,old_status,new_status,changed_at,source,external_id,listing_url,error_message) VALUES(?,?,?,?,?,?,?,?,?)""",
                       (book_id, marketplace, prior["status"], new_status, now, source, final_external, final_url, final_error))
        return {"changed": True, "protected": False, "message": "", "record": self.marketplace_records(book_id)[marketplace]}

    def set_status(self, book_id: str, marketplace: str, status: str, external_id: str | None = None, url: str | None = None) -> None:
        """Backward-compatible wrapper; identifiers are preserved when omitted."""
        self.transition_status(book_id, marketplace, status, external_id=external_id, url=url)

    def update_marketplace_record(self, book_id: str, marketplace: str, status: str, external_id: str, url: str) -> None:
        """Save a confirmed marketplace identifier/link without guessing its live state."""
        self.transition_status(book_id, marketplace, status, external_id=external_id, url=url, source="manual")

    def audit_history(self, book_id: str | None = None, marketplace: str | None = None) -> list[dict]:
        """Read the append-only publishing trail, newest first."""
        query = "SELECT audit_id,book_id,marketplace,old_status,new_status,changed_at,source,external_id,listing_url,error_message FROM marketplace_audit"
        params: tuple = ()
        clauses = []
        if book_id is not None:
            clauses.append("book_id=?"); params += (book_id,)
        if marketplace is not None:
            clauses.append("marketplace=?"); params += (marketplace,)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY changed_at DESC, audit_id DESC"
        with self._connect() as db:
            return [dict(row) for row in db.execute(query, params)]

    # -- Online integration state (automated flows write here; ``status`` stays human-owned)

    def integration_record(self, book_id: str, marketplace: str) -> dict:
        """Automation-side record for one marketplace (never the buyer-facing status)."""
        with self._connect() as db:
            row = db.execute(
                "SELECT integration_state, external_sku, idempotency_key, last_synced_at FROM marketplace_status WHERE book_id=? AND marketplace=?",
                (book_id, marketplace),
            ).fetchone()
        if not row:
            return {"integration_state": "", "external_sku": "", "idempotency_key": "", "last_synced_at": ""}
        return {key: (row[key] or "") for key in ("integration_state", "external_sku", "idempotency_key", "last_synced_at")}

    def set_integration_state(self, book_id: str, marketplace: str, state: str,
                              external_sku: str | None = None, idempotency_key: str | None = None) -> dict:
        """Persist automated progress without touching the confirmed status column.

        Only the four integration columns are written; ``status``,
        ``external_id``, ``url`` and ``error_message`` keep their values, and
        no marketplace_audit row is produced (the integration log carries this
        stream instead).
        """
        if marketplace not in MARKETPLACES:
            raise ValueError("Unknown marketplace")
        prior = self.integration_record(book_id, marketplace)
        final_state = str(state).strip()
        final_sku = prior["external_sku"] if external_sku is None else str(external_sku).strip()
        final_key = prior["idempotency_key"] if idempotency_key is None else str(idempotency_key).strip()
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute("""INSERT INTO marketplace_status(book_id,marketplace,status,integration_state,external_sku,idempotency_key,last_synced_at,updated_at) VALUES(?,?,?,?,?,?,?,?)
                          ON CONFLICT(book_id,marketplace) DO UPDATE SET integration_state=excluded.integration_state, external_sku=excluded.external_sku, idempotency_key=excluded.idempotency_key, last_synced_at=excluded.last_synced_at""",
                       (book_id, marketplace, "Not Prepared", final_state, final_sku, final_key, now, now))
        return self.integration_record(book_id, marketplace)

    def clear_integration_state(self, book_id: str, marketplace: str) -> None:
        """Reset automation columns only (used when reconciliation proves a draft vanished)."""
        if marketplace not in MARKETPLACES:
            raise ValueError("Unknown marketplace")
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute("""INSERT INTO marketplace_status(book_id,marketplace,status,integration_state,external_sku,idempotency_key,last_synced_at,updated_at) VALUES(?,?,?,?,?,?,?,?)
                          ON CONFLICT(book_id,marketplace) DO UPDATE SET integration_state='', external_sku='', idempotency_key='', last_synced_at=''""",
                       (book_id, marketplace, "Not Prepared", "", "", "", "", now))

    def record_integration_event(self, book_id: str, marketplace: str, event: str, detail: str = "") -> None:
        """Append one sanitized automation event to the integration log.

        The detail text passes through the shared secret redactor so token-like
        strings can never reach the log through an exception message.
        """
        from integrations.errors import redact_text

        clean_detail = redact_text(str(detail or "")).replace("\n", " ").strip()
        with self._connect() as db:
            db.execute("INSERT INTO integration_log(book_id,marketplace,event,detail,created_at) VALUES(?,?,?,?,?)",
                       (book_id, marketplace, str(event).strip(), clean_detail[:500], datetime.now().isoformat(timespec="seconds")))

    def integration_history(self, book_id: str, marketplace: str | None = None) -> list[dict]:
        """Read the append-only automation trail for one book, newest first."""
        query = "SELECT log_id,book_id,marketplace,event,detail,created_at FROM integration_log WHERE book_id=?"
        params: tuple = (book_id,)
        if marketplace is not None:
            query += " AND marketplace=?"
            params += (marketplace,)
        query += " ORDER BY created_at DESC, log_id DESC"
        with self._connect() as db:
            return [dict(row) for row in db.execute(query, params)]

    def assign_isbn(self, isbn: str, book_id: str, title: str, source: str) -> None:
        isbn = "".join(isbn.split()).replace("-", "")
        if not isbn: return
        with self._connect() as db:
            prior = db.execute("SELECT book_id FROM isbns WHERE isbn=?", (isbn,)).fetchone()
            if prior and prior["book_id"] not in (None, book_id): raise ValueError("That ISBN is already assigned to a different book.")
            db.execute("INSERT OR REPLACE INTO isbns(isbn,book_id,title,format,source,assigned_at) VALUES(?,?,?,?,?,?)", (isbn, book_id, title, "Paperback", source, datetime.now().isoformat(timespec="seconds")))

    def list_isbns(self) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM isbns ORDER BY assigned_at DESC")]

    def save_bundle(self, bundle_id: str, title: str, book_ids: list[str], metadata: dict, output_path: str) -> None:
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO bundles(bundle_id,title,book_ids_json,metadata_json,output_path,created_at) VALUES(?,?,?,?,?,?)", (bundle_id, title, json.dumps(book_ids), json.dumps(metadata), output_path, datetime.now().isoformat(timespec="seconds")))

    def list_bundles(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM bundles ORDER BY created_at DESC").fetchall()
        result = []
        for row in rows:
            item = dict(row); item["book_ids"] = json.loads(item.pop("book_ids_json")); item["metadata"] = json.loads(item.pop("metadata_json")); result.append(item)
        return result

    def prune_sources(self, active_source_keys: set[str]) -> int:
        """Remove only stale/duplicate catalog rows; never touches a theme or package file."""
        with self._connect() as db:
            rows = db.execute("SELECT book_id,source_key FROM books").fetchall()
            remove = [row["book_id"] for row in rows if row["source_key"] not in active_source_keys]
            for book_id in remove:
                db.execute("DELETE FROM marketplace_status WHERE book_id=?", (book_id,))
                db.execute("DELETE FROM books WHERE book_id=?", (book_id,))
            return len(remove)

    def prune_duplicate_unpublished_package_titles(self) -> int:
        """Keep the newest untracked package for a title without touching files.

        A package may be rebuilt after a cover or content correction.  Those
        dated folders are valuable history on disk, but they should not appear
        as duplicate books in Publishing Manager.  Anything that has moved
        beyond ``Not Prepared`` is retained so confirmed marketplace work is
        never hidden or discarded automatically.
        """
        with self._connect() as db:
            rows = db.execute(
                "SELECT book_id, source_key, metadata_json, updated_at FROM books "
                "WHERE source_key LIKE 'package:%'"
            ).fetchall()
            groups: dict[str, list[sqlite3.Row]] = {}
            for row in rows:
                try:
                    title = str(json.loads(row["metadata_json"]).get("title") or "").strip().casefold()
                except json.JSONDecodeError:
                    continue
                if title:
                    groups.setdefault(title, []).append(row)
            remove: list[str] = []
            for candidates in groups.values():
                if len(candidates) < 2:
                    continue
                protected = []
                for row in candidates:
                    statuses = db.execute(
                        "SELECT status FROM marketplace_status WHERE book_id=?", (row["book_id"],)
                    ).fetchall()
                    if any(status["status"] != "Not Prepared" for status in statuses):
                        protected.append(row)
                keep = max(protected or candidates, key=lambda row: str(row["updated_at"]))
                for row in candidates:
                    if row["book_id"] != keep["book_id"] and row not in protected:
                        remove.append(row["book_id"])
            for book_id in remove:
                db.execute("DELETE FROM marketplace_status WHERE book_id=?", (book_id,))
                db.execute("DELETE FROM books WHERE book_id=?", (book_id,))
            return len(remove)
