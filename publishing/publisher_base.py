"""Shared marketplace contract for safe preparation-only publishing."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class PublisherBase(ABC):
    key: str
    label: str

    @abstractmethod
    def validate(self, book: dict) -> list[str]:
        """Return plain-English reasons this marketplace is not ready."""

    @abstractmethod
    def prepare(self, book: dict, target: Path) -> list[Path]:
        """Create a marketplace handoff package; never publish through a browser."""

    def publish(self, book: dict) -> None:
        raise NotImplementedError(f"{self.label} publishing is not connected yet. Use Prepare, then upload through the official platform.")
