"""PublicationRecord: a marketplace-neutral VIEW over existing catalog rows.

CRITICAL DESIGN RULE (one publishing system):

This is NOT a second persistence system.  PublicationRecord is a frozen
domain object mapped onto data that already lives in the authoritative
SQLite catalog:

    marketplace_status  ->  listing_status / external_id / url /
                            updated_at / error_message
    + integration columns -> integration_state / last_synced_at /
                            idempotency_key / external_sku

No new tables, no migration, no dual writes.  Future GUI code can consume one
neutral type per row instead of dict-shape knowledge, while every write still
flows through the existing guarded PublishingDatabase methods.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicationRecord:
    """One product's state on one channel, as proven by stored records."""

    internal_product_id: str = ""
    integration_key: str = ""

    # Human-owned truth from marketplace_status (verbatim; never reinterpreted).
    listing_status: str = ""          # e.g. "Not Prepared", "Ready", "Uploaded", "Published"
    remote_id: str = ""               # marketplace_status.external_id (ASIN, listing id, ...)
    remote_url: str = ""              # marketplace_status.url

    # Automation-owned truth from the integration columns.
    integration_state: str = ""       # "", "draft_created", "files_uploaded", "complete"
    idempotency_key: str = ""
    external_sku: str = ""

    # Timestamps exactly as stored ('' when unknown).
    updated_at: str = ""
    last_synced_at: str = ""
    error_message: str = ""

    @property
    def published_at(self) -> str:
        """Timestamp ONLY when a human confirmed Published. Uploaded never counts."""
        return self.updated_at if self.listing_status == "Published" else ""

    @property
    def uploaded_at(self) -> str:
        """Timestamp ONLY when a human confirmed Uploaded."""
        return self.updated_at if self.listing_status == "Uploaded" else ""

    @property
    def is_published(self) -> bool:
        return self.listing_status == "Published"

    @classmethod
    def from_marketplace_record(cls, book_id: str, integration_key: str,
                                record: dict, integration: dict | None = None) -> "PublicationRecord":
        """Map one ``marketplace_records()`` row (+ optional integration row).

        Unknown/missing fields simply stay empty; this mapper never guesses a
        publication state the stored data does not prove.
        """
        record = record or {}
        integration = integration or {}
        return cls(
            internal_product_id=str(book_id),
            integration_key=str(integration_key),
            listing_status=str(record.get("status") or ""),
            remote_id=str(record.get("external_id") or ""),
            remote_url=str(record.get("url") or ""),
            integration_state=str(integration.get("integration_state") or record.get("integration_state") or ""),
            idempotency_key=str(integration.get("idempotency_key") or record.get("idempotency_key") or ""),
            external_sku=str(integration.get("external_sku") or record.get("external_sku") or ""),
            updated_at=str(record.get("updated_at") or ""),
            last_synced_at=str(integration.get("last_synced_at") or record.get("last_synced_at") or ""),
            error_message=str(record.get("error_message") or ""),
        )
