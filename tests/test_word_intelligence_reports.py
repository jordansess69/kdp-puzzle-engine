"""Tests for report generation and the precision-sampling gate."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from word_intelligence.precision_sampling import (
    AUTO_APPLY_PRECISION_GATE,
    draw_samples,
    gate_decision,
    score_sample,
)
from word_intelligence.records import PROPOSED, TRUSTED, TopicLink, WordRecord
from word_intelligence.reports import (
    bad_link_candidates,
    full_intelligence_report,
    topic_health_lines,
    unclassified_preview,
    write_json,
    write_review_queue_csv,
)
from word_intelligence.store import make_test_store
from word_intelligence.taxonomy import TopicTaxonomy


@pytest.fixture()
def classified_store():
    bank = {"topics": {"Gardening": ["TROWEL", "SEEDS"], "Birdwatching": ["WARBLER"]}}
    taxonomy = TopicTaxonomy.from_master_bank(bank)
    store = make_test_store(bank["topics"])
    # Spread of proposals across bands.
    for i, (word, topic, conf) in enumerate([
        ("PEAT", "gardening", 97), ("LOAM", "gardening", 92),
        ("ARBOR", "gardening", 71), ("MULCHPIT", "gardening", 55),
        ("NESTBOX", "birdwatching", 96), ("PERCHES", "birdwatching", 84),
    ]):
        rec = WordRecord(normalized=word, display=word.title())
        rec.topics.append(TopicLink(topic, PROPOSED, conf))
        store.records[word] = rec
    store.records["ORPHANWORD"] = WordRecord(normalized="ORPHANWORD", display="Orphan")
    return store, taxonomy


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

def test_write_json_stamps_and_round_trips(tmp_path):
    path = write_json("demo", {"a": 1}, tmp_path)
    assert path.exists() and path.parent == tmp_path
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"a": 1}


def test_review_queue_csv_contains_open_items(classified_store, tmp_path):
    from word_intelligence.review import seed_review_queue
    store, _ = classified_store
    queue = seed_review_queue(store)
    path = write_review_queue_csv(queue, tmp_path)
    with open(path, encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][:3] == ["item_id", "word", "topic_id"]
    assert len(rows) > 1
    words = {row[1] for row in rows[1:]}
    assert any(w in words for w in ("ARBOR", "MULCHPIT"))   # medium band only


def test_topic_health_lines_renders_table():
    rows = [{"grade": "B", "usable_words": 600,
             "display_name": "Gardening", "family": "Animals & Nature"}]
    lines = topic_health_lines(rows)
    assert lines[0].startswith("GRADE")
    assert any("Gardening" in line and "B" in line for line in lines[2:])


def test_full_report_writes_all_artifacts(classified_store, tmp_path):
    store, taxonomy = classified_store
    out = full_intelligence_report(store, taxonomy, project_root=".",
                                   report_dir=tmp_path / "reports")
    names = {Path(p).name.split("-")[0] for p in out["paths"].values()}
    assert {"coverage", "topic", "apply"} <= names
    coverage = out["coverage"]
    assert coverage["open_proposals"] >= 6


def test_unclassified_and_bad_link_previews(classified_store):
    store, _ = classified_store
    orphans = unclassified_preview(store)
    assert "ORPHANWORD" in orphans and "TROWEL" not in orphans
    bad = bad_link_candidates(store, max_confidence=60)
    assert any(b["word"] == "MULCHPIT" for b in bad)


# ---------------------------------------------------------------------------
# precision gate
# ---------------------------------------------------------------------------

def test_draw_samples_are_deterministic_and_banded(classified_store):
    store, _ = classified_store
    a = draw_samples(store, sample_size=10, seed=5)
    b = draw_samples(store, sample_size=10, seed=5)
    assert a["very_high"] == b["very_high"]
    bands = {pair[0] for pair in a["very_high"]}
    assert "PEAT" in bands          # 97 -> very_high stratum
    assert all(word != "TROWEL" for word, _, _ in a["very_high"])  # trusted excluded


def test_score_sample_precision_math():
    stratum = [("A", "t1", 96.0), ("B", "t1", 96.0), ("C", "t1", 96.0),
               ("D", "t1", 96.0)]
    judgements = {("A", "t1"): True, ("B", "t1"): True,
                  ("C", "t1"): False, ("D", "t1"): True}
    score = score_sample(stratum, judgements)
    assert score["judged"] == 4 and score["correct"] == 3
    assert score["precision"] == 75.0


def test_gate_requires_98_percent_and_enough_judgements():
    good = {"very_high": {"precision": 99.0, "judged": 50}}
    assert gate_decision(good)["auto_apply_allowed"] is True

    borderline = {"very_high": {"precision": float(AUTO_APPLY_PRECISION_GATE) - 0.5,
                                "judged": 50}}
    decision = gate_decision(borderline)
    assert decision["auto_apply_allowed"] is False
    assert "below" in decision["reason"]

    thin = {"very_high": {"precision": 100.0, "judged": 10}}
    decision = gate_decision(thin)
    assert decision["auto_apply_allowed"] is False
    assert "Insufficient" in decision["reason"]
