"""Opt-in universal adapter contract (Universal Publishing Foundation).

WHY A SEPARATE BASE CLASS

The Phase A contract (:class:`integrations.base.PublishingIntegration`) is
deliberately write-free, and its security tests assert that neither the base
nor the committed Etsy adapter ever grows ``create_draft``/``publish``-style
methods by accident.  That guarantee is PRESERVED: this module defines a
SIBLING subclass that future adapters opt into.  The existing Etsy stack keeps
its exact public shape and its own draft automation; nothing here changes it.

THE CONTRACT

    MasterProduct  ->  adapter (this interface)  ->  PublishResult
                                                 or Export Package

Every operation is OPTIONAL.  An adapter overrides exactly what its capability
flags advertise; everything else fails LOUDLY with
:class:`integrations.errors.UnsupportedCapabilityError` - never a silent no-op
- so callers can trust that any returned PublishResult means real work was
done.  CapabilityFlags remain authoritative; this base never invents support.

An export-only integration with NO authentication and NO network access is a
first-class citizen here (see integrations.exporting).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from integrations.base import PublishingIntegration
from integrations.errors import UnsupportedCapabilityError
from integrations.product import MasterProduct
from integrations.results import PublishResult
from integrations.validation import ValidationResult


def _unsupported(integration, operation: str) -> UnsupportedCapabilityError:
    return UnsupportedCapabilityError(
        f"{integration.label or integration.key} does not support {operation}. "
        "Nothing was attempted and nothing was changed."
    )


class UniversalPublishingIntegration(PublishingIntegration):
    """Full optional operation surface for NEW adapters.

    Class attributes (same convention as Phase A):
        key, label, capabilities - plus ``mode``:
            "api"          talks to an official remote API
            "export_only"  produces local handoff packages, no remote calls
    """

    mode: ClassVar[str] = "api"

    # -- validation -----------------------------------------------------------

    def validate_product(self, product: MasterProduct) -> ValidationResult:
        """Channel-specific pre-flight; raise-by-default, adapters opt in."""
        raise _unsupported(self, "product validation")

    # -- API-style operations ---------------------------------------------------

    def create_draft(self, product: MasterProduct) -> PublishResult:
        """Create a remote DRAFT listing; must never activate/publish."""
        raise _unsupported(self, "draft creation")

    def publish(self, product: MasterProduct) -> PublishResult:
        """Make a listing live. Only adapters whose policy explicitly allows it."""
        raise _unsupported(self, "publishing")

    def update(self, remote_id: str, product: MasterProduct) -> PublishResult:
        """Update an existing remote listing identified by *remote_id*."""
        raise _unsupported(self, "listing updates")

    def get_status(self, remote_id: str) -> PublishResult:
        """Read back the current remote state for one listing."""
        raise _unsupported(self, "status lookups")

    # -- export-only operations -------------------------------------------------

    def export_package(self, product: MasterProduct, destination) -> PublishResult:
        """Write a structured handoff package under *destination*."""
        raise _unsupported(self, "export packages")
