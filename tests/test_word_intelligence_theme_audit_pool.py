"""Theme audit + word pool builder tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from word_intelligence.pool_builder import (
    DIFFICULTY_MIN_ZIPF,
    PoolRequest,
    build_word_pool,
    collect_eligible_words,
)
from word_intelligence.records import PROPOSED, TRUSTED, TopicLink, WordRecord
from word_intelligence.store import make_test_store
from word_intelligence.taxonomy import TopicTaxonomy
from word_intelligence.theme_audit import (
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_PASS_WITH_NOTES,
    VERDICT_REVIEW_REQUIRED,
    audit_all_themes,
    audit_theme,
    resolve_target_topics,
)


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
                              "HOSE", "WEEDER", "SPADE", "Rake".upper(), "GLOVES"]):
        record = store.get(name) or WordRecord(normalized=name, display=name.title())
        record.frequency = 3.0 + (i % 10) / 10.0
        if record not in store.records.values():
            link = TopicLink("gardening", TRUSTED, 100)
            record.topics.append(link)
            store.records[name] = record
    # A batch of strong proposals to enrich the pool.
    for name in ["PEAT", "LOAM", "ARBOR"]:
        rec = WordRecord(normalized=name, display=name.title(), frequency=3.4)
        rec.topics.append(TopicLink("gardening", PROPOSED, 93))
        store.records[name] = rec
    return store, taxonomy


# ---------------------------------------------------------------------------
# theme audit
# ---------------------------------------------------------------------------

def _theme(words_by_puzzle, **meta):
    body = {
        "title": meta.pop("title", "Garden Time"),
        "puzzles": [{"name": f"P{i+1}", "words": words}
                    for i, words in enumerate(words_by_puzzle)],
        "source_word_bank": {"topics": ["Gardening"]},
    }
    body.update(meta)
    return body


def test_resolve_topic_prefers_source_word_bank(garden_store):
    _, taxonomy = garden_store
    theme = _theme([["A"]], source_word_bank={"topics": ["Gardening"]},
                   detected_topic="Baking & Food")
    targets, how = resolve_target_topics(theme, taxonomy)
    assert targets == ["gardening"] and how == "source_word_bank"


def test_resolve_topic_falls_back_to_detected_then_title(garden_store):
    _, taxonomy = garden_store
    theme_detected = _theme([["A"]], source_word_bank=None,
                            detected_topic="Birdwatching")
    targets, how = resolve_target_topics(theme_detected, taxonomy)
    assert targets == ["birdwatching"] and how == "detected_topic"

    unresolved = _theme([["A"]], source_word_bank=None,
                        title="Completely Unrelated Title Here")
    targets2, how2 = resolve_target_topics(unresolved, taxonomy)
    assert targets2 == [] and how2 == "unresolved"


def test_audit_flags_off_topic_and_weak_words(garden_store):
    store, taxonomy = garden_store
    theme = _theme([
        ["TROWEL", "SEEDS", "OVEN"],          # OVEN belongs to Baking
        ["COMPOST", "ZZZQX", "WARBLER"],      # unknown word + other topic's word
    ])
    report = audit_theme(theme, "memory.json", store, taxonomy)
    by_word = {f.normalized: f for f in report.findings}
    assert by_word["TROWEL"].status == "on_topic"
    assert by_word["OVEN"].status == "off_topic"      # evidence points elsewhere
    assert by_word["ZZZQX"].status == "unverified"    # no evidence either way
    assert by_word["WARBLER"].status == "off_topic"
    counts = {k: sum(1 for f in report.findings if f.status == k)
              for k in ("on_topic", "off_topic", "unverified")}
    assert counts["on_topic"] == 3 and counts["off_topic"] == 2
    assert counts["unverified"] == 1


def test_audit_detects_duplicates_within_theme(garden_store):
    store, taxonomy = garden_store
    theme = _theme([["TROWEL", "SEEDS"], ["TROWEL", "COMPOST"]])
    report = audit_theme(theme, "memory.json", store, taxonomy)
    dup = next(f for f in report.findings if f.normalized == "TROWEL")
    assert dup.status == "duplicate" and "2x" in dup.detail


def test_audit_suggests_replacements_from_pool(garden_store):
    store, taxonomy = garden_store
    theme = _theme([["TROWEL", "OVEN"]])   # one bad word
    report = audit_theme(theme, "memory.json", store, taxonomy)
    assert any(f.normalized == "OVEN" and f.status == "off_topic"
               for f in report.findings)
    replacements = report.suggestions.get("OVEN")
    if replacements:
        assert all(r != "OVEN" for r in replacements)
        assert all(r not in {"TROWEL"} for r in replacements)


def test_verdict_ladder(garden_store):
    store, taxonomy = garden_store
    clean = audit_theme(_theme([["TROWEL", "SEEDS"]]), "a.json", store, taxonomy)
    assert clean.verdict == VERDICT_PASS

    notes = audit_theme(
        _theme([["TROWEL", "SEEDS", "MYSTERYWEAKWORD"]]), "b.json", store, taxonomy)
    assert notes.verdict == VERDICT_PASS_WITH_NOTES

    off = audit_theme(_theme([["OVEN", "FLOUR", "WARBLER"]]), "c.json", store, taxonomy)
    assert off.verdict == VERDICT_FAIL

    unresolvable = audit_theme({"title": "Mystery", "puzzles": []}, "d.json",
                               store, taxonomy)
    assert unresolvable.verdict == VERDICT_REVIEW_REQUIRED


def test_audit_report_serializes(garden_store):
    store, taxonomy = garden_store
    report = audit_theme(_theme([["TROWEL", "OVEN"]]), "x.json", store, taxonomy)
    data = report.to_dict()
    for key in ("theme_file", "verdict", "counts", "findings"):
        assert key in data
    assert data["counts"]["on_topic"] >= 1


def test_audit_all_themes_summarizes(tmp_path, garden_store):
    store, taxonomy = garden_store
    (tmp_path / "good.json").write_text(
        '{"title":"G","source_word_bank":{"topics":["Gardening"]},'
        '"puzzles":[{"words":["TROWEL"]}]}', encoding="utf-8")
    (tmp_path / "bad.json").write_text("{{{ broken", encoding="utf-8")
    summary = audit_all_themes(tmp_path, store, taxonomy)
    assert summary["audited"] == 1
    assert summary["skipped_unreadable"] == 1
    assert summary["reports"][0].verdict == VERDICT_PASS


# ---------------------------------------------------------------------------
# pool builder
# ---------------------------------------------------------------------------

def test_builds_disjoint_no_repeat_puzzles(garden_store):
    store, taxonomy = garden_store
    request = PoolRequest(topic_id="gardening", puzzle_count=2,
                          words_per_puzzle=6, seed=11)
    result = build_word_pool(store, taxonomy, request)
    assert result.shortfall == 0
    assert len(result.puzzles) == 2
    flat = [w for p in result.puzzles for w in p]
    assert len(flat) == len(set(flat)) == 12          # fully disjoint
    assert all(len(p) == 6 for p in result.puzzles)


def test_deterministic_with_seed(garden_store):
    store, taxonomy = garden_store
    request_a = PoolRequest(topic_id="gardening", puzzle_count=2,
                            words_per_puzzle=5, seed=42)
    request_b = PoolRequest(topic_id="gardening", puzzle_count=2,
                            words_per_puzzle=5, seed=42)
    a = build_word_pool(store, taxonomy, request_a)
    b = build_word_pool(store, taxonomy, request_b)
    assert [sorted(p) for p in a.puzzles] == [sorted(p) for p in b.puzzles]


def test_shortfall_is_explicit_never_silent(garden_store):
    store, taxonomy = garden_store
    request = PoolRequest(topic_id="gardening", puzzle_count=50,
                          words_per_puzzle=12, seed=7)
    result = build_word_pool(store, taxonomy, request)
    assert result.puzzles == [] or len(result.puzzles) < 50
    assert result.shortfall > 0
    assert any("short" in w.lower() for w in result.warnings)
    assert result.capacity["no_repeat_12_word_puzzles"] >= 1


def test_difficulty_gate_blocks_obscure_words():
    from word_intelligence.pool_builder import _difficulty_ok
    obscure = WordRecord(normalized="QUAZGIMBLE", display="Quazgimble", frequency=1.9)
    ok, reason = _difficulty_ok(obscure, "easy")
    assert not ok and "zipf" in reason
    common = WordRecord(normalized="GARDEN", display="Garden", frequency=4.2)
    ok2, _ = _difficulty_ok(common, "easy")
    assert ok2
    flagged = WordRecord(normalized="DISNEY", display="Disney", frequency=4.9,
                         safety_review=True)
    ok3, reason3 = _difficulty_ok(flagged, "medium")
    assert not ok3 and reason3 == "safety"


def test_series_context_excludes_sibling_book_words(garden_store):
    store, taxonomy = garden_store
    used_up = sorted({r.normalized for r in store.records.values()
                      if r.link_for("gardening")})[:8]
    request = PoolRequest(topic_id="gardening", puzzle_count=1,
                          words_per_puzzle=6, series_context=used_up, seed=3)
    result = build_word_pool(store, taxonomy, request)
    for puzzle in result.puzzles:
        assert not (set(puzzle) & set(used_up))


def test_roles_present_in_eligible_collection(garden_store):
    store, taxonomy = garden_store
    request = PoolRequest(topic_id="gardening", puzzle_count=1, words_per_puzzle=5)
    roles = collect_eligible_words(store, taxonomy, request)
    assert roles["anchor"], "trusted familiar words must anchor"
    assert roles["support"] or roles["specialty"]
