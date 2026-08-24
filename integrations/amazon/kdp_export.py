"""Amazon KDP export-only integration: real proof of the export contract.

This adapter demonstrates that a channel with NO official API is a
first-class Universal Publishing citizen.  It performs ZERO new KDP business
logic:

- It reuses the print-interior / full-wrap cover files the existing KDP
  pipeline already generated (never regenerating or re-dimensioning them).
- It writes a structured handoff folder via the shared export machinery:

      exports/amazon_kdp/<product-id>/
          LISTING_KIT.txt     listing copy + print details from MasterProduct
          manifest.json       machine-readable, non-secret product summary
          files/              copies of interior PDF, wrap cover, thumbnails

- It never logs in, never opens a browser, never uploads, never publishes,
  and never touches marketplace_status (the human-owned record).  The only
  state an adopting caller may persist is the automation-owned
  ``integration_state`` column.

Registry key is ``amazon_kdp`` so ``registry.get_integration("amazon")``
stays None - the Phase A security invariant that only reviewed API adapters
appear there is preserved; use ``get_export_integration("amazon_kdp")``.
"""

from __future__ import annotations

from integrations.base import CapabilityFlags, ConnectionReport
from integrations.exporting import FolderExportIntegration
from integrations.product import ArtifactPurpose, MasterProduct, validate_canonical
from integrations.validation import (
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


class KDPPackageExportIntegration(FolderExportIntegration):
    """Export-only Amazon KDP handoff builder (local files only)."""

    key = "amazon_kdp"
    label = "Amazon KDP Export"
    mode = "export_only"
    capabilities = CapabilityFlags(can_export_package=True, can_validate_products=True)

    def test_connection(self):
        return ConnectionReport(
            platform=self.key,
            ok=True,
            connected=False,
            message=("Amazon KDP has no seller API: this integration prepares a local "
                     "export package from your finished book. Upload it at kdp.amazon.com "
                     "yourself - nothing is sent automatically."),
        )

    def validate_product(self, product: MasterProduct) -> ValidationResult:
        """Canonical checks plus KDP's two mandatory print assets."""
        result = validate_canonical(product)
        issues = list(result.issues)

        def add(code: str, message: str, purpose: ArtifactPurpose) -> None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR, code=code, message=message,
                artifact_ref=purpose.value,
                suggested_fix=f"Create the complete package so the {purpose.value.replace('_', ' ')} file exists.",
            ))

        if not product.has_artifact(ArtifactPurpose.PRINT_INTERIOR):
            add("kdp_interior_required",
                "A KDP export needs the finished interior PDF.", ArtifactPurpose.PRINT_INTERIOR)
        if not product.has_artifact(ArtifactPurpose.PRINT_COVER):
            add("kdp_cover_required",
                "A KDP export needs the full-wrap cover PDF built on the current KDP template.",
                ArtifactPurpose.PRINT_COVER)
        if not str(product.isbn).strip():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING, code="kdp_isbn_missing",
                message="No ISBN supplied; KDP can assign one during setup.",
                field_ref="isbn",
            ))
        if not str(product.trim_size).strip():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING, code="kdp_trim_missing",
                message="No trim size recorded; confirm 8.5 x 11 during KDP setup.",
                field_ref="trim_size",
            ))
        return ValidationResult(issues=tuple(issues))


def create_kdp_export_integration(**kwargs) -> KDPPackageExportIntegration:
    """Factory used by the registry's export table."""
    return KDPPackageExportIntegration(**kwargs)
