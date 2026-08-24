"""Builder-side consumption of the curated approved-links source.

Proves that human decisions survive master-bank regeneration: approved pairs
merge into generation packs additively, trademark/exclusion gates still apply,
and an absent intelligence layer never blocks a build.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_master_word_bank as bwm


def _write_links(tmp_path, links, raw_names):
    path = tmp_path / "approved_topic_links.json"
    path.write_text(json.dumps(
        {"schema_version": 1, "links": links, "topic_raw_names": raw_names}),
        encoding="utf-8")
    return path


def test_loader_tolerates_missing_file(tmp_path):
    links, names = bwm._load_approved_links(tmp_path / "absent.json")
    assert links == {} and names == {}


def test_merge_is_additive_and_gated(tmp_path):
    words_by_topic = {"Gardening": {"SEED", "TROWEL"}}
    links = {
        "Window": {"gardening": {"status": "approved"}},   # mixed case input
        "DISNEY": {"gardening": {"status": "approved"}},   # trademark-blocked
        "MOSS": {"gardening": {"status": "rejected"}},     # never merged
    }
    raw_names = {"gardening": ["Gardening", "Retired Old Name"]}

    summary = bwm.merge_approved_links(words_by_topic, links, raw_names)

    assert "WINDOW" in words_by_topic["Gardening"]
    assert "DISNEY" not in words_by_topic["Gardening"]
    assert "MOSS" not in words_by_topic["Gardening"]
    assert summary == {"approved_pairs": 2, "merged_words": 1,
                       "skipped_unknown_topic": 0}


def test_unknown_canonical_slug_is_reported_not_fatal():
    words_by_topic = {"Gardening": set()}
    summary = bwm.merge_approved_links(
        words_by_topic,
        {"ACORN": {"no_such_topic": {"status": "approved"}}},
        {})
    assert summary["skipped_unknown_topic"] == 1
    assert words_by_topic["Gardening"] == set()


def test_end_to_end_load_then_merge(tmp_path):
    path = _write_links(
        tmp_path,
        links={"RIVER": {"coastal_lake_river_life": {"status": "approved"}}},
        raw_names={"coastal_lake_river_life": ["Coastal Lake and River Life"]})
    links, names = bwm._load_approved_links(path)
    packs = {"Coastal Lake and River Life": {"HARBOR"}}
    summary = bwm.merge_approved_links(packs, links, names)
    assert packs["Coastal Lake and River Life"] == {"HARBOR", "RIVER"}
    assert summary["merged_words"] == 1
