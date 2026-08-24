"""Ambiguity registry: words that legitimately belong to several topics.

Some words are permanently multi-sense (BASS the fish vs BASS the guitar).
Rather than forcing a wrong single answer, ambiguous words are registered,
surfaced for human resolution, and excluded from automatic linking until
resolved.  Human decisions here feed future classification runs.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .normalization import clean_surface
from .records import TRUSTED, band_of
from .store import AMBIGUITY_FILENAME

# Well-known multi-sense words seed the registry so day-one behaviour is
# sensible even before any scan has run.
SEED_AMBIGUOUS = {
    "BASS": ["fish", "music"],
    "BAT": ["animals", "sports"],
    "BANK": ["money", "nature"],
    "JAGUAR": ["animals", "cars"],
    "MUSTANG": ["animals", "vehicles"],
    "JAVA": ["coffee", "programming"],
    "RAM": ["animals", "computers"],
    "TURKEY": ["birds", "countries", "food"],
    "DATE": ["fruit", "time"],
    "CRANE": ["birds", "machinery"],
    "SEAL": ["ocean life", "emblems"],
}

FAMILY_SPLIT_THRESHOLD = 70.0  # both senses must score at least this high

# The grab-bag family is cross-cutting BY DESIGN; membership there never
# counts as a competing sense (mission §11: ambiguity = unrelated senses).
CROSS_CUTTING_FAMILIES = frozenset({"General & Flexible", ""})


class AmbiguityRegistry:
    def __init__(self, entries: dict | None = None) -> None:
        # word -> {"senses": [...], "resolved_to": str|None, "notes": str}
        self.entries: dict[str, dict] = dict(entries or {})

    @staticmethod
    def _key(normalized: str) -> str:
        return clean_surface(normalized)

    @classmethod
    def seeded(cls) -> "AmbiguityRegistry":
        registry = cls()
        for word, senses in SEED_AMBIGUOUS.items():
            registry.entries[word] = {"senses": list(senses), "resolved_to": None, "notes": ""}
        return registry

    # ------------------------------------------------------------------

    def is_ambiguous(self, normalized: str) -> bool:
        entry = self.entries.get(self._key(normalized))
        return bool(entry and not entry.get("resolved_to"))

    def resolve(self, normalized: str, topic_id: str, note: str = "") -> None:
        entry = self.entries.setdefault(
            self._key(normalized), {"senses": [], "resolved_to": None, "notes": ""})
        entry["resolved_to"] = topic_id
        if note:
            entry["notes"] = note

    def unresolve(self, normalized: str) -> None:
        entry = self.entries.get(self._key(normalized))
        if entry is not None:
            entry["resolved_to"] = None

    def register(self, normalized: str, senses, note: str = "") -> None:
        key = self._key(normalized)
        entry = self.entries.get(key)
        if entry is None:
            self.entries[key] = {
                "senses": list(senses), "resolved_to": None, "notes": note}
        else:
            for sense in senses:
                if sense not in entry["senses"]:
                    entry["senses"].append(sense)

    def entries_sorted(self) -> list[tuple[str, dict]]:
        return sorted(self.entries.items())

    # ------------------------------------------------------------------

    def save(self, state_dir) -> Path:
        state_dir = Path(state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)
        path = state_dir / AMBIGUITY_FILENAME
        payload = json.dumps({"words": dict(self.entries_sorted())},
                             indent=1, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(dir=str(state_dir), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
        return path

    @classmethod
    def load(cls, state_dir) -> "AmbiguityRegistry":
        path = Path(state_dir) / AMBIGUITY_FILENAME
        if not path.exists():
            return cls.seeded()
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return cls(data.get("words") or {})
        except (OSError, json.JSONDecodeError):
            return cls.seeded()


def scan_for_ambiguity(store, families: dict[str, str], registry: AmbiguityRegistry,
                       apply_flags: bool = True) -> list[str]:
    """Detect words where CLASSIFIER proposals conflict across families.

    Multiple TRUSTED memberships across families are deliberate curation
    in the existing master bank (common words serve several topics), so
    they are NOT treated as ambiguity - only unconfirmed strong proposals
    that disagree trigger a flag.  Humans can always flag any word
    manually via the review queue.
    """
    def _specific(fam: str | None) -> str | None:
        if not fam or fam in CROSS_CUTTING_FAMILIES:
            return None
        return fam

    detected: list[str] = []
    for norm, record in sorted(store.records.items()):
        proposed_families: set[str] = set()
        for link in record.topics:
            if link.status != "proposed":
                continue
            fam = _specific(families.get(link.topic_id))
            if link.confidence >= FAMILY_SPLIT_THRESHOLD and fam:
                proposed_families.add(fam)
        if len(proposed_families) > 1:
            senses = sorted(proposed_families)
            if not registry.entries.get(norm, {}).get("resolved_to"):
                registry.register(norm, senses, note="auto-detected")
                detected.append(norm)
                if apply_flags and norm not in record.ambiguous_senses:
                    record.ambiguous_senses = senses[:4]
    return detected


def ambiguity_guard(record, registry: AmbiguityRegistry, families: dict[str, str],
                    candidate_links: list) -> float:
    """Penalty applied during classification for unresolved ambiguous words.

    Returns a multiplicative damping factor (1.0 = no penalty).  Ambiguity
    never blocks human review - it just keeps scores out of auto-link range
    until someone resolves the sense.
    """
    if not registry.is_ambiguous(record.normalized):
        return 1.0
    entry = registry.entries[record.normalized]
    resolved = entry.get("resolved_to")
    if resolved:
        return 1.0
    top = max((l.confidence for l in candidate_links), default=0.0)
    if top >= FAMILY_SPLIT_THRESHOLD:
        return 0.55  # caps below VERY_HIGH once damped through scoring
    return 0.8
