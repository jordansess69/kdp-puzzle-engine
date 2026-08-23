"""Small SQLite store that can grow to a large catalog without changing theme files."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

MARKETPLACES = ("amazon", "etsy", "ingram", "website", "lulu", "bookvault", "barnes_noble")


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
            rows = db.execute("SELECT marketplace,status,external_id,url,updated_at FROM marketplace_status WHERE book_id=?", (book_id,)).fetchall()
        records = {row["marketplace"]: dict(row) for row in rows}
        for marketplace in MARKETPLACES:
            records.setdefault(marketplace, {"marketplace": marketplace, "status": "Not Prepared", "external_id": "", "url": "", "updated_at": ""})
        return records

    def set_status(self, book_id: str, marketplace: str, status: str, external_id: str = "", url: str = "") -> None:
        if marketplace not in MARKETPLACES: raise ValueError("Unknown marketplace")
        with self._connect() as db: db.execute("""INSERT INTO marketplace_status(book_id,marketplace,status,external_id,url,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(book_id,marketplace) DO UPDATE SET status=excluded.status, external_id=excluded.external_id, url=excluded.url, updated_at=excluded.updated_at""", (book_id, marketplace, status, external_id, url, datetime.now().isoformat(timespec="seconds")))

    def update_marketplace_record(self, book_id: str, marketplace: str, status: str, external_id: str, url: str) -> None:
        """Save a confirmed marketplace identifier/link without guessing its live state."""
        self.set_status(book_id, marketplace, status, external_id.strip(), url.strip())

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
