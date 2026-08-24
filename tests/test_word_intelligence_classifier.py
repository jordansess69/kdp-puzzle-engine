"""Tests for signal evidence collection and the deterministic classifier."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from word_intelligence.classifier import (
    PROPOSAL_FLOOR,
    Classifier,
    RunStats,
    scope_records,
)
from word_intelligence.records import (
    APPROVED,
    PROPOSED,
    REJECTED,
    SIGNAL_LEXICON,
    TRUSTED,
    WordRecord,
    band_of,
)
from word_intelligence.signals import (
    POINTS_LEXICON_EXACT,
    detect_ambiguity,
    damped_total,
    familiarity_bonus,
)
from word_intelligence.store import make_test_store
from word_intelligence.taxonomy import TopicTaxonomy


@pytest.fixture()
def world():
    bank = {
        "topics": {
            "Gardening": ["TROWEL", "SEEDS", "COMPOST", "PRUNERS"],
            "Birdwatching": ["WARBLER", "BINOCULARS", "FEATHERS", "BIRDSONG"],
            "Baking & Food": ["FLOUR", "OVEN"],
        },
        "words": [],
    }
    taxonomy = TopicTaxonomy.from_master_bank(bank)
    store = make_test_store(bank["topics"])
    classifier = Classifier(store, taxonomy)
    return store, taxonomy, classifier


def _record(word, freq=None):
    return WordRecord(normalized=word, display=word.title(), frequency=freq)


# ---------------------------------------------------------------------------
# damped_total / small helpers
# ---------------------------------------------------------------------------

def test_damped_total_diminishing_returns():
    single = damped_total([POINTS_LEXICON_EXACT])
    double = damped_total([POINTS_LEXICON_EXACT, 50])
    triple = damped_total([POINTS_LEXICON_EXACT, 50, 30])
    assert single == pytest.approx(POINTS_LEXICON_EXACT)
    assert double < single + 50          # second signal discounted
    assert triple < double + 30          # third discounted more


def test_damped_total_order_independent_and_negatives_full():
    a = damped_total([50, 20, 10])
    b = damped_total([10, 50, 20])
    assert a == pytest.approx(b)
    assert damped_total([60, 20, -35]) == pytest.approx(damped_total([60, -35, 20]) )
    assert damped_total([60, -35]) == pytest.approx(60 * 1.0 - 35)


def test_familiarity_bonus_tiers():
    assert familiarity_bonus(None)[0] == 0.0
    strong = familiarity_bonus(3.5)
    ok = familiarity_bonus(2.8)
    weak = familiarity_bonus(2.0)
    assert strong[0] > ok[0] > weak[0] == 0.0
    assert strong[1] is not None and strong[1].weight > 0


def test_detect_ambiguity_requires_unrelated_strong_pairs():
    families = {"dogs": "Animals & Nature", "cats": "Animals & Nature", "baking_food": "Home"}
    ev, other = detect_ambiguity([("dogs", 90), ("cats", 85)], families)
    assert ev is None and other is None            # same family -> fine
    ev, other = detect_ambiguity([("dogs", 90), ("baking_food", 82)], families)
    assert ev is not None and other == "baking_food"
    ev, _ = detect_ambiguity([("dogs", 90), ("baking_food", 65)], families)
    assert ev is None                              # second too weak


# ---------------------------------------------------------------------------
# scoring behaviour
# ---------------------------------------------------------------------------

def test_exact_lexicon_word_is_high_and_needs_no_more(world):
    store, taxonomy, clf = world
    record = _record("TROWEL")  # no frequency info
    links = clf.score_word(record)
    gardening = next(l for l in links if l.topic_id == "gardening")
    assert gardening.status == PROPOSED
    assert gardening.confidence == pytest.approx(92)
    assert gardening.band == "high"
    assert any(e.signal == SIGNAL_LEXICON for e in gardening.evidence)


def test_exact_lexicon_plus_familiarity_reaches_very_high(world):
    store, taxonomy, clf = world
    record = _record("TROWEL", freq=3.6)  # common word
    gardening = next(l for l in clf.score_word(record) if l.topic_id == "gardening")
    assert gardening.band == "very_high"   # auto-linkable tier


def test_unknown_word_gets_no_proposals(world):
    _, _, clf = world
    assert clf.score_word(_record("QUANTUMFLIBBER")) == []


def test_phrase_token_alone_never_links(world):
    store, taxonomy, clf = world
    # BIRDSEED splits to BIRD (indexed via BIRDSONG) + SEED; weak overlap only.
    record = _record("BIRDSEED")
    links = clf.score_word(record)
    assert links == [], "weak token overlap must stay below the proposal floor"


def test_root_suggestion_with_token_overlap_proposes_for_review(world):
    store, taxonomy, clf = world
    clf.prepare(catalog={"root_suggestions": {"BIRDSEED": ["Birdwatching"]}})
    record = _record("BIRDSEED", freq=2.9)
    links = clf.score_word(record)
    birds = [l for l in links if l.topic_id == "birdwatching"]
    assert birds and birds[0].status == PROPOSED
    assert PROPOSAL_FLOOR <= birds[0].confidence < 80   # MEDIUM: human review


def test_taxonomy_relation_alone_is_insufficient(world):
    store, taxonomy, clf = world
    # Declare Gardening/Birdwatching related; FEATHERS is exact in Birdwatching.
    taxo = TopicTaxonomy.from_master_bank(
        {"topics": {}, "words": []},
        overrides={"related_pairs": [{"a": "Gardening", "b": "Birdwatching"}]})
    # Rebuild classifier sharing the same store but related taxonomy:
    from word_intelligence.taxonomy import TopicTaxonomy as TT
    full_bank = {
        "topics": {
            "Gardening": ["TROWEL", "SEEDS", "COMPOST", "PRUNERS"],
            "Birdwatching": ["WARBLER", "BINOCULARS", "FEATHERS", "BIRDSONG"],
        },
        "words": [],
    }
    taxo = TT.from_master_bank(full_bank, overrides={
        "related_pairs": [{"a": "Gardening", "b": "Birdwatching"}]})
    clf2 = Classifier(store, taxo)
    record = _record("FEATHERS")
    links = clf2.score_word(record)
    ids = {l.topic_id for l in links}
    assert "birdwatching" in ids          # exact entry -> proposed
    assert "gardening" not in ids         # mere relation never crosses floor


def test_human_rejection_blocks_new_proposals(world):
    store, taxonomy, clf = world
    record = _record("TROWEL")
    from word_intelligence.records import TopicLink
    record.topics.append(TopicLink("gardening", REJECTED, 99))
    links = clf.score_word(record)
    assert all(l.topic_id != "gardening" for l in links)


def test_approved_links_are_not_rescored(world):
    store, taxonomy, clf = world
    record = _record("TROWEL")
    from word_intelligence.records import TopicLink
    record.topics.append(TopicLink("gardening", APPROVED, 88))
    links = clf.score_word(record)
    assert all(l.topic_id != "gardening" for l in links)


def test_classify_record_merges_without_downgrading(world):
    store, taxonomy, clf = world
    record = _record("TROWEL")
    added = clf.classify_record(record)
    assert added >= 1
    first_conf = record.link_for("gardening").confidence
    # Re-running must be stable (idempotent confidence).
    clf.classify_record(record)
    assert record.link_for("gardening").confidence == first_conf
    assert record.classifier_version  # stamped


def test_safety_flag_suppresses_scores(monkeypatch, world):
    store, taxonomy, clf = world
    record = _record("TROWEL")
    record.safety_review = True
    links = clf.score_word(record)
    gardening = [l for l in links if l.topic_id == "gardening"]
    assert not gardening or gardening[0].band != "very_high"


def test_trusted_topics_survive_classification(world):
    store, taxonomy, clf = world
    record = store.get("WARBLER")   # ingested trusted
    clf.classify_record(record)
    assert "birdwatching" in record.trusted_topics()
    trusted_link = record.link_for("birdwatching")
    assert trusted_link.status == TRUSTED and trusted_link.confidence == 100.0


def test_run_stats_counts_bands(world):
    store, taxonomy, clf = world
    # Simulate dictionary-sourced copies (no trusted links yet).
    seeds = WordRecord(normalized="SEEDS", display="Seeds", frequency=3.4)
    warbler = WordRecord(normalized="WARBLER", display="Warbler")
    stats = RunStats()
    clf.classify_record(seeds, stats)
    clf.classify_record(warbler, stats)
    assert stats.words_seen == 2
    assert stats.very_high >= 1      # SEEDS: exact entry + familiar
    assert stats.high >= 1           # WARBLER: exact entry, unknown frequency
    report = stats.to_dict()
    assert report["proposals"] >= report["words_classified"]


def test_scope_records_filters():
    store = make_test_store({"Tools": ["WRENCH"]}, extra_words=["ORPHAN"])
    store.get("WRENCH").topics = []
    proven = list(scope_records(store, "proven"))
    assert {r.normalized for r in proven} == {"WRENCH"}   # has sources
    unclassified = {r.normalized for r in scope_records(store, "unclassified")}
    assert "ORPHAN" in unclassified
    stale = {r.normalized for r in scope_records(store, "stale")}
    assert stale == {"WRENCH", "ORPHAN"}
    with pytest.raises(ValueError):
        list(scope_records(store, "bogus"))
