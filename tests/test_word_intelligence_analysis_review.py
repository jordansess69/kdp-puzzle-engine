"""Tests for topic analytics and the human review workflow."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from word_intelligence.ambiguity import AmbiguityRegistry
from word_intelligence.analysis import (
    coverage_summary,
    duplicate_topic_warnings,
    estimate_capacity,
    exclusive_words_preview,
    _grade,
    topic_health,
    words_for_topic,
)
from word_intelligence.quality import PuzzleWorthiness
from word_intelligence.records import (
    APPROVED,
    PROPOSED,
    REJECTED,
    TRUSTED,
    TopicLink,
    WordRecord,
)
from word_intelligence.review import (
    ACTION_APPROVE,
    ACTION_FLAG_TRADEMARK,
    ACTION_IGNORE,
    ACTION_MOVE,
    ACTION_REJECT,
    ACTION_RESOLVE_AMBIGUOUS,
    DecisionLog,
    ReviewQueue,
    apply_decision,
    seed_review_queue,
)
from word_intelligence.store import make_test_store
from word_intelligence.taxonomy import TopicTaxonomy


@pytest.fixture()
def garden_world():
    bank = {
        "topics": {
            "Gardening": ["TROWEL", "SEEDS", "COMPOST", "PRUNERS", "MULCH"],
            "Birdwatching": ["WARBLER", "BINOCULARS"],
        },
        "words": [],
    }
    taxonomy = TopicTaxonomy.from_master_bank(bank)
    store = make_test_store(bank["topics"])
    # Give gardening a healthy pool plus one medium proposal.
    for name in ("TROWEL", "SEEDS", "COMPOST", "PRUNERS", "MULCH"):
        store.get(name).frequency = 3.5
    extra = WordRecord(normalized="HOSEMULCH", display="Hose Mulch", frequency=2.8)
    extra.topics.append(TopicLink("gardening", PROPOSED, 65))
    store.records["HOSEMULCH"] = extra
    return store, taxonomy


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

def test_capacity_math_mirrors_master_bank_conventions():
    caps = estimate_capacity(600, 12)
    assert caps["no_repeat_12_word_puzzles"] == 50
    assert caps["books_48_puzzles"] == 1
    assert caps["books_100_puzzles"] == 0
    assert estimate_capacity(0, 12)["no_repeat_12_word_puzzles"] == 0
    # Degenerate puzzle size must not crash or divide by zero.
    safe = estimate_capacity(100, 0)
    assert safe["unique_words"] == 100


def test_words_for_topic_filters_by_strength(garden_world):
    store, taxonomy = garden_world
    words = words_for_topic(store, "gardening")
    assert "TROWEL" in words            # trusted + familiar
    assert "HOSEMULCH" in words         # medium proposal counts by default
    strong_only = words_for_topic(store, "gardening", min_band="high")
    assert "HOSEMULCH" not in strong_only


def test_topic_health_rows_and_grades(garden_world):
    store, taxonomy = garden_world
    rows = {r["topic_id"]: r for r in topic_health(store, taxonomy)}
    garden = rows["gardening"]
    assert garden["usable_words"] == 6
    assert garden["trusted_words"] == 5
    assert garden["proposed_medium"] == 1
    assert garden["capacity_12w"]["no_repeat_12_word_puzzles"] == 0  # 6 words < 12
    birds = rows["birdwatching"]
    assert birds["trusted_words"] == 2 and birds["grade"] == "F"
    # Worst topics first for actionable reporting.
    listed = [r["topic_id"] for r in topic_health(store, taxonomy)]
    assert listed.index("birdwatching") < listed.index("gardening")


def test_grade_boundaries():
    assert _grade(1300, 576) == "A"      # signature tier
    assert _grade(600, 576) == "B"
    assert _grade(288, 576) == "C"
    assert _grade(144, 576) == "D"
    assert _grade(10, 576) == "F"


def test_coverage_summary_counts(garden_world):
    store, _ = garden_world
    summary = coverage_summary(store)
    assert summary["total_records"] == len(store.records)
    assert summary["confirmed_records"] >= 6
    assert summary["proposal_bands"]["medium"] >= 1
    assert summary["open_proposals"] >= 1


def test_duplicate_warnings_use_taxonomy_candidates():
    bank = {
        "topics": {
            "Alpha Topic": ["APPLE", "BANANA", "CHERRY", "DATE", "FIG",
                            "GRAPE", "LEMON", "LIME", "MANGO", "OLIVE"],
            "Alpha Topic Two": ["APPLE", "BANANA", "CHERRY", "DATE", "FIG",
                                "GRAPE", "LEMON", "LIME", "PAPAYA", "QUINCE"],
        },
        "words": [],
    }
    taxonomy = TopicTaxonomy.from_master_bank(bank)
    warnings = duplicate_topic_warnings(taxonomy)
    assert warnings and warnings[0]["jaccard"] > 0.6


def test_exclusive_preview_prefers_loyal_words(garden_world):
    store, _ = garden_world
    preview = exclusive_words_preview(store, "gardening")
    assert "TROWEL" in preview          # trusted only here -> exclusivity 1.0
    assert all(w in {"TROWEL", "SEEDS", "COMPOST", "PRUNERS", "MULCH"} for w in preview)


# ---------------------------------------------------------------------------
# review queue + decision log
# ---------------------------------------------------------------------------

def test_review_queue_add_is_idempotent_and_persists(tmp_path):
    queue = ReviewQueue()
    first = queue.add("BASS", "freshwater_fish", "Medium confidence proposal", 66)
    again = queue.add("BASS", "freshwater_fish", "dup")
    assert first is again
    other = queue.add("BASS", "music_instruments", "different pair")
    assert other.item_id != first.item_id
    queue.save(tmp_path)
    loaded = ReviewQueue.load(tmp_path)
    assert len(loaded.items) == 2
    assert loaded.open_items()[0].word == "BASS"


def test_decision_log_appends_and_validates(tmp_path):
    log = DecisionLog(tmp_path / "decisions.jsonl")
    log.append(ACTION_APPROVE, "TROWEL", topic_id="gardening", note="obviously right")
    with pytest.raises(ValueError):
        log.append("delete_everything", "TROWEL")
    reloaded = DecisionLog(tmp_path / "decisions.jsonl")
    assert len(reloaded.entries) == 1
    assert reloaded.decisions_for("TROWEL")[0]["action"] == ACTION_APPROVE


def test_apply_approve_reject_cycle(garden_world, tmp_path):
    store, taxonomy = garden_world
    state = tmp_path / "state"
    registry = AmbiguityRegistry()
    log = DecisionLog(state / "decisions.jsonl")
    queue = seed_review_queue(store)

    item = queue.open_items()[0]     # HOSEMULCH/gardening medium proposal
    outcome = apply_decision(
        store, taxonomy, registry, log, queue,
        ACTION_APPROVE, item.word, topic_id=item.topic_id, note="keeper")
    assert outcome["action"] == ACTION_APPROVE
    link = store.get(item.word).link_for(item.topic_id)
    assert link.status == APPROVED and link.confidence == 100.0
    assert item.status == "resolved"

    apply_decision(store, taxonomy, registry, log, queue,
                   ACTION_REJECT, "WARBLER", topic_id="gardening",
                   note="not a garden word")
    record = store.get("WARBLER")
    assert record.has_rejection_for("gardening")

    entries = DecisionLog(state / "decisions.jsonl").entries
    assert {e["action"] for e in entries} == {ACTION_APPROVE, ACTION_REJECT}


def test_apply_move_rejects_source_and_approves_target(garden_world, tmp_path):
    store, taxonomy = garden_world
    registry = AmbiguityRegistry()
    log = DecisionLog(tmp_path / "decisions.jsonl")
    queue = ReviewQueue()
    apply_decision(store, taxonomy, registry, log, queue,
                   ACTION_MOVE, "MULCH", topic_id="birdwatching",
                   topic_from="gardening", note="wrong home")
    mulch = store.get("MULCH")
    assert mulch.has_rejection_for("gardening")
    assert mulch.link_for("birdwatching").status == APPROVED


def test_trademark_flagging_blocks_quality(garden_world, tmp_path):
    store, taxonomy = garden_world
    registry = AmbiguityRegistry()
    log = DecisionLog(tmp_path / "decisions.jsonl")
    queue = ReviewQueue()
    apply_decision(store, taxonomy, registry, log, queue,
                   ACTION_FLAG_TRADEMARK, "TROWEL")
    assert store.get("TROWEL").trademark_review


def test_resolve_ambiguous_clears_senses(tmp_path):
    store = make_test_store({"Fish": ["BASS"], "Music Instruments": ["GUITAR"]})
    taxonomy = TopicTaxonomy.from_master_bank({"topics": {}, "words": []})
    registry = AmbiguityRegistry.seeded()
    log = DecisionLog(tmp_path / "decisions.jsonl")
    queue = ReviewQueue()
    bass = store.get("BASS")
    bass.ambiguous_senses = ["fish", "music"]
    apply_decision(store, taxonomy, registry, log, queue,
                   ACTION_RESOLVE_AMBIGUOUS, "BASS", topic_id="fish",
                   note="fish wins")
    assert bass.ambiguous_senses == []
    assert not registry.is_ambiguous("BASS")


def test_ignore_dismisses_open_items_without_state_change(garden_world, tmp_path):
    store, taxonomy = garden_world
    registry = AmbiguityRegistry()
    log = DecisionLog(tmp_path / "decisions.jsonl")
    queue = seed_review_queue(store)
    before = store.get("HOSEMULCH").to_dict()
    open_before = {i.item_id for i in queue.open_items()}
    apply_decision(store, taxonomy, registry, log, queue,
                   ACTION_IGNORE, "HOSEMULCH", topic_id="gardening")
    assert store.get("HOSEMULCH").to_dict() == before
    assert {i.item_id for i in queue.open_items()} < open_before


def test_seed_review_queue_creates_medium_items(garden_world):
    store, _ = garden_world
    queue = seed_review_queue(store)
    items = queue.open_items(kind="word_link")
    assert any(i.word == "HOSEMULCH" and i.topic_id == "gardening" for i in items)
    # trusted-only words never enter the queue
    assert not any(i.word == "TROWEL" for i in items)
