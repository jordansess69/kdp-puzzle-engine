"""Generic validation structures shared by the universal publishing layer.

Canonical product checks live next to MasterProduct
(:func:`integrations.product.validate_canonical`).  Marketplace-specific rules
(title length, tag counts, taxonomy ids, image limits) belong to each
adapter/mapper and simply reuse the structures below, so one GUI renderer can
display every channel's findings without hardcoding platforms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple


class ValidationSeverity(str, Enum):
    ERROR = "error"      # blocks the operation for this channel
    WARNING = "warning"  # proceed possible, but review first
    INFO = "info"        # neutral note


@dataclass(frozen=True)
class ValidationIssue:
    """One finding: what is wrong (or worth knowing), where, and how to fix it."""

    severity: ValidationSeverity
    code: str
    message: str
    field_ref: str = ""
    artifact_ref: str = ""          # artifact path or purpose value when relevant
    suggested_fix: str = ""

    def __post_init__(self):
        if not isinstance(self.severity, ValidationSeverity):
            object.__setattr__(self, "severity", ValidationSeverity(str(self.severity)))


@dataclass(frozen=True)
class ValidationResult:
    """Aggregate of issues with a strict definition of validity.

    ``valid`` means ZERO errors.  Warnings and infos never flip validity, so a
    channel may proceed while still surfacing review items.
    """

    issues: Tuple[ValidationIssue, ...] = field(default_factory=tuple)

    @property
    def valid(self) -> bool:
        return not any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    @property
    def errors(self) -> Tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warnings(self) -> Tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == ValidationSeverity.WARNING)

    @property
    def infos(self) -> Tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == ValidationSeverity.INFO)

    def first_error_message(self) -> str:
        return self.errors[0].message if self.errors else ""

    @classmethod
    def aggregate(cls, *results: "ValidationResult") -> "ValidationResult":
        """Merge many results into one; duplicates are kept so counts stay truthful."""
        merged: list = []
        for result in results:
            merged.extend(result.issues)
        return cls(issues=tuple(merged))

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls()
