"""Audit saved theme files without treating them as automatic master sources.

Saved files may be legacy, mixed-topic, or incomplete.  This report identifies
only candidates that are both new and supported by an existing direct-topic
keyword signal; it never silently imports anything into the Master Library.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from classify_dictionary_candidates import TOPIC_ROOTS, has_strong_root


APP_DIR = Path(__file__).resolve().parent
THEMES = APP_DIR / "themes"
MASTER = APP_DIR / "word_banks" / "Guided_Builder_Master_Word_Bank.json"
OUTPUT = APP_DIR / "word_banks" / "SAVED_THEME_SOURCE_AUDIT.json"

# Known prefix coincidences.  Prefix matching is intentionally only a research
# aid; these demonstrate why it must never be used as a direct import rule.
ROOT_FALSE_POSITIVES = {
    "Cat Lover": {"CATERPILLAR", "CATSKILLS"},
    "Birdwatching": {"FEATHEREDHAIR"},
    "Herbs Fruits and Vegetables": {"BASILICA"},
    "Sports and Hobbies": {"SPORTCOAT"},
    "Vehicles & Automotive": {"ENGINEER"},
    "Weather and Climate": {"WINDOWSHOPPING", "WEATHERED", "SNOWBOARD"},
}


def clean(value: object) -> str:
    return re.sub(r"[^A-Z]", "", str(value).upper())


def words_from_theme(payload: dict) -> set[str]:
    words: set[str] = set()
    for puzzle in payload.get("puzzles", []):
        if not isinstance(puzzle, dict):
            continue
        for key in ("words", "word_list", "answers"):
            value = puzzle.get(key, [])
            if isinstance(value, str):
                value = re.split(r"[,;\n]", value)
            if isinstance(value, list):
                words.update(clean(item) for item in value)
    return {word for word in words if 3 <= len(word) <= 18}


def target_topics(payload: dict, filename: str, available: set[str]) -> list[str]:
    haystack = " ".join([filename, str(payload.get("title", "")), str(payload.get("detected_topic", "")), str(payload.get("series", ""))]).casefold()
    return [topic for topic in TOPIC_ROOTS if topic.casefold() in haystack or any(root.casefold() in haystack for root in TOPIC_ROOTS[topic])]


def main() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    existing = set(master.get("words", []))
    available = set(master.get("topics", {}))
    results = []
    candidate_by_topic: dict[str, set[str]] = defaultdict(set)
    for path in sorted(THEMES.glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        words = words_from_theme(payload)
        targets = target_topics(payload, path.stem, available)
        new = words - existing
        root_signals = {
            word for word in new
            if any(any(has_strong_root(word, root) for root in TOPIC_ROOTS[topic]) for topic in targets)
        }
        excluded = set().union(*(ROOT_FALSE_POSITIVES.get(topic, set()) for topic in targets)) if targets else set()
        supported = root_signals - excluded
        for topic in targets:
            candidate_by_topic[topic].update(
                word for word in supported
                if any(has_strong_root(word, root) for root in TOPIC_ROOTS[topic])
            )
        results.append({
            "file": path.name,
            "title": payload.get("title", ""),
            "puzzles": len(payload.get("puzzles", [])),
            "recognized_topic_leads": targets,
            "unique_puzzle_words": len(words),
            "new_vs_master": len(new),
            "root_signal_review_candidates": len(supported),
            "review_examples": sorted(supported)[:15],
        })
    payload = {
        "schema_version": 1,
        "created": datetime.now().isoformat(timespec="seconds"),
        "policy": "Saved theme files are audited as candidate sources only. No word is imported automatically; mixed and legacy books cannot contaminate the Master Library.",
        "summary": {
            "files_audited": len(results),
            "files_with_root_signal_candidates": sum(row["root_signal_review_candidates"] > 0 for row in results),
            "supported_leads_by_topic": {topic: len(words) for topic, words in sorted(candidate_by_topic.items())},
        },
        "themes": results,
        "review_leads_by_topic": {topic: sorted(words) for topic, words in sorted(candidate_by_topic.items())},
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Audited {len(results)} saved themes; {sum(row['root_signal_review_candidates'] > 0 for row in results)} have root-signal review candidates.")


if __name__ == "__main__":
    main()
