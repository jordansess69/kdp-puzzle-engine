"""Canonical, marketplace-neutral product model (Universal Publishing Foundation).

The ONE publishing system keeps the SQLite catalog authoritative.  This module
adds a domain-only representation built FROM that catalog data:

    Puzzle Project / Catalog Record
            |
        MasterProduct  <-- this module (in-memory, no persistence)
            |
    Marketplace Adapter / Mapper
            |
    Remote Listing OR Export Package

Design rules:

- Field names are marketplace-NEUTRAL: ``keywords``, ``tags``, ``price``.
  Never ``etsy_tags``/``kdp_keywords``/``shopify_product_type``; those source
  names may only appear inside factories/mappers where the translation happens.
- Incomplete products are valid.  Every field has a default so any channel can
  receive whatever metadata actually exists today.
- No secrets ever belong here; credentials stay adapter-specific.
- Artifacts live in a generic collection (:class:`ProductArtifact`) instead of
  per-marketplace fields, without changing how files are generated.

Nothing in this module performs I/O except the opt-in ``sha256_checksum``
helper and artifact size inspection done by the factory layer.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from integrations.validation import ValidationIssue, ValidationResult, ValidationSeverity


class ArtifactPurpose(str, Enum):
    """Why an artifact exists, independent of any marketplace."""

    PRINT_INTERIOR = "print_interior"
    PRINT_COVER = "print_cover"
    DIGITAL_PDF = "digital_pdf"
    EPUB = "epub"
    THUMBNAIL = "thumbnail"
    LISTING_IMAGE = "listing_image"
    PREVIEW = "preview"
    SOURCE_ARCHIVE = "source_archive"
    METADATA_EXPORT = "metadata_export"


#: Suffix -> MIME type for file kinds this project actually produces.
_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".epub": "application/epub+zip",
    ".zip": "application/zip",
    ".json": "application/json",
    ".txt": "text/plain",
}


def guess_media_type(path: str) -> str:
    """Best-effort MIME type from a filename suffix ('' when unknown)."""
    suffix = "." + str(path).rsplit(".", 1)[-1].lower() if "." in str(path) else ""
    return _MEDIA_TYPES.get(suffix, "")


def sha256_checksum(path: str) -> str:
    """SHA-256 hex digest of a file; callers opt in because large PDFs cost time."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ProductArtifact:
    """One generated file described generically.

    ``checksum``/``file_size`` are optional because hashing or even stat-ing
    large PDFs on every UI refresh would be wasteful; the export layer opts in
    when a durable record is needed.
    """

    path: str
    purpose: ArtifactPurpose
    media_type: str = ""
    file_size: Optional[int] = None
    checksum: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    position: Optional[int] = None
    label: str = ""

    def __post_init__(self):
        if not isinstance(self.purpose, ArtifactPurpose):
            # Accept raw strings so persisted JSON round-trips without ceremony.
            object.__setattr__(self, "purpose", ArtifactPurpose(str(self.purpose)))
        if not self.media_type:
            object.__setattr__(self, "media_type", guess_media_type(self.path))


@dataclass(frozen=True)
class MasterProduct:
    """Marketplace-neutral description of one sellable product.

    All fields default empty/None so incomplete products remain constructible;
    adapters decide what their channel actually requires via validation.
    """

    # -- identity -----------------------------------------------------------
    internal_product_id: str = ""
    sku: str = ""
    revision: int = 1

    # -- core metadata -------------------------------------------------------
    title: str = ""
    subtitle: str = ""
    series: str = ""
    description: str = ""
    short_description: str = ""
    author: str = ""
    brand: str = ""
    language: str = ""
    product_type: str = ""
    target_audience: str = ""
    age_range: str = ""
    categories: Tuple[str, ...] = ()
    keywords: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()

    # -- commercial ----------------------------------------------------------
    price: Optional[float] = None
    currency: str = "USD"
    publication_date: str = ""
    copyright_notice: str = ""

    # -- print ---------------------------------------------------------------
    isbn: str = ""
    page_count: int = 0
    trim_size: str = ""
    bleed_inches: Optional[float] = None

    # -- source / traceability ------------------------------------------------
    source_reference: str = ""
    generated_at: str = ""
    ai_disclosure: str = ""

    # -- artifacts -------------------------------------------------------------
    artifacts: Tuple[ProductArtifact, ...] = field(default_factory=tuple)

    # -- artifact helpers -------------------------------------------------------

    def artifacts_for(self, purpose: ArtifactPurpose) -> Tuple[ProductArtifact, ...]:
        """All artifacts with *purpose*, ordered by position then input order."""
        matches = [item for item in self.artifacts if item.purpose == purpose]
        matches.sort(key=lambda item: (item.position is None, item.position or 0))
        return tuple(matches)

    def first_artifact(self, purpose: ArtifactPurpose) -> Optional[ProductArtifact]:
        matches = self.artifacts_for(purpose)
        return matches[0] if matches else None

    def has_artifact(self, purpose: ArtifactPurpose) -> bool:
        return bool(self.artifacts_for(purpose))

    @property
    def is_digital_ready(self) -> bool:
        """True when a digital-buyer file is present on disk."""
        artifact = self.first_artifact(ArtifactPurpose.DIGITAL_PDF)
        return bool(artifact and artifact.path)


# ---------------------------------------------------------------------------
# Canonical validation (channel rules belong to adapters/mappers, never here)
# ---------------------------------------------------------------------------

def validate_canonical(product: MasterProduct) -> ValidationResult:
    """Channel-independent sanity checks every marketplace agrees on."""
    issues = []
    if not str(product.internal_product_id).strip():
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR, code="missing_product_id",
            message="The product has no internal id.",
            field_ref="internal_product_id",
            suggested_fix="Build the product from a catalog record with MasterProductFactory.",
        ))
    if not str(product.title).strip():
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR, code="missing_title",
            message="The product has no title.",
            field_ref="title",
            suggested_fix="Set a title in Publishing Manager before preparing any channel.",
        ))
    if not product.artifacts:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING, code="no_artifacts",
            message="No generated files are attached to this product yet.",
            suggested_fix="Create the book package so print/digital files exist.",
        ))
    if product.price is None:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO, code="missing_price",
            message="No price was supplied; each channel will apply its own default.",
            field_ref="price",
        ))
    return ValidationResult(issues=tuple(issues))
