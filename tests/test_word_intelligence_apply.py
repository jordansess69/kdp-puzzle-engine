"""Apply-engine safety tests: dry-run default, snapshots, rollback."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from word_intelligence.apply_engine import (
    apply_approved_links,
    collect_decisions,
    latest_snapshot,
    load_approved_links,
    plan_apply,
    rollback,
    snapshot_files,
)
from word_intelligence.records import APPROVED, PROPOSED, REJECTED, TopicLink, WordRecord
from word_intelligence.review import (
    ACTION_APPROVE,
    ACTION_MOVE,
    ACTION_REJECT,
    DecisionLog,
    ReviewQueue,
    apply_decision,
)
from word_intelligence.store import make_test_store
from word_intelligence.taxonomy import TopicTaxonomy


def _store_with_decisions():
    bank = {"topics": {"Gardening": ["TROWEL"], "Birdwatching": ["WARBLER"]}}
    taxonomy = TopicTaxonomy.from_master_bank(bank)
    store = make_test_store(bank["topics"])
    log = DecisionLog(Path(__file__).parent / "_tmp_nothing.jsonl")
    queue = ReviewQueue()
    apply_decision(store, taxonomy, {}, log, queue,
                   ACTION_APPROVE, "MOSS", topic_id="gardening", note="fits")
    apply_decision(store, taxonomy, {}, log, queue,
                   ACTION_REJECT, "WARBLER", topic_id="gardening", note="nope")
    return store, taxonomy


def test_collect_decisions_requires_human_evidence_for_rejections():
    store, _ = _store_with_decisions()
    decisions = collect_decisions(store)
    assert decisions["MOSS"]["gardening"]["status"] == APPROVED
    assert decisions["WARBLER"]["gardening"]["status"] == REJECTED

    # A classifier-only rejection must NOT enter the curated source.
    plain = WordRecord(normalized="ACORN", display="Acorn")
    plain.topics.append(TopicLink("gardening", REJECTED, 40))
    store.records["ACORN"] = plain
    assert "ACORN" not in collect_decisions(store)


def test_plan_reports_counts_without_writing():
    store, _ = _store_with_decisions()
    plan = plan_apply(store)
    assert plan["approved_pairs"] == 1
    assert plan["rejected_pairs"] == 1
    assert plan["words_with_decisions"] == 2


def test_dry_run_is_default_and_writes_nothing(tmp_path):
    store, _ = _store_with_decisions()
    result = apply_approved_links(store, project_root=tmp_path)  # dry_run defaults True
    assert result.dry_run is True
    assert not Path(result.output_path).exists()
    assert result.would_write == [result.output_path]
    # explicit dry-run flag behaves the same
    result2 = apply_approved_links(store, project_root=tmp_path, dry_run=True)
    assert not Path(result2.output_path).exists()


def test_apply_writes_validated_curated_source(tmp_path):
    store, _ = _store_with_decisions()
    state_dir = tmp_path / "word_banks" / "word_intelligence"
    state_dir.mkdir(parents=True)

    # Pre-existing file must be snapshotted before overwrite.
    out_path = state_dir / "approved_topic_links.json"
    out_path.write_text('{"links": {}}', encoding="utf-8")

    result = apply_approved_links(store, project_root=tmp_path,
                                  state_dir=state_dir, dry_run=False)
    assert result.validated and not result.errors
    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert set(data["links"]) == {"MOSS", "WARBLER"}
    assert data["links"]["MOSS"]["gardening"]["status"] == APPROVED
    assert latest_snapshot(state_dir) is not None
    assert Path(result.snapshot_dir).exists()


def test_snapshot_manifest_and_rollback_round_trip(tmp_path):
    target = tmp_path / "data.json"
    target.write_text('{"v": 1}', encoding="utf-8")
    snap = snapshot_files([target], tmp_path / "snaps", label="test")

    manifest = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    original_sha = manifest["files"]["data.json"]["sha256"]
    assert len(original_sha) == 64

    target.write_text('{"v": 2, "corrupted": true}', encoding="utf-8")
    restored = rollback(snap)
    assert restored == [str(target)]
    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 1}

    # Tampering with the snapshot aborts the restore.
    (snap / "data.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(IOError):
        rollback(snap)


def test_validation_failure_triggers_automatic_rollback(tmp_path, monkeypatch):
    store, _ = _store_with_decisions()
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)

    calls = {"n": 0}
    real_replace = __import__("os").replace

    def flaky_replace(src, dst):
        # Let the atomic rename happen but corrupt content beforehand by
        # making validation read a broken payload: simulate by writing junk.
        with open(dst, "w", encoding="utf-8") as handle:
            handle.write("{ this is not json")
        calls["n"] += 1

    monkeypatch.setattr("word_intelligence.apply_engine.os.replace", flaky_replace)
    result = apply_approved_links(store, project_root=tmp_path,
                                  state_dir=state_dir, dry_run=False)
    monkeypatch.setattr("word_intelligence.apply_engine.os.replace", real_replace)

    assert not result.validated
    assert any("Validation failed" in e for e in result.errors)
    assert any("Rolled back" in e for e in result.errors)


def test_load_approved_links_tolerates_missing_or_broken(tmp_path):
    assert load_approved_links(tmp_path) == {}
    path = tmp_path / "word_banks" / "word_intelligence" / "approved_topic_links.json"
    path.parent.mkdir(parents=True)
    path.write_text("not json at all", encoding="utf-8")
    assert load_approved_links(tmp_path) == {}


def test_payload_carries_topic_raw_names_for_builder(tmp_path):
    store, taxonomy = _store_with_decisions()
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)

    result = apply_approved_links(store, project_root=tmp_path,
                                  state_dir=state_dir, dry_run=False,
                                  taxonomy=taxonomy)
    assert result.validated
    data = json.loads(Path(result.output_path).read_text(encoding="utf-8-sig"))
    # The builder maps canonical ids back to master-bank raw pack names.
    assert data["topic_raw_names"]["gardening"] == ["Gardening"]
    # Without a taxonomy the map is simply empty - never an error.
    result2 = apply_approved_links(store, project_root=tmp_path,
                                   state_dir=tmp_path / "state2", dry_run=False)
    data2 = json.loads(Path(result2.output_path).read_text(encoding="utf-8-sig"))
    assert data2["topic_raw_names"] == {}
