"""Catalog synchronization and marketplace preparation orchestration."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from .database import MARKETPLACES, PROTECTED_STATUSES, PublishingDatabase
from .marketplaces import PUBLISHERS
from .metadata_service import build_metadata
from .master_package import build_master_package
from .etsy_bundles import build_etsy_bundle, eligible_book_error
from theme_health import read_theme_health


class PublishingService:
    def __init__(self, project: Path) -> None:
        self.project = project; self.output = project / "out"; self.db = PublishingDatabase(project / "data" / "books.db")

    @staticmethod
    def _id(source_key: str) -> str:
        return hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:12]

    def sync_theme(self, theme_path: Path, package_path: Path | None = None) -> str:
        source = json.loads(theme_path.read_text(encoding="utf-8-sig")); key = str(theme_path.resolve()); book_id = self._id(key)
        meta = build_metadata(source); pages = int(source.get("interior_pages") or 0)
        health = read_theme_health(self.project / "data" / "theme_readiness_cache.json", theme_path)
        if not package_path or not package_path.is_dir(): package_path = self._find_package_for_title(meta["title"])
        if package_path and package_path.exists():
            meta["page_count"] = pages or self._pages_from_manifest(package_path) or self._interior_pages(package_path)
            meta["files"] = self._package_files(package_path)
        else:
            meta["page_count"] = pages or self._estimate_wordsearch_pages(source); meta["files"] = {}
        meta.update({"book_id": book_id, "puzzle_count": len(source.get("puzzles") or []), "trim_size": "8.5x11", "language": "English", "publication_date": "", "isbn": str(source.get("isbn") or ""), "edition": "1", "categories": meta["ingram_subjects"], "production_status": str((health or {}).get("status") or "Needs content check"), "price": {"amazon": 11.99, "etsy": 6.99, "ingram": 12.99, "direct_print": 12.99, "direct_digital": 5.99, "barnes_noble": 12.99, "lulu": 12.99, "bookvault": 12.99}, "last_synced": datetime.now().isoformat(timespec="seconds")})
        if package_path and package_path.is_dir():
            build_master_package(package_path, meta)
        self.db.upsert_book(book_id, key, meta, str(package_path or "")); return book_id

    def sync_catalog(self, themes: list[Path], release_catalog: dict) -> int:
        # Theme Builder keeps historical timestamped copies. They are useful
        # source backups but should not look like separate books for sale.
        grouped: dict[str, list[tuple[Path, Path | None]]] = {}
        unreadable: set[str] = set()
        for path in themes:
            try:
                source = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                # A theme file that still exists but cannot be read/parsed
                # (disk hiccup, partial write, encoding damage) must not
                # silently delete its catalog book — that would destroy
                # statuses, saved listing links and ISBN assignments during
                # a routine re-sync. Keep it active; fixing the file and
                # re-syncing refreshes it normally. Truly vanished files
                # (path gone) still prune as before.
                if path.is_file():
                    unreadable.add(str(path.resolve()))
                continue
            key = self._publication_key(source)
            record = release_catalog.get(path.name, {}); raw = str(record.get("package") or "")
            package = Path(raw) if raw else self._find_package_for_title(str(source.get("title") or ""))
            grouped.setdefault(key, []).append((path, package if package and package.is_dir() else None))
        active: set[str] = set()
        for candidates in grouped.values():
            path, package = max(candidates, key=self._canonical_score)
            self.sync_theme(path, package); active.add(str(path.resolve()))
        active |= unreadable
        self.db.prune_sources(active)
        return len(grouped)

    def sync_output_packages(self) -> int:
        """Register complete non-word-search books, which do not have theme JSON files."""
        imported = 0
        seen: set[Path] = set()
        for manifest_path in self.output.rglob("PACKAGE_SOURCE_RECORD.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8")); folder = manifest_path.parent
            except (OSError, json.JSONDecodeError):
                continue
            seen.add(folder.resolve()); source_theme = str(manifest.get("source_theme") or "")
            if source_theme and Path(source_theme).is_file():
                self.sync_theme(Path(source_theme), folder); continue
            key = "package:" + str(folder.resolve()); book_id = self._id(key)
            source = {"title": manifest.get("title"), "subtitle": manifest.get("subtitle"), "author": manifest.get("author"), "series": manifest.get("series", ""), "detected_topic": manifest.get("theme") or manifest.get("puzzle_type") or "Puzzle Book", "puzzle_count": manifest.get("puzzle_count", 0), "difficulty_label": manifest.get("difficulty", "Standard")}
            meta = build_metadata(source)
            meta.update({"book_id": book_id, "trim_size": manifest.get("trim_size", "8.5x11"), "language": "English", "publication_date": "", "isbn": "", "edition": "1", "categories": meta["ingram_subjects"], "production_status": "Complete package", "page_count": int(manifest.get("pages") or manifest.get("interior_pages") or self._interior_pages(folder)), "files": self._package_files(folder), "price": {"amazon": 11.99, "etsy": 6.99, "ingram": 12.99, "direct_print": 12.99, "direct_digital": 5.99, "barnes_noble": 12.99, "lulu": 12.99, "bookvault": 12.99}, "last_synced": datetime.now().isoformat(timespec="seconds")})
            build_master_package(folder, meta)
            self.db.upsert_book(book_id, key, meta, str(folder)); imported += 1
        # Version 3.28 and earlier already made high-quality non-word-search
        # packages. Import them from their listing kit instead of rebuilding.
        for interior in self.output.rglob("interior.pdf"):
            folder = interior.parent
            if folder.resolve() in seen or not (folder / "AUTOMATIC_BOOK_PLAN.txt").is_file(): continue
            try:
                listing = (folder / "KDP_LISTING_KIT.txt").read_text(encoding="utf-8-sig")
            except OSError:
                continue
            fields = {line.split(":", 1)[0].strip().casefold(): line.split(":", 1)[1].strip() for line in listing.splitlines() if ":" in line[:60]}
            kind = fields.get("book type", "")
            if kind not in {"Sudoku", "Cryptogram", "Word Scramble + Trivia", "Mixed Brain Games"}: continue
            key = "package:" + str(folder.resolve()); book_id = self._id(key)
            source = {"title": fields.get("title", folder.name), "subtitle": fields.get("subtitle", ""), "author": fields.get("author", "Jordan M. Slade"), "detected_topic": fields.get("content theme", kind), "puzzle_count": int(fields.get("puzzle count", "0") or 0), "difficulty_label": fields.get("difficulty", "Standard")}
            meta = build_metadata(source)
            meta.update({"book_id": book_id, "trim_size": "8.5x11", "language": "English", "publication_date": "", "isbn": "", "edition": "1", "categories": meta["ingram_subjects"], "production_status": "Complete package", "page_count": self._interior_pages(folder), "files": self._package_files(folder), "price": {"amazon": 11.99, "etsy": 6.99, "ingram": 12.99, "direct_print": 12.99, "direct_digital": 5.99, "barnes_noble": 12.99, "lulu": 12.99, "bookvault": 12.99}, "last_synced": datetime.now().isoformat(timespec="seconds")})
            build_master_package(folder, meta)
            self.db.upsert_book(book_id, key, meta, str(folder)); imported += 1
        self.db.prune_duplicate_unpublished_package_titles()
        return imported

    def recommended_books(self, limit: int = 6) -> list[dict]:
        """Return practical next steps from the user's own verified catalog.

        This intentionally does not claim live sales data.  It favors broad,
        evergreen topics, adequate puzzle counts, and books that have not
        already been fully created.  A completed package appears only after
        those next-to-create ideas, so the list stays useful at production time.
        """
        priorities = {
            "national park": 32, "garden": 30, "homestead": 29, "christmas": 29,
            "holiday": 27, "bible": 27, "space": 26, "planet": 25, "pet": 25,
            "cat": 24, "dog": 24, "travel": 23, "bird": 23, "nature": 22,
            "car": 22, "vehicle": 22, "school": 21, "vocabulary": 21,
            "history": 20, "ocean": 20, "food": 19, "sport": 19,
        }
        choices: list[dict] = []
        for book in self.db.list_books():
            meta = book["metadata"]
            if meta.get("production_status") not in {"Passed", "Complete package"}:
                continue
            files = meta.get("files") if isinstance(meta.get("files"), dict) else {}
            has_package = bool(files.get("print_interior") and files.get("print_cover") and Path(str(files["print_interior"])).is_file() and Path(str(files["print_cover"])).is_file())
            text = " ".join(str(meta.get(field) or "") for field in ("title", "subtitle", "theme", "series")).casefold()
            score = sum(weight for word, weight in priorities.items() if word in text)
            count = int(meta.get("puzzle_count") or 0)
            score += 12 if count >= 100 else 9 if count >= 48 else 0
            score += 4 if str(meta.get("difficulty") or "").casefold() in {"easy", "standard", "mixed"} else 0
            # Fresh ideas come first. A complete package is still useful as a
            # ready-to-prepare fallback after the new-book recommendations.
            score += 2 if not has_package else -10
            if score <= 0:
                continue
            topic = str(meta.get("theme") or "themed puzzles")
            reason_parts = ["broad evergreen topic"]
            if any(word in text for word in ("christmas", "holiday")):
                reason_parts = ["seasonal favorite with a clear gift angle"]
            elif any(word in text for word in ("national park", "travel", "garden", "space", "pet", "vocabulary")):
                reason_parts = ["strong series-friendly topic"]
            if count >= 100:
                reason_parts.append("100-puzzle edition")
            elif count >= 48:
                reason_parts.append(f"{count}-puzzle full book")
            choices.append({"book": book, "score": score, "action": "Prepare package" if has_package else "Create book", "reason": " • ".join(reason_parts), "topic": topic, "puzzles": count})
        return sorted(choices, key=lambda item: (-item["score"], item["book"]["metadata"].get("title", "")))[:limit]

    def etsy_bundle_candidates(self) -> list[dict]:
        """Only offer completed books that Etsy can receive as buyer downloads."""
        return [book for book in self.db.list_books() if not eligible_book_error(book)]

    def create_etsy_bundle(self, title: str, book_ids: list[str], price: float) -> tuple[Path, dict]:
        books = [book for item in book_ids if (book := self.db.get_book(item))]
        if len(books) != len(book_ids):
            raise ValueError("One or more selected books are no longer in the catalog. Sync the catalog and try again.")
        folder, details = build_etsy_bundle(self.output, title, books, price)
        bundle_id = self._id("etsy-bundle:" + str(folder.resolve()))
        self.db.save_bundle(bundle_id, title, book_ids, details, str(folder))
        return folder, details

    @staticmethod
    def _publication_key(source: dict) -> str:
        """A buyer-facing identity, not a filename, is the manager's unique book key."""
        parts = (str(source.get("title") or ""), str(source.get("subtitle") or ""), str(source.get("author") or "Jordan M. Slade"))
        return "|".join("".join(char for char in part.casefold() if char.isalnum()) for part in parts)

    @staticmethod
    def _canonical_score(candidate: tuple[Path, Path | None]) -> tuple[int, int, float]:
        path, package = candidate
        # Prefer a valid completed package, then a clean non-timestamped source,
        # then the newest backup. All other copies stay safely on disk.
        stamped = bool(__import__("re").search(r"_20\d{6}_\d{6}$", path.stem))
        try: modified = path.stat().st_mtime
        except OSError: modified = 0.0
        return (1 if package else 0, 0 if stamped else 1, modified)

    def _find_package_for_title(self, title: str) -> Path | None:
        """Support older packages and moved folders without changing the original output."""
        wanted = "".join(char for char in title.casefold() if char.isalnum())
        matches: list[Path] = []
        for interior in self.output.rglob("interior.pdf"):
            folder = interior.parent
            try:
                listing = (folder / "KDP_LISTING_KIT.txt").read_text(encoding="utf-8-sig")
            except OSError:
                listing = ""
            name = "".join(char for char in folder.name.casefold() if char.isalnum())
            if title.casefold() in listing.casefold() or wanted in name or name in wanted:
                if (folder / "kdp_full_wrap.pdf").is_file(): matches.append(folder)
        return max(matches, key=lambda item: item.stat().st_mtime) if matches else None

    @staticmethod
    def _pages_from_manifest(folder: Path) -> int:
        try: return int(json.loads((folder / "PACKAGE_SOURCE_RECORD.json").read_text(encoding="utf-8")).get("interior_pages") or 0)
        except (OSError, ValueError, json.JSONDecodeError): return 0

    @staticmethod
    def _interior_pages(folder: Path) -> int:
        try:
            from pypdf import PdfReader
            return len(PdfReader(str(folder / "interior.pdf")).pages)
        except Exception:
            return 0

    @staticmethod
    def _estimate_wordsearch_pages(source: dict) -> int:
        """Mirrors the current word-search interior layout without importing the GUI."""
        puzzles = source.get("puzzles") if isinstance(source.get("puzzles"), list) else []
        count = len(puzzles)
        signature = source.get("signature_edition") if isinstance(source.get("signature_edition"), dict) else {}
        signature_extra = (count + 59) // 60 + 1 if signature.get("enabled") else 0
        if signature.get("fact_cards"): signature_extra += 1
        details = len(source.get("signature_details") or [])
        raw = 4 + details + signature_extra + count + 1 + ((count + 1) // 2) + 2 + (1 if source.get("also_from") else 0)
        return raw if raw % 2 == 0 else raw + 1

    @staticmethod
    def _package_files(folder: Path) -> dict:
        return {"print_interior": str(folder / "interior.pdf") if (folder / "interior.pdf").exists() else "", "print_cover": str(folder / "kdp_full_wrap.pdf") if (folder / "kdp_full_wrap.pdf").exists() else "", "front_cover": str(folder / "front_cover.png") if (folder / "front_cover.png").exists() else "", "printable_pdf": ""}

    def prepare(self, book_id: str, marketplace: str) -> tuple[Path, list[str]]:
        book = self.db.get_book(book_id)
        if not book: raise ValueError("Book was not found in the Publishing Manager.")
        publisher = PUBLISHERS[marketplace]; issues = publisher.validate(book)
        root = Path(book.get("package_path") or self.output / book["book_id"])
        prior = self.db.marketplace_records(book_id)[marketplace]
        if prior["status"] in PROTECTED_STATUSES:
            # The user already confirmed an upload/live listing. Re-preparing
            # must never downgrade that record or erase its ASIN/link.
            return root, [f"{publisher.label} is already recorded as {prior['status']}. Nothing was changed and your listing details are safe."]
        if issues:
            self.db.transition_status(book_id, marketplace, "Needs Review", source="prepare")
            return Path(book.get("package_path") or self.output), issues
        try:
            folder_name = {"amazon": "kdp", "barnes_noble": "barnes_noble"}.get(marketplace, marketplace)
            target = root / folder_name
            publisher.prepare(book, target)
        except Exception as exc:
            # Keep the human-readable reason with the record so errors survive
            # the restart; prepare_many's fallback write is deduplicated.
            self.db.transition_status(book_id, marketplace, "Error", source="prepare", error_message=str(exc))
            raise
        self.db.transition_status(book_id, marketplace, "Ready", source="prepare")
        return target, []

    def prepare_many(self, book_ids: list[str], marketplaces: list[str]) -> list[tuple[str, str, str]]:
        report = []
        for book_id in book_ids:
            for marketplace in marketplaces:
                prior = self.db.marketplace_records(book_id)[marketplace]
                if prior["status"] in PROTECTED_STATUSES:
                    report.append((book_id, marketplace, f"Already {prior['status']}"))
                    continue
                try:
                    _folder, issues = self.prepare(book_id, marketplace); report.append((book_id, marketplace, "Needs Review" if issues else "Ready"))
                except Exception as exc:
                    self.db.transition_status(book_id, marketplace, "Error", source="prepare", error_message=str(exc))
                    report.append((book_id, marketplace, f"Error: {exc}"))
        return report

    def detect_local_marketplace_status(self) -> int:
        """Mark locally prepared handoffs as Ready, while never overwriting upload/live data."""
        updated = 0
        folder_names = {"amazon": "kdp", "barnes_noble": "barnes_noble"}
        for book in self.db.list_books():
            package = Path(str(book.get("package_path") or ""))
            if not package.is_dir():
                continue
            for marketplace in MARKETPLACES:
                target = package / folder_names.get(marketplace, marketplace)
                record = self.db.marketplace_records(book["book_id"])[marketplace]
                if target.is_dir() and record["status"] == "Not Prepared":
                    self.db.transition_status(book["book_id"], marketplace, "Ready", source="local_scan")
                    updated += 1
        return updated
