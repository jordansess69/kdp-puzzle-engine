"""Word Intelligence record model.

A WordRecord is marketplace-independent and theme-independent: it captures
what the system KNOWS about a vocabulary item - never where it is being
sold.  Existing master-bank structures stay authoritative for "trusted"
membership; this layer adds normalized identity, evidence, confidence,
flags and review state around them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

CLASSIFIER_VERSION = "1.0"

# Signal names used in evidence items (stable strings - reports depend on them).
SIGNAL_EXISTING = "existing_trusted_assignment"
SIGNAL_LEXICON = "exact_topic_lexicon_match"
SIGNAL_ALIAS = "alias_or_variant"
SIGNAL_TAXONOMY = "taxonomy_relation"
SIGNAL_PHRASE_TOKEN = "phrase_token_signal"
SIGNAL_SOURCE_SUGGESTION = "source_root_suggestion"
SIGNAL_COOCCURRENCE = "theme_co_occurrence"
SIGNAL_THEME_HISTORY = "production_theme_history"
SIGNAL_FAMILIARITY = "familiarity_screen"
SIGNAL_HUMAN_DECISION = "human_review_decision"
SIGNAL_NEGATIVE = "negative_signal"
SIGNAL_AMBIGUITY = "ambiguity_warning"

# Confidence bands (mission §6).
VERY_HIGH_MIN = 95
HIGH_MIN = 80
MEDIUM_MIN = 60


def band_of(confidence: float) -> str:
    if confidence >= VERY_HIGH_MIN:
        return "very_high"
    if confidence >= HIGH_MIN:
        return "high"
    if confidence >= MEDIUM_MIN:
        return "medium"
    return "low"


@dataclass(frozen=True)
class EvidenceItem:
    """One explainable reason behind a score ('Why does this belong here?')."""

    signal: str
    detail: str
    weight: float = 0.0

    def __str__(self) -> str:  # compact human line for reports/GUI
        sign = "+" if self.weight >= 0 else "-"
        return f"{sign} {self.detail}"

    def to_dict(self) -> dict:
        return {"signal": self.signal, "detail": self.detail, "weight": round(self.weight, 1)}

    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceItem":
        return cls(
            signal=str(data.get("signal", "")),
            detail=str(data.get("detail", "")),
            weight=float(data.get("weight", 0.0)),
        )


# Link status lifecycle.
TRUSTED = "trusted"          # existing reviewed association (master bank)
PROPOSED = "proposed"        # classifier proposal awaiting decision
APPROVED = "approved"        # human-approved via review queue
REJECTED = "rejected"        # human-rejected; blocks future proposals
EXCLUDED = "excluded"        # safety/exclusion rule


@dataclass
class TopicLink:
    topic_id: str
    status: str
    confidence: float = 0.0
    evidence: list[EvidenceItem] = field(default_factory=list)
    classifier_version: str = CLASSIFIER_VERSION
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat(timespec="seconds")

    @property
    def band(self) -> str:
        return band_of(self.confidence)

    def strongest_evidence(self) -> EvidenceItem | None:
        if not self.evidence:
            return None
        return max(self.evidence, key=lambda e: abs(e.weight))

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "status": self.status,
            "confidence": round(self.confidence, 1),
            "band": self.band,
            "evidence": [e.to_dict() for e in self.evidence],
            "classifier_version": self.classifier_version,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TopicLink":
        return cls(
            topic_id=str(data.get("topic_id", "")),
            status=str(data.get("status", PROPOSED)),
            confidence=float(data.get("confidence", 0.0)),
            evidence=[EvidenceItem.from_dict(e) for e in data.get("evidence", [])],
            classifier_version=str(data.get("classifier_version", "")),
            updated_at=str(data.get("updated_at", "")),
        )


@dataclass
class WordRecord:
    """Everything known about one vocabulary item."""

    normalized: str                      # canonical comparison key
    display: str                         # human-facing form
    aliases: list[str] = field(default_factory=list)   # alternate surface forms
    sources: list[str] = field(default_factory=list)
    frequency: float | None = None       # zipf familiarity when known
    grade_bands: list[str] = field(default_factory=list)
    topics: list[TopicLink] = field(default_factory=list)
    ambiguous_senses: list[str] = field(default_factory=list)  # topic ids or hints
    trademark_review: bool = False
    safety_review: bool = False
    last_classified: str = ""
    classifier_version: str = ""

    # ------------------------- convenience -------------------------

    def link_for(self, topic_id: str) -> TopicLink | None:
        for link in self.topics:
            if link.topic_id == topic_id:
                return link
        return None

    def trusted_topics(self) -> list[str]:
        return [l.topic_id for l in self.topics if l.status == TRUSTED]

    def proposed_topics(self) -> list[TopicLink]:
        return [l for l in self.topics if l.status == PROPOSED]

    def is_unclassified(self) -> bool:
        return not any(l.status in (TRUSTED, APPROVED) for l in self.topics)

    def has_rejection_for(self, topic_id: str) -> bool:
        return any(l.topic_id == topic_id and l.status == REJECTED for l in self.topics)

    def best_confidence_for(self, topic_id: str) -> float:
        link = self.link_for(topic_id)
        return link.confidence if link else 0.0

    def to_dict(self) -> dict:
        return {
            "normalized": self.normalized,
            "display": self.display,
            "aliases": list(self.aliases),
            "sources": list(self.sources),
            "frequency": self.frequency,
            "grade_bands": list(self.grade_bands),
            "topics": [l.to_dict() for l in self.topics],
            "ambiguous_senses": list(self.ambiguous_senses),
            "trademark_review": self.trademark_review,
            "safety_review": self.safety_review,
            "last_classified": self.last_classified,
            "classifier_version": self.classifier_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WordRecord":
        return cls(
            normalized=str(data.get("normalized", "")),
            display=str(data.get("display") or data.get("normalized", "")),
            aliases=list(data.get("aliases", [])),
            sources=list(data.get("sources", [])),
            frequency=data.get("frequency"),
            grade_bands=list(data.get("grade_bands", [])),
            topics=[TopicLink.from_dict(t) for t in data.get("topics", [])],
            ambiguous_senses=list(data.get("ambiguous_senses", [])),
            trademark_review=bool(data.get("trademark_review", False)),
            safety_review=bool(data.get("safety_review", False)),
            last_classified=str(data.get("last_classified", "")),
            classifier_version=str(data.get("classifier_version", "")),
        )
