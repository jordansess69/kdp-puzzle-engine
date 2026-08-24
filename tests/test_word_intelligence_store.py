"""Unit tests for the Word Intelligence record model and store."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from word_intelligence import records
from word_intelligence.records import (
    CLASSIFIER_VERSION,
    APPROVED,
    EvidenceItem,
    PROPOSED,
    REJECTED,
    SIGNAL_EXISTING,
    TRUSTED,
    TopicLink,
    WordRecord,
    band_of,
)
from word_intelligence.store import (
    WordIntelligenceStore,
    make_test_store,
)


# ---------------------------------------------------------------------------
# records primitives
# ---------------------------------------------------------------------------

def test_band_boundaries():
    assert band_of(100) == "very_high"
    assert band_of(95) == "very_high"
    assert band_of(94.9) == "high"
    assert band_of(80) == "high"
    assert band_of(79.9) == "medium"
    assert band_of(60) == "medium"
    assert band_of(0) == "low"


def test_evidence_item_round_trip_and_display():
    item = EvidenceItem("lexicon", "Exact match in topic lexicon", 25)
    data = item.to_dict()
    restored = EvidenceItem.from_dict(data)
    assert restored == item
    assert str(item).startswith("+")
    assert str(EvidenceItem("neg", "blocked", -5)).startswith("-")


def test_topic_link_defaults_and_serialization():
    link = TopicLink(topic_id="gardening", status=PROPOSED, confidence=88.0,
                     evidence=[EvidenceItem(SIGNAL_EXISTING, "trusted seed", 30)])
    assert link.band == "high"
    assert link.updated_at  # auto timestamp
    data = link.to_dict()
    assert data["band"] == "high" and data["confidence"] == 88.0
    restored = TopicLink.from_dict(data)
    assert restored.topic_id == "gardening" and restored.confidence == 88.0
    assert restored.evidence[0].detail == "trusted seed"


def test_word_record_helpers():
    rec = WordRecord(normalized="TROWEL", display="trowel")
    rec.topics = [
        TopicLink("gardening", TRUSTED, 100),
        TopicLink("tools", PROPOSED, 70),
        TopicLink("kitchen", REJECTED, 40),
    ]
    assert rec.trusted_topics() == ["gardening"]
    assert [l.topic_id for l in rec.proposed_topics()] == ["tools"]
    assert not rec.is_unclassified()
    assert rec.has_rejection_for("kitchen") and not rec.has_rejection_for("tools")
    assert rec.best_confidence_for("tools") == 70
    assert rec.best_confidence_for("nope") == 0

    empty = WordRecord(normalized="ZZZ", display="zzz")
    assert empty.is_unclassified()


def test_word_record_round_trip(tmp_path):
    rec = WordRecord(
        normalized="NATIONALPARK", display="National Park", aliases=["National Park"],
        sources=["master_bank_topics"], frequency=3.9,
        grade_bands=["Grade 5 Vocabulary"],
        topics=[TopicLink("national_parks", TRUSTED, 100,
                          [EvidenceItem(SIGNAL_EXISTING, "bank", 30)])],
        ambiguous_senses=["birds"], trademark_review=True,
        last_classified="2026-08-23T00:00:00", classifier_version=CLASSIFIER_VERSION,
    )
    restored = WordRecord.from_dict(rec.to_dict())
    assert restored == rec


# ---------------------------------------------------------------------------
# store ingestion
# ---------------------------------------------------------------------------

@pytest.fixture()
def mini_bank():
    return {
        "topics": {
            "Gardening": ["TROWEL", "SEEDS", "COMPOST"],
            "Birdwatching": ["WARBLER", "BINOCULARS"],
        },
        "words": ["TROWEL", "SEEDS", "COMPOST", "WARBLER", "BINOCULARS"],
        "word_profiles": {
            "TROWEL": {"topics": ["Gardening"], "grade_bands": []},
            "WARBLER": {"topics": ["Birdwatching"]},
        },
    }


def test_ingest_master_bank_builds_trusted_records(mini_bank):
    store = WordIntelligenceStore()
    store.ingest_master_bank(mini_bank)

    rec = store.get("TROWEL")
    assert rec is not None
    assert rec.trusted_topics() == ["gardening"]
    assert rec.sources == ["master_bank_topics"]
    assert rec.topics[0].evidence[0].signal == SIGNAL_EXISTING
    assert store.topic_lexicon["gardening"] == {"TROWEL", "SEEDS", "COMPOST"}
    assert "WARBLER" in store.dictionary_words


def test_double_ingest_is_idempotent(mini_bank):
    store = WordIntelligenceStore()
    store.ingest_master_bank(mini_bank)
    first = store.get("TROWEL").to_dict()
    store.ingest_master_bank(mini_bank)
    assert store.get("TROWEL").to_dict() == first
    assert len(store.get("TROWEL").topics) == 1


def test_candidate_catalog_populates_frequency_and_sources():
    catalog = {
        "frequency_scores": {"BRISKET": 2.87, "QUIXOTIC": 1.9},
        "root_suggestions": {"BRISKET": ["Baking & Food"], "PADDLEBOARD": ["Water Sports"]},
    }
    store = WordIntelligenceStore()
    store.ingest_candidate_catalog(catalog)
    brisket = store.get("BRISKET")
    assert brisket.frequency == pytest.approx(2.87)
    assert "dwyl_root_suggestion" in brisket.sources
    assert store.get("PADDLEBOARD").sources == ["dwyl_root_suggestion"]


def test_grade_bands_attached():
    bands_doc = {"bands": {"Grade 3 Vocabulary": ["APPLE", "TIGER"]}}
    store = WordIntelligenceStore()
    store.ingest_grade_bands(bands_doc)
    apple = store.get("APPLE")
    assert apple.grade_bands == ["Grade 3 Vocabulary"]


def test_dictionary_registration_counts_new_words():
    store = WordIntelligenceStore()
    added = store.ingest_dictionary(["apple", "tiger", "Apple", "zz"])
    # 'apple' dedupes caselessly, 'zz' is too short
    assert added == 2
    assert {"APPLE", "TIGER"} <= store.dictionary_words


def test_safety_flags_applied(monkeypatch):
    monkeypatch.setattr(
        "word_intelligence.store.safety_terms",
        lambda: ({"DISNEY"}, {"FOOBAR"}),
    )
    store = WordIntelligenceStore()
    trademark, rejected = store.apply_safety_flags()
    assert (trademark, rejected) == (1, 1)
    assert store.get("DISNEY").trademark_review
    assert store.get("FOOBAR").safety_review


def test_token_index_and_variant_neighbors():
    from word_intelligence.normalization import variant_group_key

    store = make_test_store({"National Parks": ["NATIONALPARK", "RANGER"]})
    # COLOR/COLOUR are a real spelling-variant group; NATIONALPARK is not.
    store.ensure_record("COLOR", "Color")
    store.ensure_record("COLOUR", "Colour")
    assert "NATIONALPARK" in store.words_with_token("NATIONAL")
    assert store.variant_neighbors("COLOR") == {"COLOUR"}
    assert store.variant_neighbors("NATIONALPARK") == set()
    assert variant_group_key("COLOR") == variant_group_key("COLOUR")


def test_store_save_load_round_trip(tmp_path, mini_bank):
    store = WordIntelligenceStore()
    store.ingest_master_bank(mini_bank)
    store.ingest_dictionary(["BRISKET"])
    path = store.save(tmp_path / "state")
    loaded = WordIntelligenceStore.load(tmp_path / "state")
    assert path.exists()
    assert set(loaded.records) == set(store.records)
    assert loaded.get("TROWEL").to_dict() == store.get("TROWEL").to_dict()
    assert "BRISKET" in loaded.dictionary_words
    assert loaded.words_with_token("TROWEL") == {"TROWEL"}


def test_make_test_store_helper():
    store = make_test_store({"Tools": ["WRENCH"]}, extra_words=["SPROCKET"])
    assert store.get("WRENCH").trusted_topics() == ["tools"]
    assert "SPROCKET" in store.dictionary_words


# ---------------------------------------------------------------------------
# real-project integration (read-only)
# ---------------------------------------------------------------------------

def test_build_store_from_real_project_data():
    from word_intelligence.store import build_store
    from word_intelligence.taxonomy import TopicTaxonomy
    import json

    bank_path = Path(__file__).resolve().parents[1] / "word_banks" / "Guided_Builder_Master_Word_Bank.json"
    if not bank_path.exists():
        pytest.skip("master bank not present")

    taxonomy = TopicTaxonomy.from_master_bank(json.load(open(bank_path, encoding="utf-8-sig")))
    store, report = build_store(".", taxonomy=taxonomy)

    assert report["trusted_records"] > 15000
    trowel = store.get("TROWEL")
    assert trowel is not None and "gardening" in trowel.trusted_topics()
    # zipf cache attached for known words
    some_freq = sum(1 for r in store.records.values() if r.frequency is not None)
    assert some_freq > 30000
