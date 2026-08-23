"""Rank every library topic by real production capacity and evidence quality."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
MASTER = APP_DIR / "word_banks" / "Guided_Builder_Master_Word_Bank.json"
OUTPUT = APP_DIR / "word_banks" / "TOPIC_LIBRARY_READINESS.json"
STANDARD_TARGET = 48 * 12
SIGNATURE_TARGET = 100 * 12


def main() -> None:
    bank = json.loads(MASTER.read_text(encoding="utf-8"))
    candidate = bank.get("three_level_library", {}).get("candidate_catalog", {})
    suggested = candidate.get("suggested_counts_by_topic", {}) if isinstance(candidate, dict) else {}
    records = []
    for topic, capacity in bank.get("topic_capacities", {}).items():
        words = int(capacity.get("unique_words", 0))
        suggestion_count = int(suggested.get(topic, 0)) if isinstance(suggested, dict) else 0
        records.append({
            "topic": topic,
            "proven_words": words,
            "suggested_review_candidates": suggestion_count,
            "standard_48_puzzle_gap": max(0, STANDARD_TARGET - words),
            "signature_100_puzzle_gap": max(0, SIGNATURE_TARGET - words),
            "ready_for_standard": words >= STANDARD_TARGET,
            "ready_for_signature": words >= SIGNATURE_TARGET,
            "next_action": (
                "Ready for a 100-puzzle Signature Edition" if words >= SIGNATURE_TARGET else
                "Ready for a 48-puzzle standard book; expand before Signature" if words >= STANDARD_TARGET else
                "Review suggested candidates and add researched topic words before generating"
            ),
        })
    records.sort(key=lambda item: (item["ready_for_standard"], item["proven_words"], item["topic"].casefold()))
    payload = {
        "schema_version": 1,
        "created": datetime.now().isoformat(timespec="seconds"),
        "rules": {"standard_book_words": STANDARD_TARGET, "signature_book_words": SIGNATURE_TARGET},
        "summary": {
            "topics": len(records),
            "ready_for_standard": sum(bool(row["ready_for_standard"]) for row in records),
            "ready_for_signature": sum(bool(row["ready_for_signature"]) for row in records),
            "needs_expansion": sum(not bool(row["ready_for_standard"]) for row in records),
        },
        "topics": records,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}: {payload['summary']}")


if __name__ == "__main__":
    main()
