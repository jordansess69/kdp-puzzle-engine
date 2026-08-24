"""Marketplace-neutral operation result (Universal Publishing Foundation).

One shape for every adapter answer - API publishes, draft creation, status
pulls and export-only runs alike - so future GUI code never needs per-platform
result handling.

Security contract (mirrors integrations.errors):

- ``message`` is passed through :func:`redact_text` at construction time.
- ``__repr__``/``__str__`` deliberately EXCLUDE ``recovery`` metadata; even
  though callers should only store non-secret recovery hints there, the repr
  is the one string most likely to end up in a log, so it stays minimal.
- No credential objects can be attached: there is no field for them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Tuple

from integrations.errors import redact_text


@dataclass(frozen=True)
class PublishResult:
    """Outcome of one marketplace operation on one product."""

    success: bool
    integration_key: str = ""
    remote_id: str = ""
    remote_url: str = ""
    status: str = ""                 # neutral verb: "draft_created", "exported", ...
    message: str = ""                # plain-English, pre-redacted, GUI-safe
    error_code: str = ""             # stable machine code ("unsupported_capability", ...)
    warnings: Tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = ""
    # Non-secret recovery hints only (export folder, idempotency key, state name).
    recovery: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "message", redact_text(self.message))
        clean_warnings = tuple(redact_text(str(w)) for w in self.warnings)
        if clean_warnings != self.warnings:
            object.__setattr__(self, "warnings", clean_warnings)

    def __repr__(self):  # secrets can never appear: recovery is excluded entirely
        return (
            f"<PublishResult success={self.success} integration={self.integration_key!r} "
            f"remote_id={'set' if self.remote_id else 'unset'} status={self.status!r} "
            f"message={self.message!r}>"
        )

    __str__ = __repr__

    @classmethod
    def ok(cls, *, integration_key: str, status: str, message: str = "",
           remote_id: str = "", remote_url: str = "", **kwargs) -> "PublishResult":
        return cls(success=True, integration_key=integration_key, status=status,
                   message=message, remote_id=remote_id, remote_url=remote_url, **kwargs)

    @classmethod
    def failure(cls, *, integration_key: str, message: str,
                error_code: str = "", **kwargs) -> "PublishResult":
        return cls(success=False, integration_key=integration_key,
                   status="failed", message=message, error_code=error_code, **kwargs)
