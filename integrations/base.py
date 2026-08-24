"""Shared integration contract for marketplace adapters (Phase A).

Phase A deliberately defines ONLY the read-only surface area: a configuration
check plus a connection verification report.  Write capabilities (draft
creation, file/image uploads, listing activation) are intentionally absent
from this contract; they will be added in explicitly approved later phases.

Not defining write methods here is a safety feature: an adapter cannot grow a
write path by accident - it would have to extend this contract first, which
shows up in code review and in the Phase A security tests.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Optional


@dataclass(frozen=True)
class CapabilityFlags:
    """Truthful advertisement of what an adapter can do *right now*.

    Adapters must only set flags for capabilities that are actually
    implemented and safe to invoke; future capability may be discussed in the
    adapter's docstring instead of being pre-advertised here.
    """

    can_test_connection: bool = False
    can_create_draft: bool = False
    can_upload_files: bool = False
    can_upload_images: bool = False
    can_activate: bool = False
    can_pull_status: bool = False
    can_pull_sales: bool = False
    requires_public_file_urls: bool = False

    @property
    def has_any_write_capability(self):
        return any(
            (
                self.can_create_draft,
                self.can_upload_files,
                self.can_upload_images,
                self.can_activate,
            )
        )


@dataclass(frozen=True)
class ConnectionReport:
    """Result of a read-only connectivity verification.

    ``ok`` means the check itself ran to a conclusion (no unexpected crash);
    ``connected`` means remote credentials were actually verified.  All fields
    are non-secret and safe to display in the Publishing Hub.
    """

    platform: str
    ok: bool
    connected: bool
    user_id: Optional[int] = None
    shop_id: Optional[int] = None
    shop_name: Optional[str] = None
    message: str = ""


class PublishingIntegration(ABC):
    """Base contract every marketplace adapter implements.

    Class attributes:
        key: short registry key, e.g. "etsy".
        label: human-readable platform name for UI display.
        capabilities: CapabilityFlags describing implemented features only.
    """

    key: ClassVar[str] = ""
    label: ClassVar[str] = ""
    capabilities: ClassVar[CapabilityFlags] = CapabilityFlags()

    @abstractmethod
    def is_configured(self) -> bool:
        """True when enough credentials are present to attempt a connection."""

    @abstractmethod
    def test_connection(self) -> ConnectionReport:
        """Perform read-only verification against the remote platform.

        Implementations must never raise for ordinary failure modes; they
        return a ConnectionReport with a plain-English message instead.
        """
