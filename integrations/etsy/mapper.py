"""Etsy listing mapper: MasterProduct -> Etsy-shaped data (reference adapter).

This module demonstrates the mapper layer of the Universal Publishing
Foundation using the ONE active marketplace.  It owns Etsy-specific rules
(title charset/length, tag count/length, digital type, taxonomy) while the
canonical model stays clean.

Compatibility rule: :meth:`EtsyListingData.to_form_fields` produces EXACTLY
the same createDraftListing payload as the committed
``integrations.etsy.draft_service.build_draft_fields`` for equivalent inputs
(verified by tests).  The draft automation keeps working untouched; this
mapper is the path future universal adapters will call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from integrations.product import ArtifactPurpose, MasterProduct
from integrations.validation import ValidationIssue, ValidationResult, ValidationSeverity

# Reuse the committed sanitizers - one implementation of Etsy's rules only.
from integrations.etsy.draft_service import sanitize_tags, sanitize_title

ETSY_TITLE_MAX_CHARS = 140
ETSY_TAG_MAX_CHARS = 20
ETSY_MAX_TAGS = 13
ETSY_MIN_PRICE = 0.20

WHO_MADE = "i_did"
WHEN_MADE = "made_to_order"
LISTING_TYPE_DIGITAL = "download"
DIGITAL_QUANTITY = "999"


@dataclass(frozen=True)
class EtsyListingData:
    """Etsy-shaped listing description produced by :class:`EtsyListingMapper`."""

    title: str = ""
    description: str = ""
    price: str = ""                    # Etsy wants a plain decimal string
    quantity: str = DIGITAL_QUANTITY
    who_made: str = WHO_MADE
    when_made: str = WHEN_MADE
    listing_type: str = LISTING_TYPE_DIGITAL
    is_supply: str = "false"
    taxonomy_id: Optional[int] = None
    tags: Tuple[str, ...] = ()
    materials: Tuple[str, ...] = ()

    def to_form_fields(self) -> dict:
        """The exact createDraftListing form body (same keys as build_draft_fields)."""
        fields = {
            "quantity": self.quantity,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "who_made": self.who_made,
            "when_made": self.when_made,
            "type": self.listing_type,
            "is_supply": self.is_supply,
        }
        if self.taxonomy_id is not None:
            fields["taxonomy_id"] = str(int(self.taxonomy_id))
        if self.tags:
            fields["tags"] = ",".join(self.tags)
        return fields


class EtsyListingMapper:
    """Translate a canonical product into Etsy's listing shape."""

    def to_listing_data(self, product: MasterProduct, *, taxonomy_id: Optional[int] = None,
                        price_override: Optional[float] = None) -> EtsyListingData:
        """Apply Etsy rules to *product*; raises nothing, reports via validation."""
        raw_price = price_override if price_override is not None else product.price
        try:
            price_value = float(raw_price)
        except (TypeError, ValueError):
            price_value = 0.0
        return EtsyListingData(
            title=sanitize_title(product.title),
            description=str(product.description or "").strip(),
            price=f"{price_value:.2f}",
            taxonomy_id=int(taxonomy_id) if taxonomy_id is not None else None,
            tags=tuple(sanitize_tags(list(product.tags))),
        )

    def validate_for_etsy(self, product: MasterProduct, *,
                          taxonomy_id: Optional[int] = None) -> ValidationResult:
        """Marketplace-specific pre-flight (canonical checks live elsewhere)."""
        issues: List[ValidationIssue] = []
        if not sanitize_title(product.title):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR, code="etsy_title_required",
                message="A listing title with at least one usable character is required.",
                field_ref="title",
                suggested_fix="Add a descriptive title in Publishing Manager.",
            ))
        if not str(product.description or "").strip():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR, code="etsy_description_required",
                message="An Etsy listing needs a description.",
                field_ref="description",
            ))
        if taxonomy_id is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR, code="etsy_taxonomy_required",
                message="An Etsy category (taxonomy id) must be chosen before creating a draft.",
                suggested_fix="Connect Etsy so the app can resolve the Books category automatically.",
            ))
        if not product.has_artifact(ArtifactPurpose.DIGITAL_PDF):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR, code="etsy_digital_file_required",
                message="Etsy digital listings need at least one buyer-ready file; click Prepare Etsy first.",
                artifact_ref=ArtifactPurpose.DIGITAL_PDF.value,
            ))
        if not product.has_artifact(ArtifactPurpose.LISTING_IMAGE) and not product.has_artifact(ArtifactPurpose.THUMBNAIL):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING, code="etsy_image_recommended",
                message="At least one listing image is expected; drafts without images sell poorly.",
                suggested_fix="Prepare Etsy so thumbnail.jpg exists in the prepared folder.",
            ))
        price = product.price
        if price is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR, code="etsy_price_required",
                message="A price is required before an Etsy draft can be created.",
                field_ref="price",
            ))
        elif float(price) < ETSY_MIN_PRICE:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR, code="etsy_price_below_minimum",
                message=f"Etsy requires a price of at least ${ETSY_MIN_PRICE:.2f}.",
                field_ref="price",
            ))
        if len(tuple(product.tags)) > ETSY_MAX_TAGS or any(
                len(str(tag)) > ETSY_TAG_MAX_CHARS for tag in product.tags):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO, code="etsy_tags_adjusted",
                message="Tags will be trimmed to Etsy's limits (13 tags, 20 characters each).",
                field_ref="tags",
            ))
        return ValidationResult(issues=tuple(issues))
