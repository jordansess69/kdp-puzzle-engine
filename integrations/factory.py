"""MasterProductFactory: bridge existing catalog data -> MasterProduct.

The SQLite catalog (publishing/database.py) and the metadata engine
(publishing/metadata_service.py) stay THE authoritative source of truth.  This
factory is a pure TRANSLATOR: it reads an existing book record dict (the shape
returned by ``PublishingDatabase.get_book`` / ``list_books``) plus the files
that already exist on disk, and never regenerates PDFs, covers or puzzle
content.

Source field names such as ``etsy_tags`` / ``amazon_keywords`` appear ONLY
here, where the marketplace-specific -> neutral translation happens; the
MasterProduct itself carries neutral names (tags/keywords).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from integrations.product import (
    ArtifactPurpose,
    ProductArtifact,
    MasterProduct,
    guess_media_type,
)

# metadata["files"] keys -> canonical artifact purposes.
_FILE_KEY_PURPOSES = {
    "print_interior": ArtifactPurpose.PRINT_INTERIOR,
    "print_cover": ArtifactPurpose.PRINT_COVER,
    "front_cover": ArtifactPurpose.THUMBNAIL,
}

# Standard KDP bleed for this project's interiors; kept in step with the
# print pipeline (0.125") without importing any generation code.
DEFAULT_BLEED_INCHES = 0.125


def _existing(path_value) -> str:
    """Return the path when it points at a real file, else ''."""
    candidate = str(path_value or "").strip()
    return candidate if candidate and os.path.isfile(candidate) else ""


def _artifact(path: str, purpose: ArtifactPurpose, position=None, label: str = "") -> ProductArtifact:
    size = None
    try:
        size = os.path.getsize(path)
    except OSError:
        pass
    return ProductArtifact(path=path, purpose=purpose, media_type=guess_media_type(path),
                           file_size=size, position=position, label=label)


def collect_artifacts(book: dict) -> tuple:
    """Describe already-generated files (catalog files map + prepared folders).

    Never creates, moves or regenerates anything; missing files are simply
    omitted so the product truthfully reflects what exists right now.
    """
    meta = book.get("metadata") or {}
    files = meta.get("files") if isinstance(meta.get("files"), dict) else {}
    artifacts = []
    for key, purpose in _FILE_KEY_PURPOSES.items():
        found = _existing(files.get(key))
        if found:
            artifacts.append(_artifact(found, purpose))
    package = str(book.get("package_path") or "")
    if package and os.path.isdir(package):
        prepared = Path(package) / "etsy"
        digital = _existing(prepared / "printable.pdf")
        if digital:
            artifacts.append(_artifact(digital, ArtifactPurpose.DIGITAL_PDF, label="Buyer download"))
        listing_image = _existing(prepared / "thumbnail.jpg")
        if listing_image:
            artifacts.append(_artifact(listing_image, ArtifactPurpose.LISTING_IMAGE,
                                       position=1, label="Primary listing image"))
        preview_dir = prepared if prepared.is_dir() else Path(package)
        previews = sorted(
            name for name in os.listdir(preview_dir)
            if name.startswith("preview-") and name.lower().endswith((".jpg", ".jpeg", ".png"))
        ) if preview_dir.is_dir() else []
        for index, name in enumerate(previews, start=1):
            artifacts.append(_artifact(str(preview_dir / name), ArtifactPurpose.PREVIEW, position=index))
    return tuple(artifacts)


class MasterProductFactory:
    """Builds MasterProduct objects from authoritative application data."""

    #: Which channel price becomes the product's default commercial price until
    #: per-channel pricing lands in mappers (mappers may override per channel).
    DEFAULT_PRICE_CHANNEL = "etsy"

    @classmethod
    def from_book_record(cls, book: dict, *, price_channel: str | None = None,
                         generated_at: str | None = None) -> MasterProduct:
        if not isinstance(book, dict) or not book.get("book_id"):
            raise ValueError("from_book_record needs a catalog book record with a book_id.")
        meta = book.get("metadata") or {}
        prices = meta.get("price") if isinstance(meta.get("price"), dict) else {}
        channel = price_channel or cls.DEFAULT_PRICE_CHANNEL
        raw_price = prices.get(channel)
        try:
            price = float(raw_price) if raw_price not in (None, "") else None
        except (TypeError, ValueError):
            price = None
        tags = list(meta.get("etsy_tags") or ()) or list(meta.get("website_tags") or ())
        keywords = list(meta.get("amazon_keywords") or ())
        author = str(meta.get("author") or "")
        year = str(meta.get("copyright_year") or "")
        copyright_notice = f"© {year} {author}".strip() if (year or author) else ""
        return MasterProduct(
            internal_product_id=str(book["book_id"]),
            sku=str(meta.get("sku") or book["book_id"]),
            revision=int(meta.get("edition") or 1),
            title=str(meta.get("title") or ""),
            subtitle=str(meta.get("subtitle") or ""),
            series=str(meta.get("series") or ""),
            description=str(meta.get("description") or ""),
            short_description=str(meta.get("short_description") or ""),
            author=author,
            brand=str(meta.get("imprint") or meta.get("brand") or ""),
            language=str(meta.get("language") or ""),
            product_type="puzzle_book",
            target_audience=str(meta.get("audience") or ""),
            age_range=str(meta.get("age_range") or ""),
            categories=tuple(str(c) for c in (meta.get("categories") or ())),
            keywords=tuple(str(k) for k in keywords),
            tags=tuple(str(t) for t in tags),
            price=price,
            currency="USD",
            publication_date=str(meta.get("publication_date") or ""),
            copyright_notice=copyright_notice,
            isbn=str(meta.get("isbn") or ""),
            page_count=int(meta.get("page_count") or 0),
            trim_size=str(meta.get("trim_size") or ""),
            bleed_inches=DEFAULT_BLEED_INCHES,
            source_reference=str(book.get("source_key") or ""),
            generated_at=generated_at or datetime.now().isoformat(timespec="seconds"),
            ai_disclosure=str(meta.get("ai_disclosure") or ""),
            artifacts=collect_artifacts(book),
        )
