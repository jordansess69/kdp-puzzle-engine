"""MasterProductFactory + Etsy mapper tests: translation-layer correctness.

The critical guarantee here is OUTPUT PARITY: the universal path
(book record -> MasterProduct -> EtsyListingMapper -> form fields) produces
byte-identical createDraftListing payloads to the committed
``build_draft_fields`` path for equivalent inputs, so the existing draft
automation could adopt the mapper later without any behavior change.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.etsy.draft_service import build_draft_fields
from integrations.etsy.mapper import (
    ETSY_MAX_TAGS,
    EtsyListingMapper,
)
from integrations.factory import MasterProductFactory
from integrations.product import ArtifactPurpose, ProductArtifact, MasterProduct
from integrations.validation import ValidationSeverity


BOOK_ID = "b1a2c3d4e5f6"


def make_book(tmp_path, **meta_overrides) -> dict:
    """A realistic PublishingDatabase.get_book-shaped record with real files."""
    package = tmp_path / "package"
    etsy_dir = package / "etsy"
    etsy_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "print_interior": package / "interior.pdf",
        "print_cover": package / "kdp_full_wrap.pdf",
        "front_cover": package / "front_cover.png",
    }
    for name, path in {**files, "digital": etsy_dir / "printable.pdf",
                       "thumb": etsy_dir / "thumbnail.jpg",
                       "prev1": etsy_dir / "preview-a.png",
                       "prev2": etsy_dir / "preview-b.jpg"}.items():
        path.write_bytes(b"content-" + name.encode())
    metadata = {
        "title": "Garden Word Search", "subtitle": "", "author": "Jordan M. Slade",
        "description": "Relaxing garden puzzles.", "short_description": "60 puzzles.",
        "audience": "Adults and teens", "language": "English", "isbn": "",
        "page_count": 64, "trim_size": "8.5x11", "edition": "1",
        "categories": ["Games & Activities / Word & Word Search"],
        "amazon_keywords": ["garden word search", "garden puzzle book"],
        "website_tags": ["garden", "word search"],
        "etsy_tags": ["garden", "word search", "printable puzzle"],
        "price": {"amazon": 11.99, "etsy": 6.99},
        "files": {key: str(path) for key, path in files.items()} | {"printable_pdf": ""},
    }
    metadata.update(meta_overrides)
    return {"book_id": BOOK_ID, "source_key": r"C:\themes\garden.json",
            "metadata": metadata, "package_path": str(package),
            "created_at": "2026-08-01T00:00:00", "updated_at": "2026-08-22T00:00:00"}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestMasterProductFactory:
    def test_builds_complete_product_from_book_record(self, tmp_path):
        product = MasterProductFactory.from_book_record(make_book(tmp_path))
        assert product.internal_product_id == BOOK_ID
        assert product.title == "Garden Word Search"
        assert product.author == "Jordan M. Slade"
        assert product.product_type == "puzzle_book"
        assert product.language == "English"
        assert product.price == 6.99 and product.currency == "USD"
        assert product.page_count == 64 and product.trim_size == "8.5x11"
        assert product.revision == 1
        assert product.tags == ("garden", "word search", "printable puzzle")
        assert product.keywords == ("garden word search", "garden puzzle book")
        assert product.categories == ("Games & Activities / Word & Word Search",)
        assert product.source_reference.endswith("garden.json")
        assert product.generated_at

    def test_artifacts_reflect_real_files_with_purpose_and_order(self, tmp_path):
        product = MasterProductFactory.from_book_record(make_book(tmp_path))
        purposes = {item.purpose for item in product.artifacts}
        assert purposes == {
            ArtifactPurpose.PRINT_INTERIOR, ArtifactPurpose.PRINT_COVER,
            ArtifactPurpose.THUMBNAIL, ArtifactPurpose.DIGITAL_PDF,
            ArtifactPurpose.LISTING_IMAGE, ArtifactPurpose.PREVIEW,
        }
        digital = product.first_artifact(ArtifactPurpose.DIGITAL_PDF)
        assert digital.path.endswith("printable.pdf")
        assert digital.file_size > 0 and digital.media_type == "application/pdf"
        previews = product.artifacts_for(ArtifactPurpose.PREVIEW)
        assert [item.position for item in previews] == [1, 2]
        listing_image = product.first_artifact(ArtifactPurpose.LISTING_IMAGE)
        assert listing_image.position == 1
        assert product.is_digital_ready

    def test_missing_files_are_omitted_not_invented(self, tmp_path):
        book = make_book(tmp_path)
        book["package_path"] = ""          # no prepared folders at all
        for key in ("print_interior", "front_cover"):
            book["metadata"]["files"][key] = ""
        product = MasterProductFactory.from_book_record(book)
        purposes = {item.purpose for item in product.artifacts}
        assert purposes == {ArtifactPurpose.PRINT_COVER}   # only file that still exists
        assert not product.is_digital_ready

    def test_price_channel_selection_and_garbage_tolerance(self, tmp_path):
        book = make_book(tmp_path)
        amazon_product = MasterProductFactory.from_book_record(
            book, price_channel="amazon")
        assert amazon_product.price == 11.99
        book["metadata"]["price"]["ingram"] = "not-a-number"
        broken = MasterProductFactory.from_book_record(book, price_channel="ingram")
        assert broken.price is None
        absent = MasterProductFactory.from_book_record(book, price_channel="lulu")
        assert absent.price is None

    def test_tag_fallback_when_no_etsy_tags(self, tmp_path):
        book = make_book(tmp_path)
        book["metadata"]["etsy_tags"] = []
        product = MasterProductFactory.from_book_record(book)
        assert product.tags == ("garden", "word search")

    def test_requires_a_catalog_record(self):
        with pytest.raises(ValueError):
            MasterProductFactory.from_book_record({})
        with pytest.raises(ValueError):
            MasterProductFactory.from_book_record("not a dict")


# ---------------------------------------------------------------------------
# Etsy mapper: parity + marketplace-specific validation
# ---------------------------------------------------------------------------


METADATA_FOR_PARITY = {
    "title": "My emoji Book 🌊!!",
    "description": "  Waves of fun puzzles.  ",
    "etsy_tags": ["ocean animals", "word search", "printable puzzle", "ocean animals"],
}


def _product_for_parity(tmp_path, price=7.49) -> MasterProduct:
    printable = tmp_path / "printable.pdf"; printable.write_bytes(b"%PDF")
    return MasterProduct(
        internal_product_id=BOOK_ID,
        title=METADATA_FOR_PARITY["title"],
        description=METADATA_FOR_PARITY["description"],
        price=price,
        tags=tuple(METADATA_FOR_PARITY["etsy_tags"]),
        artifacts=(ProductArtifact(path=str(printable), purpose=ArtifactPurpose.DIGITAL_PDF),),
    )


class TestEtsyMapperParity:
    def test_form_fields_match_committed_draft_service_output(self, tmp_path):
        product = _product_for_parity(tmp_path)
        listing = EtsyListingMapper().to_listing_data(product, taxonomy_id=161)
        fields = listing.to_form_fields()
        expected = build_draft_fields(METADATA_FOR_PARITY, 161, 7.49)
        assert fields == expected
        # The emoji/charset rules come from the SAME sanitizer, so both paths
        # agree even on hostile titles.
        assert fields["title"] == "My emoji Book !!"

    def test_digital_listing_shape_is_immutable_safety_surface(self, tmp_path):
        product = _product_for_parity(tmp_path)
        listing = EtsyListingMapper().to_listing_data(product, taxonomy_id=161)
        assert listing.listing_type == "download"
        assert listing.quantity == "999"
        assert listing.who_made == "i_did" and listing.when_made == "made_to_order"
        assert listing.is_supply == "false"
        payload = repr(listing) + str(listing.to_form_fields())
        for banned in ("activate", "publish", "state=active", "listings_d"):
            assert banned not in payload.lower()

    def test_price_override_beats_product_price(self, tmp_path):
        product = _product_for_parity(tmp_path, price=6.99)
        listing = EtsyListingMapper().to_listing_data(product, taxonomy_id=9, price_override=4.5)
        assert listing.price == "4.50"


class TestEtsyValidationSeparation:
    def test_channel_ready_product_passes(self, tmp_path):
        thumb = tmp_path / "thumbnail.jpg"; thumb.write_bytes(b"\xff\xd8")
        product = MasterProduct(
            internal_product_id="p1",
            title="Ocean Word Search", description="Fun puzzles.", price=6.99,
            tags=("ocean",), artifacts=(
                ProductArtifact(path=str(thumb), purpose=ArtifactPurpose.LISTING_IMAGE),
                ProductArtifact(path=str(tmp_path / "printable.pdf"),
                                purpose=ArtifactPurpose.DIGITAL_PDF),
            ),
        )
        (tmp_path / "printable.pdf").write_bytes(b"%PDF")
        result = EtsyListingMapper().validate_for_etsy(product, taxonomy_id=161)
        assert result.valid and not result.warnings

    @pytest.mark.parametrize("code,changes,taxonomy", [
        ("etsy_title_required", {"title": "   🌊"}, 161),
        ("etsy_description_required", {"description": " "}, 161),
        ("etsy_taxonomy_required", {}, None),
        ("etsy_digital_file_required", {"artifacts": ()}, 161),
        ("etsy_price_required", {"price": None}, 161),
        ("etsy_price_below_minimum", {"price": 0.05}, 161),
    ])
    def test_marketplace_rules_are_errors(self, code, changes, taxonomy):
        product = dataclasses.replace(
            MasterProduct(internal_product_id="p", title="Great Title",
                          description="desc", price=6.99), **changes)
        result = EtsyListingMapper().validate_for_etsy(product, taxonomy_id=taxonomy)
        assert not result.valid
        assert code in {issue.code for issue in result.errors}

    def test_image_and_tag_rules_stay_advisory(self, tmp_path):
        printable = tmp_path / "printable.pdf"; printable.write_bytes(b"%PDF")
        long_tags = tuple(f"tag-number-{i:02d} that is far too long for etsy" for i in range(ETSY_MAX_TAGS + 3))
        product = MasterProduct(internal_product_id="p", title="Title",
                                description="desc", price=6.99, tags=long_tags,
                                artifacts=(ProductArtifact(
                                    path=str(printable), purpose=ArtifactPurpose.DIGITAL_PDF),))
        result = EtsyListingMapper().validate_for_etsy(product, taxonomy_id=5)
        assert result.valid                      # warnings/info never block
        codes = {issue.code for issue in result.warnings} | {issue.code for issue in result.infos}
        assert "etsy_image_recommended" in codes and "etsy_tags_adjusted" in codes

    def test_canonical_and_marketplace_validation_do_not_leak_into_each_other(self, tmp_path):
        product = _product_for_parity(tmp_path)
        canonical = __import__("integrations.product", fromlist=["validate_canonical"]).validate_canonical(product)
        assert canonical.valid                     # fine as a neutral product
        etsy_result = EtsyListingMapper().validate_for_etsy(product, taxonomy_id=None)
        assert not etsy_result.valid               # but not ready for THIS channel
        merged = __import__("integrations.validation", fromlist=["ValidationResult"]).ValidationResult.aggregate(canonical, etsy_result)
        assert len(merged.errors) >= 1
