"""Repair-engine tests: causes, inventory, dry-run plans, safe apply, gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from word_intelligence.repair import (
    CAUSE_DUPLICATE,
    CAUSE_OFF_TOPIC,
    CAUSE_TRADEMARK,
    TIER_APPROVAL,
    TIER_AUTO,
    TIER_BLOCKED,
    TIER_REVIEW,
    ThemeRepairPlan,
    WordReplacement,
    apply_plan,
    build_inventory,
    cause_for,
    classify_repair_tier,
    plan_theme_repairs,
    production_readiness,
    recommend_disposition,
)
from word_intelligence.records import PROPOSED, TRUSTED, TopicLink, WordRecord
from word_intelligence.store import make_test_store
from word_intelligence.taxonomy import TopicTaxonomy
from word_intelligence.theme_audit import WordFinding


@pytest.fixture()
def garden_store():
    bank = {"topics": {
        "Gardening": ["TROWEL", "SEEDS", "COMPOST", "PRUNERS", "MULCH", "HOSE"],
        "Birdwatching": ["WARBLER", "BINOCULARS"],
        "Baking & Food": ["FLOUR", "OVEN"],
    }}
    taxonomy = TopicTaxonomy.from_master_bank(bank)
    store = make_test_store(bank["topics"])
    for i, name in enumerate(["TROWEL", "SEEDS", "COMPOST", "PRUNERS", "MULCH",
                              "HOSE", "WEEDER", "SPADE", "RAKE", "GLOVES"]):
        record = store.get(name) or WordRecord(normalized=name, display=name.title())
        record.frequency = 3.0 + (i % 10) / 10.0
        if record.normalized not in store.records:
            record.topics.append(TopicLink("gardening", TRUSTED, 100))
            store.records[name] = record
    for name in ["PEAT", "LOAM", "ARBOR"]:
        rec = WordRecord(normalized=name, display=name.title(), frequency=3.4)
        rec.topics.append(TopicLink("gardening", PROPOSED, 93))
        store.records[name] = rec
    return store, taxonomy


def _theme(words_by_puzzle, **meta):
    puzzles = [{"name": f"Puzzle {i + 1}", "words": list(words)}
               for i, words in enumerate(words_by_puzzle)]
    data = {"title": meta.get("title", "Test Theme"), "author": "Tester",
            "palette": "Forest Green", "puzzles": puzzles}
    data.update({k: v for k, v in meta.items() if k != "title"})
    return data


# ---------------------------------------------------------------------------
# cause mapping
# ---------------------------------------------------------------------------

def test_cause_mapping_covers_failure_buckets():
    assert cause_for(WordFinding("X", "X", "off_topic", "Points elsewhere: a")) == CAUSE_OFF_TOPIC
    assert cause_for(WordFinding("X", "X", "flagged", "Trademark-review term")) == CAUSE_TRADEMARK
    assert cause_for(WordFinding("X", "X", "duplicate", "Used 3x")) == CAUSE_DUPLICATE
    assert cause_for(WordFinding("X", "X", "unverified", "...")) is None
    assert cause_for(WordFinding("X", "X", "on_topic", "")) is None


# ---------------------------------------------------------------------------
# inventory + dispositions
# ---------------------------------------------------------------------------

def test_inventory_groups_causes_and_flags_duplicate_groups(tmp_path, garden_store):
    store, taxonomy = garden_store
    good = _theme([["TROWEL", "SEEDS", "COMPOST"]], title="Good Book")
    bad = _theme([["TROWEL", "OVEN"], ["MULCH", "MULCH"]], title="Bad Book")
    good["detected_topic"] = "Gardening"
    bad["detected_topic"] = "Gardening"
    (tmp_path / "good.json").write_text(json.dumps(good), encoding="utf-8")
    (tmp_path / "bad_a.json").write_text(json.dumps(bad), encoding="utf-8")
    (tmp_path / "bad_b.json").write_text(json.dumps(bad), encoding="utf-8")

    inventory = build_inventory(tmp_path, store, taxonomy)
    by_file = {t["file"]: t for t in inventory["themes"]}
    assert by_file["good.json"]["verdict"] in ("PASS", "PASS_WITH_NOTES")
    bad_entry = by_file["bad_a.json"]
    assert CAUSE_OFF_TOPIC in bad_entry["causes"]
    assert any(w["word"] == "OVEN" for w in bad_entry["causes"][CAUSE_OFF_TOPIC])
    assert CAUSE_DUPLICATE in bad_entry["causes"]
    # Identical content -> one accidental-duplicate group; newest copy kept.
    groups = inventory["duplicate_content_groups"]
    assert len(groups) == 1
    assert set(groups[0]["files"]) == {"bad_a.json", "bad_b.json"}
    assert groups[0]["keep"] == "bad_b.json"
    assert by_file["bad_a.json"]["disposition"] == "merge_duplicate"
    # A Standard/Signature pair is NEVER an accidental duplicate.
    sig_bad = _theme([["TROWEL", "OVEN"], ["MULCH", "MULCH"]], title="Bad Sig")
    sig_bad["detected_topic"] = "Gardening"
    (tmp_path / "bad_a_signature_edition.json").write_text(
        json.dumps(sig_bad), encoding="utf-8")
    inventory2 = build_inventory(tmp_path, store, taxonomy)
    sig_entry = {t["file"]: t for t in inventory2["themes"]}
    assert sig_entry["good.json"]["disposition"] == "retain"
    pair_groups = [g for g in inventory2["duplicate_content_groups"]
                   if {"bad_a.json", "bad_a_signature_edition.json"} <= set(g["files"])]
    assert pair_groups == []


def test_disposition_rules(tmp_path):
    legacy = {"verdict": "FAIL", "word_count": 600, "targets": [],
              "bad_words_total": 100, "file": "legacy.json"}
    assert recommend_disposition(legacy, set()) == "archive_candidate"
    majority_junk = {"verdict": "FAIL", "word_count": 100, "targets": ["gardening"],
                     "bad_words_total": 90, "file": "junk.json"}
    assert recommend_disposition(majority_junk, set()) == "archive_candidate"
    structural = {"verdict": "FAIL", "word_count": 600, "targets": ["gardening"],
                  "bad_words_total": 200, "file": "structural.json"}
    assert recommend_disposition(structural, set()) == "repair_partial"
    targeted = {"verdict": "FAIL", "word_count": 600, "targets": ["gardening"],
                "bad_words_total": 20, "file": "targeted.json"}
    assert recommend_disposition(targeted, set()) == "repair"


# ---------------------------------------------------------------------------
# planning + application
# ---------------------------------------------------------------------------

def test_plan_replaces_off_topic_with_pool_word(garden_store):
    store, taxonomy = garden_store
    # OVEN is trusted to Baking & Food, so it carries real "points elsewhere"
    # evidence inside a Gardening book (unknown words stay unverified/kept).
    theme = _theme([["TROWEL", "OVEN"], ["SEEDS", "MULCH"]],
                   title="Intruder")
    theme["detected_topic"] = "Gardening"
    plan = plan_theme_repairs(theme, "memory.json", store, taxonomy)
    assert plan.replacement_count >= 1
    rep = next(r for r in plan.replacements if r.old_word == "OVEN")
    assert rep.cause == CAUSE_OFF_TOPIC
    new_data, changelog = apply_plan(theme, plan)
    flat = [w for pz in new_data["puzzles"] for w in pz["words"]]
    assert "OVEN" not in flat and rep.chosen in flat
    assert changelog and changelog[0]["action"] == "replace"


def test_plan_keeps_unverified_words_and_records_them(garden_store):
    store, taxonomy = garden_store
    # QQXYZVVM is unknown to the store: no evidence either way -> preserved.
    theme = _theme([["TROWEL", "QQXYZZVVM"]], title="Unknown")
    theme["detected_topic"] = "Gardening"
    plan = plan_theme_repairs(theme, "memory.json", store, taxonomy)
    assert plan.replacement_count == 0
    flat = [w for pz in apply_plan(theme, plan)[0]["puzzles"] for w in pz["words"]]
    assert "QQXYZZVVM" in flat


def test_plan_unresolved_when_pool_already_used(garden_store):
    store, taxonomy = garden_store
    # Baking anchor: pool is FLOUR/OVEN; both already used -> nothing fresh.
    theme = _theme([["TROWEL", "FLOUR", "OVEN"]], title="Starved")
    theme["detected_topic"] = "Baking & Food"
    plan = plan_theme_repairs(theme, "memory.json", store, taxonomy)
    assert any(u["word"] == "TROWEL" for u in plan.unresolved)
    assert not plan.auto_applicable


def test_duplicate_occurrences_removed_after_first(garden_store):
    store, taxonomy = garden_store
    theme = _theme([["TROWEL", "SEEDS", "SEEDS"], ["MULCH", "HOSE"]],
                   title="Dupes")
    theme["detected_topic"] = "Gardening"
    plan = plan_theme_repairs(theme, "memory.json", store, taxonomy)
    new_data, changelog = apply_plan(theme, plan)
    first_words = new_data["puzzles"][0]["words"]
    assert first_words.count("SEEDS") == 1
    assert len(first_words) == 2   # duplicate dropped, nothing added
    assert any(entry["action"] == "remove_duplicate" for entry in changelog)


def test_medium_confidence_blocks_auto_apply(garden_store):
    store, taxonomy = garden_store
    from word_intelligence.repair import build_topic_member_index
    # Hand-built index where every candidate is only high-band (80-94):
    # plans must refuse auto-apply and record the blocker.
    index = {"gardening": {"PEAT": 85.0, "LOAM": 82.0, "ARBOR": 81.0}}
    assert build_topic_member_index(store, taxonomy)["gardening"]["TROWEL"] == 100.0
    theme = _theme([["TROWEL", "OVEN"]], title="Med")
    theme["detected_topic"] = "Gardening"
    plan = plan_theme_repairs(theme, "memory.json", store, taxonomy,
                              member_index=index)
    assert not plan.auto_applicable
    assert plan.blockers


def test_majority_rewrite_is_never_auto_applicable(garden_store):
    store, taxonomy = garden_store
    # A book where most words point elsewhere: even with perfect candidates
    # the plan must refuse auto-apply - rewriting most of a book is curation.
    intruders = ["OVEN", "FLOUR", "WARBLER", "BINOCULARS"]
    puzzles = [[w, intruders[i % len(intruders)]] for i, w in
               enumerate(["TROWEL"] * 8)]
    theme = _theme(puzzles, title="Mostly Intruders")
    theme["detected_topic"] = "Gardening"
    plan = plan_theme_repairs(theme, "memory.json", store, taxonomy)
    share = len(plan.replacements) / 16
    assert share > 0.20
    assert not plan.auto_applicable
    assert any("human curation" in b or "human approval" in b
               for b in plan.blockers)


def test_tier_classification_boundaries():
    # Unresolved gaps always block, regardless of size.
    assert classify_repair_tier(0.01, 1, 100.0, {CAUSE_OFF_TOPIC}) == TIER_BLOCKED
    # Tiny + fully confident + benign cause -> the only auto tier.
    assert classify_repair_tier(0.05, 0, 100.0, {CAUSE_OFF_TOPIC}) == TIER_AUTO
    # Just over the auto share line -> review.
    assert classify_repair_tier(0.11, 0, 100.0, {CAUSE_OFF_TOPIC}) == TIER_REVIEW
    # Exactly at the rewrite boundary -> approval_required.
    assert classify_repair_tier(0.36, 0, 100.0, {CAUSE_OFF_TOPIC}) == TIER_APPROVAL
    # A single low-confidence swap demotes to review even when tiny.
    assert classify_repair_tier(0.03, 0, 80.0, {CAUSE_OFF_TOPIC}) == TIER_REVIEW
    # Trademark/safety causes always need human eyes, however small.
    assert classify_repair_tier(0.02, 0, 100.0, {CAUSE_TRADEMARK}) == TIER_REVIEW


def test_plan_carries_tier_and_scale_metadata(garden_store):
    store, taxonomy = garden_store
    theme = _theme([["TROWEL", "OVEN"]], title="Meta")
    theme["detected_topic"] = "Gardening"
    plan = plan_theme_repairs(theme, "memory.json", store, taxonomy)
    d = plan.to_dict()
    assert d["tier"] in (TIER_AUTO, TIER_REVIEW, TIER_APPROVAL)
    # A 1-in-2 swap is rewrite scale and must never claim auto.
    assert not plan.auto_applicable
    assert d["word_count"] >= 2
    assert d["puzzles_affected"] <= 2
    assert abs(d["replacement_share"]
               - len(plan.replacements) / d["word_count"]) < 0.01


def test_replacements_within_a_plan_never_repeat_a_chosen_word(garden_store):
    store, taxonomy = garden_store
    # Two different intruders in one book: each must get a DISTINCT
    # replacement, even though the pool ranks the same word first.
    theme = _theme([["TROWEL", "OVEN"], ["SEEDS", "FLOUR"]],
                   title="Distinct")
    theme["detected_topic"] = "Gardening"
    plan = plan_theme_repairs(theme, "memory.json", store, taxonomy)
    swaps = [r.chosen for r in plan.replacements if r.cause != CAUSE_DUPLICATE]
    assert len(swaps) == 2
    assert len(set(swaps)) == len(swaps), \
        f"plan reused a replacement word: {swaps}"


def test_apply_plan_refuses_to_starve_a_puzzle():
    data = _theme([["ECHO", "ECHO", "ECHO", "ECHO", "ECHO", "ECHO",
                    "ECHO", "ECHO", "ECHO"]], title="Thin")
    plan = ThemeRepairPlan(theme_file="x.json", title="Thin")
    for _ in range(4):
        plan.replacements.append(
            WordReplacement(puzzle_index=0, old_word="ECHO",
                            normalized="echo", cause=CAUSE_DUPLICATE,
                            reason="dup", chosen="-REMOVE-"))
    with pytest.raises(ValueError, match="below"):
        apply_plan(data, plan)


def test_production_readiness_gate(garden_store):
    store, taxonomy = garden_store
    # Register a known trademark-review term so the gate has something real
    # to catch (make_test_store does not ingest safety flags by itself).
    disney = WordRecord(normalized="DISNEY", display="Disney")
    disney.trademark_review = True
    store.records["DISNEY"] = disney

    # Varied puzzles (no repeats) drawn from the trusted/proposed garden pool.
    good = _theme([
        ["TROWEL", "SEEDS", "COMPOST"],
        ["PRUNERS", "MULCH", "HOSE"],
        ["WEEDER", "SPADE", "PEAT"],
        ["LOAM", "ARBOR", "GLOVES"],
    ], title="Ready")
    good["detected_topic"] = "Gardening"
    report = production_readiness(good, "memory.json", store, taxonomy)
    assert report["ready"] is True

    contaminated = _theme([
        ["TROWEL", "DISNEY", "COMPOST"],
        ["PRUNERS", "MULCH", "HOSE"],
        ["WEEDER", "SPADE", "PEAT"],
        ["LOAM", "ARBOR", "GLOVES"],
    ], title="Flagged")
    contaminated["detected_topic"] = "Gardening"
    report2 = production_readiness(contaminated, "memory.json", store, taxonomy)
    assert report2["ready"] is False
    assert report2["checks"]["no_trademark_flags"] is False
