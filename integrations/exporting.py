"""Export-only integrations: first-class citizens without network access.

Some channels have no usable official API (Amazon KDP, IngramSpark, ...).
Their correct shape is: MasterProduct in, structured local handoff package out,
exactly like the prepared ``kdp/``/``etsy/`` folders the manual workflow
already produces - never a fake "API".

    exports/<integration_key>/<product-id>/
        LISTING_KIT.txt     human-readable listing copy
        manifest.json       machine-readable product summary (non-secret)
        files/              artifact bytes copied under stable names

The generic :class:`FolderExportIntegration` below is the minimal reference
implementation of that contract.  It is NOT registered in the integration
registry and performs no remote calls; production exporters for specific
platforms should subclass it and only adjust naming/validation as needed.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from integrations.base import CapabilityFlags, ConnectionReport
from integrations.foundation import UniversalPublishingIntegration
from integrations.product import MasterProduct, validate_canonical
from integrations.results import PublishResult
from integrations.validation import ValidationSeverity  # noqa: F401 (re-exported for adapters)

EXPORT_LAYOUT_VERSION = 1

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")


def safe_segment(raw: str) -> str:
    """Filesystem-safe folder/file name segment ('' -> 'unnamed')."""
    cleaned = _SAFE_SEGMENT.sub("-", str(raw or "").strip()).strip("-.")
    return cleaned[:80] or "unnamed"


class FolderExportIntegration(UniversalPublishingIntegration):
    """Reference export-only adapter: writes handoff folders, nothing else.

    No credentials, no configuration and no network are involved, so
    ``is_configured`` is always True and the connection report explains the
    export-only mode instead of pretending an account exists.
    """

    key = "folder_export"
    label = "Folder Export"
    mode = "export_only"
    capabilities = CapabilityFlags(can_export_package=True, can_validate_products=True)

    def is_configured(self) -> bool:
        return True

    def test_connection(self) -> ConnectionReport:
        return ConnectionReport(
            platform=self.key,
            ok=True,
            connected=False,
            message=("This is an export-only channel: packages are generated locally "
                     "and uploaded by hand. There is no account connection to test."),
        )

    def validate_product(self, product: MasterProduct):
        return validate_canonical(product)

    def export_package(self, product: MasterProduct, destination) -> PublishResult:
        validation = self.validate_product(product)
        if not validation.valid:
            return PublishResult.failure(
                integration_key=self.key,
                message=f"Cannot export yet: {validation.first_error_message()}",
                error_code="validation_failed",
                recovery={"errors": str(len(validation.errors))},
            )
        try:
            root = write_export_bundle(product, self.key, destination)
        except OSError as exc:
            return PublishResult.failure(
                integration_key=self.key,
                message=f"The export folder could not be written ({exc}).",
                error_code="write_failed",
            )
        return PublishResult.ok(
            integration_key=self.key,
            status="exported",
            message=(f"Export package created at {root}. Upload it through the "
                     "channel's own seller portal; nothing was published."),
            recovery={"export_path": str(root), "layout_version": str(EXPORT_LAYOUT_VERSION)},
        )


def write_export_bundle(product: MasterProduct, integration_key: str, destination) -> Path:
    """Create ``<destination>/<key>/<product-id>/`` with kit + manifest + files."""
    root = Path(destination) / safe_segment(integration_key) / safe_segment(product.internal_product_id)
    files_dir = root / "files"
    # Re-exports overwrite deterministically: same product revision in,
    # identical file set out, no stale artifacts left behind.
    files_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    used_names = set()
    for index, artifact in enumerate(product.artifacts):
        source = Path(artifact.path)
        if not source.is_file():
            continue
        stem = source.stem or f"artifact-{index}"
        name = safe_segment(f"{index:02d}-{stem}") + source.suffix.lower()
        while name in used_names:
            name = safe_segment(f"{index:02d}-{stem}-copy") + source.suffix.lower()
        used_names.add(name)
        shutil.copyfile(source, files_dir / name)
        copied.append({"file": f"files/{name}", "purpose": artifact.purpose.value})
    (root / "LISTING_KIT.txt").write_text(render_listing_kit(product), encoding="utf-8")
    manifest = {
        "layout_version": EXPORT_LAYOUT_VERSION,
        "integration_key": integration_key,
        "internal_product_id": product.internal_product_id,
        "sku": product.sku,
        "revision": product.revision,
        "title": product.title,
        "subtitle": product.subtitle,
        "author": product.author,
        "language": product.language,
        "product_type": product.product_type,
        "price": product.price,
        "currency": product.currency,
        "isbn": product.isbn,
        "page_count": product.page_count,
        "trim_size": product.trim_size,
        "generated_at": product.generated_at,
        "ai_disclosure": product.ai_disclosure,
        "artifacts": copied,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return root


def render_listing_kit(product: MasterProduct) -> str:
    """Human-readable listing copy, matching the spirit of existing kits."""
    lines = [
        "LISTING KIT",
        "=" * 40,
        f"Title: {product.title}",
    ]
    if product.subtitle:
        lines.append(f"Subtitle: {product.subtitle}")
    if product.author:
        lines.append(f"Author/Creator: {product.author}")
    if product.brand:
        lines.append(f"Brand/Imprint: {product.brand}")
    if product.short_description:
        lines.append(f"\nShort description:\n{product.short_description}")
    if product.description:
        lines.append(f"\nDescription:\n{product.description}")
    if product.tags:
        lines.append("\nTags (one per line):\n" + "\n".join(product.tags))
    if product.keywords:
        lines.append("\nKeywords (one per line):\n" + "\n".join(product.keywords))
    if product.categories:
        lines.append("\nCategories:\n" + "\n".join(product.categories))
    commercial = []
    if product.price is not None:
        commercial.append(f"Suggested price: {product.price:.2f} {product.currency}")
    if product.publication_date:
        commercial.append(f"Publication date: {product.publication_date}")
    if commercial:
        lines.append("\n" + "; ".join(commercial))
    print_bits = []
    if product.isbn:
        print_bits.append(f"ISBN: {product.isbn}")
    if product.page_count:
        print_bits.append(f"Pages: {product.page_count}")
    if product.trim_size:
        print_bits.append(f'Trim size: {product.trim_size}"')
    if print_bits:
        lines.append("\nPrint details: " + ", ".join(print_bits))
    lines.append(f"\nLanguage: {product.language or 'unspecified'}")
    if product.target_audience:
        lines.append(f"Audience: {product.target_audience}")
    if product.ai_disclosure:
        lines.append(f"AI content disclosure: {product.ai_disclosure}")
    if product.generated_at:
        lines.append(f"Generated: {product.generated_at}")
    lines.append("\nReview everything above in the channel's own seller portal before publishing.")
    return "\n".join(lines) + "\n"
