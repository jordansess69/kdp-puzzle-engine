"""Human review queue + append-only decision log.

Every classification proposal that matters but is not certain lands here.
Human decisions are recorded once in decisions.jsonl (provenance) and can
be replayed onto any store, so approvals/rejections survive re-runs and
regenerations.  Decisions also feed the ambiguity registry and the
curated approved-links source used by the master bank builder.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .records import (
    APPROVED,
    CLASSIFIER_VERSION,
    PROPOSED,
    REJECTED,
    EvidenceItem,
    SIGNAL_HUMAN_DECISION,
    TopicLink,
)
from .store import DECISIONS_LOGNAME, REVIEW_QUEUE_FILENAME

# Review actions (stable strings - they persist in the decision log).
ACTION_APPROVE = "approve_link"
ACTION_REJECT = "reject_link"
ACTION_MOVE = "move_word"
ACTION_FLAG_AMBIGUOUS = "flag_ambiguous"
ACTION_RESOLVE_AMBIGUOUS = "resolve_ambiguous"
ACTION_FLAG_TRADEMARK = "flag_trademark"
ACTION_IGNORE = "ignore"

VALID_ACTIONS = {
    ACTION_APPROVE, ACTION_REJECT, ACTION_MOVE, ACTION_FLAG_AMBIGUOUS,
    ACTION_RESOLVE_AMBIGUOUS, ACTION_FLAG_TRADEMARK, ACTION_IGNORE,
}


@dataclass
class ReviewItem:
    item_id: str
    word: str
    topic_id: str
    reason: str
    confidence: float = 0.0
    kind: str = "word_link"          # word_link | ambiguous_word | theme_issue
    status: str = "open"             # open | resolved | dismissed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    resolved_at: str = ""
    evidence_summary: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id, "word": self.word, "topic_id": self.topic_id,
            "reason": self.reason, "confidence": round(self.confidence, 1),
            "kind": self.kind, "status": self.status,
            "created_at": self.created_at, "resolved_at": self.resolved_at,
            "evidence_summary": list(self.evidence_summary),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewItem":
        return cls(
            item_id=str(data["item_id"]), word=str(data.get("word", "")),
            topic_id=str(data.get("topic_id", "")), reason=str(data.get("reason", "")),
            confidence=float(data.get("confidence", 0.0)),
            kind=str(data.get("kind", "word_link")),
            status=str(data.get("status", "open")),
            created_at=str(data.get("created_at", "")),
            resolved_at=str(data.get("resolved_at", "")),
            evidence_summary=list(data.get("evidence_summary", [])),
        )


class ReviewQueue:
    def __init__(self, items=None) -> None:
        self.items: dict[str, ReviewItem] = {i.item_id: i for i in (items or [])}
        self._counter = 0

    # ---------------- queue management ----------------

    def add(self, word: str, topic_id: str, reason: str, confidence: float = 0.0,
            kind: str = "word_link", evidence_summary=None) -> ReviewItem:
        existing = self.find_open(word, topic_id, kind)
        if existing is not None:
            return existing
        self._counter += 1
        item = ReviewItem(
            item_id=f"{datetime.now().strftime('%Y%m%d')}-{self._counter:04d}",
            word=word, topic_id=topic_id, reason=reason,
            confidence=confidence, kind=kind,
            evidence_summary=list(evidence_summary or []))
        self.items[item.item_id] = item
        return item

    def find_open(self, word: str, topic_id: str, kind: str = "word_link") -> ReviewItem | None:
        for item in self.items.values():
            if (item.status == "open" and item.word == word
                    and item.topic_id == topic_id and item.kind == kind):
                return item
        return None

    def open_items(self, kind: str | None = None) -> list[ReviewItem]:
        chosen = [i for i in self.items.values() if i.status == "open"]
        if kind:
            chosen = [i for i in chosen if i.kind == kind]
        return sorted(chosen, key=lambda i: (-i.confidence, i.word, i.item_id))

    def mark_resolved(self, item_id: str, dismissed: bool = False) -> None:
        item = self.items.get(item_id)
        if item is None:
            raise KeyError(item_id)
        item.status = "dismissed" if dismissed else "resolved"
        item.resolved_at = datetime.now().isoformat(timespec="seconds")

    # ---------------- persistence ----------------

    def save(self, state_dir) -> Path:
        state_dir = Path(state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)
        path = state_dir / REVIEW_QUEUE_FILENAME
        payload = json.dumps(
            {"items": [i.to_dict() for i in sorted(self.items.values(),
                                                   key=lambda x: x.item_id)]},
            indent=1, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(dir=str(state_dir), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
        return path

    @classmethod
    def load(cls, state_dir) -> "ReviewQueue":
        path = Path(state_dir) / REVIEW_QUEUE_FILENAME
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return cls([ReviewItem.from_dict(d) for d in data.get("items", [])])
        except (OSError, json.JSONDecodeError):
            return cls()


class DecisionLog:
    """Append-only JSONL record of every human decision."""

    def __init__(self, path) -> None:
        self.path = Path(path)
        self.entries: list[dict] = []
        if self.path.exists():
            try:
                for line in self.path.read_text(encoding="utf-8-sig").splitlines():
                    line = line.strip()
                    if line:
                        self.entries.append(json.loads(line))
            except (OSError, json.JSONDecodeError):
                self.entries = []

    def append(self, action: str, word: str, topic_id: str = "",
               topic_from: str = "", note: str = "") -> dict:
        if action not in VALID_ACTIONS:
            raise ValueError(f"Unknown review action: {action}")
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "actor": "human",
            "action": action,
            "word": word,
            "topic_id": topic_id,
            "topic_from": topic_from,
            "note": note,
            "classifier_version": CLASSIFIER_VERSION,
        }
        self.entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def decisions_for(self, word: str) -> list[dict]:
        return [e for e in self.entries if e.get("word") == word]


# ---------------------------------------------------------------------------
# Applying decisions to the store
# ---------------------------------------------------------------------------

def apply_decision(store, taxonomy, registry, log: DecisionLog, queue: ReviewQueue,
                   action: str, word: str, topic_id: str = "", topic_from: str = "",
                   note: str = "") -> dict:
    """Apply one human decision; returns a small outcome summary.

    APPROVE/REJECT create permanent TopicLinks that later classifier runs
    respect; approved links additionally flow into the curated source file
    via the apply engine, keeping builder regeneration safe.
    """
    norm = word.upper()
    record = store.get(norm)
    if record is None:
        record = store.ensure_record(norm, word.title())

    outcome = {"action": action, "word": norm}

    if action == ACTION_APPROVE:
        _set_link(record, topic_id, APPROVED, note)
    elif action == ACTION_REJECT:
        _set_link(record, topic_id, REJECTED, note)
    elif action == ACTION_MOVE:
        if topic_from:
            _set_link(record, topic_from, REJECTED, f"moved: {note}")
        if topic_id:
            _set_link(record, topic_id, APPROVED, note)
        outcome["moved"] = True
    elif action == ACTION_FLAG_AMBIGUOUS:
        senses = [s for s in (topic_id, topic_from) if s]
        registry.register(norm, senses or ["unspecified"], note="human-flagged")
        if norm not in record.ambiguous_senses:
            record.ambiguous_senses += senses[:2]
    elif action == ACTION_RESOLVE_AMBIGUOUS:
        registry.resolve(norm, topic_id, note=note)
        record.ambiguous_senses = []
    elif action == ACTION_FLAG_TRADEMARK:
        record.trademark_review = True
    elif action == ACTION_IGNORE:
        pass  # no state change; recorded for provenance only

    log.append(action, norm, topic_id=topic_id, topic_from=topic_from, note=note)

    item = queue.find_open(norm, topic_id or topic_from)
    if item is not None:
        queue.mark_resolved(item.item_id, dismissed=(action == ACTION_IGNORE))
    else:
        for open_item in queue.open_items():
            if open_item.word == norm:
                queue.mark_resolved(open_item.item_id,
                                    dismissed=(action == ACTION_IGNORE))
                break
    return outcome


def _set_link(record, topic_id: str, status: str, note: str) -> None:
    link = record.link_for(topic_id)
    evidence = [EvidenceItem(SIGNAL_HUMAN_DECISION, note or f"Human {status}", status_weight(status))]
    if link is None:
        record.topics.append(TopicLink(topic_id, status, status_weight(status), evidence))
    else:
        link.status = status
        link.evidence = evidence + [e for e in link.evidence
                                    if e.signal != SIGNAL_HUMAN_DECISION]
        if status == APPROVED:
            link.confidence = max(link.confidence, 100.0)


def status_weight(status: str) -> float:
    return 100.0 if status == APPROVED else 0.0


def seed_review_queue(store, classifier_stats_bands=("medium",)) -> ReviewQueue:
    """Create review items from current store state (idempotent)."""
    from .records import band_of as _band
    queue = ReviewQueue()
    for norm, record in sorted(store.records.items()):
        if record.safety_review or record.trademark_review:
            continue
        for link in record.topics:
            if link.status == PROPOSED and _band(link.confidence) in classifier_stats_bands:
                queue.add(
                    norm, link.topic_id,
                    reason=f"{_band(link.confidence).replace('_', ' ').title()} "
                           f"confidence proposal ({link.confidence:.0f})",
                    confidence=link.confidence,
                    evidence_summary=[str(e) for e in link.evidence[:4]])
        if record.ambiguous_senses:
            first = record.ambiguous_senses[0]
            queue.add(norm, first, reason="Word has multiple strong senses",
                      kind="ambiguous_word")
    return queue
