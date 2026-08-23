import json
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from publishing.manager import PublishingService
from publishing.marketplaces import PUBLISHERS
from publishing.master_package import build_master_package
from theme_health import read_theme_health, record_theme_health


def _theme(tmp_path: Path) -> Path:
    path = tmp_path / "sample.json"
    path.write_text(json.dumps({"title": "Garden Word Search", "subtitle": "48 calming puzzles", "author": "Jordan M. Slade", "series": "Garden Collection", "detected_topic": "Gardening", "puzzles": [{"words": ["ROSE"]}] * 48}), encoding="utf-8")
    return path


def test_sync_creates_one_master_record_and_preserves_locked_metadata(tmp_path):
    service = PublishingService(tmp_path)
    theme = _theme(tmp_path)
    book_id = service.sync_theme(theme)
    book = service.db.get_book(book_id)
    assert book["metadata"]["title"] == "Garden Word Search"
    assert book["metadata"]["page_count"] > 0
    book["metadata"]["title"] = "Locked Garden Title"
    service.db.save_metadata(book_id, book["metadata"], locked=True)
    theme.write_text(theme.read_text(encoding="utf-8").replace("Garden Word Search", "Changed Title"), encoding="utf-8")
    service.sync_theme(theme)
    assert service.db.get_book(book_id)["metadata"]["title"] == "Locked Garden Title"


def test_isbn_cannot_be_assigned_to_two_different_books(tmp_path):
    service = PublishingService(tmp_path)
    first = service.sync_theme(_theme(tmp_path))
    other = tmp_path / "other.json"; other.write_text(json.dumps({"title": "Other", "author": "Jordan M. Slade", "puzzles": []}), encoding="utf-8")
    second = service.sync_theme(other)
    service.db.assign_isbn("978-1-234-56789-0", first, "Garden Word Search", "User-owned ISBN")
    try:
        service.db.assign_isbn("9781234567890", second, "Other", "User-owned ISBN")
    except ValueError:
        pass
    else:
        raise AssertionError("ISBN duplicate should have been blocked")


def test_prepare_returns_needs_review_without_required_print_files(tmp_path):
    service = PublishingService(tmp_path)
    book_id = service.sync_theme(_theme(tmp_path))
    _folder, issues = service.prepare(book_id, "amazon")
    assert issues and service.db.statuses(book_id)["amazon"] == "Needs Review"


def test_upload_status_keeps_confirmed_link_and_local_scan_never_overwrites_it(tmp_path):
    service = PublishingService(tmp_path)
    package = tmp_path / "finished"; (package / "kdp").mkdir(parents=True)
    book_id = service.sync_theme(_theme(tmp_path), package)
    assert service.detect_local_marketplace_status() == 1
    assert service.db.statuses(book_id)["amazon"] == "Ready"
    service.db.update_marketplace_record(book_id, "amazon", "Published", "B0TEST123", "https://www.amazon.com/dp/B0TEST123")
    assert service.detect_local_marketplace_status() == 0
    record = service.db.marketplace_records(book_id)["amazon"]
    assert record["status"] == "Published"
    assert record["external_id"] == "B0TEST123"
    assert record["url"].endswith("B0TEST123")


def test_catalog_sync_hides_timestamped_duplicate_theme_copies(tmp_path):
    service = PublishingService(tmp_path)
    first = _theme(tmp_path)
    duplicate = tmp_path / "garden_20260822_174014.json"
    duplicate.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
    assert service.sync_catalog([first, duplicate], {}) == 1
    assert len(service.db.list_books()) == 1


def test_recommendations_prioritize_a_ready_to_create_evergreen_book(tmp_path):
    service = PublishingService(tmp_path)
    theme = _theme(tmp_path)
    record_theme_health(tmp_path / "data" / "theme_readiness_cache.json", theme, [], [])
    service.sync_theme(theme)
    recommendations = service.recommended_books()
    assert recommendations
    assert recommendations[0]["book"]["metadata"]["title"] == "Garden Word Search"
    assert recommendations[0]["action"] == "Create book"
    assert "series-friendly" in recommendations[0]["reason"]


def test_changed_theme_cannot_reuse_an_old_passed_content_check(tmp_path):
    theme = _theme(tmp_path); cache = tmp_path / "data" / "theme_readiness_cache.json"
    record_theme_health(cache, theme, [], [])
    assert read_theme_health(cache, theme)["status"] == "Passed"
    theme.write_text(theme.read_text(encoding="utf-8").replace("Garden Word Search", "Changed Garden Word Search"), encoding="utf-8")
    assert read_theme_health(cache, theme) is None


def test_unchecked_theme_is_not_recommended_for_production(tmp_path):
    service = PublishingService(tmp_path)
    service.sync_theme(_theme(tmp_path))
    assert not service.recommended_books()


def test_kdp_validation_rejects_stale_file_paths(tmp_path):
    service = PublishingService(tmp_path)
    book_id = service.sync_theme(_theme(tmp_path))
    book = service.db.get_book(book_id)
    book["metadata"]["files"] = {"print_interior": str(tmp_path / "missing-interior.pdf"), "print_cover": str(tmp_path / "missing-cover.pdf")}
    assert "interior PDF" in " ".join(PUBLISHERS["amazon"].validate(book))
    assert "cover PDF" in " ".join(PUBLISHERS["amazon"].validate(book))


def test_master_release_package_separates_platform_handoffs(tmp_path):
    (tmp_path / "interior.pdf").write_bytes(b"interior")
    (tmp_path / "kdp_full_wrap.pdf").write_bytes(b"cover")
    (tmp_path / "front_cover.png").write_bytes(b"front")
    master = build_master_package(tmp_path, {"title": "Garden Word Search", "author": "Jordan M. Slade", "trim_size": "8.5x11", "page_count": 100})
    assert master and (master / "01_KDP_UPLOAD" / "interior.pdf").is_file()
    assert (master / "02_ETSY_DIGITAL" / "digital_download.pdf").is_file()
    assert (master / "04_INGRAMSPARK" / "BUILD_PLATFORM_COVER_FIRST.txt").is_file()


def test_etsy_bundle_creates_buyer_download_and_catalog_record(tmp_path):
    service = PublishingService(tmp_path)
    ids = []
    for number in (1, 2):
        package = tmp_path / f"package_{number}"; package.mkdir()
        for name in ("interior.pdf", "kdp_full_wrap.pdf"):
            (package / name).write_bytes(f"{name}-{number}".encode())
        Image.new("RGB", (100, 150), (30, 120, 100)).save(package / "front_cover.png")
        theme = tmp_path / f"theme_{number}.json"
        theme.write_text(json.dumps({"title": f"Garden Book {number}", "author": "Jordan M. Slade", "detected_topic": "Gardening", "puzzles": [{"words": ["ROSE"]}] * 48}), encoding="utf-8")
        ids.append(service.sync_theme(theme, package))
    folder, details = service.create_etsy_bundle("Garden Puzzle Pack", ids, 12.99)
    assert (folder / "01_ETSY_UPLOAD_FILES").is_dir()
    assert (folder / "ETSY_LISTING_KIT.txt").is_file()
    assert details["upload_files"]
    assert service.db.list_bundles()[0]["title"] == "Garden Puzzle Pack"
