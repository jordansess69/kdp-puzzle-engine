"""Synchronize Master Library topic lists back into every word profile.

This is intentionally additive: it never removes a topic or word, and writes a
timestamped backup before replacing the library file.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LIBRARY = ROOT / "word_banks" / "Guided_Builder_Master_Word_Bank.json"


def clean(value: object) -> str:
    return re.sub(r"[^A-Z]", "", str(value).upper())


def main() -> None:
    data = json.loads(LIBRARY.read_text(encoding="utf-8-sig"))
    topics = data.get("topics") if isinstance(data.get("topics"), dict) else {}
    profiles = data.get("word_profiles") if isinstance(data.get("word_profiles"), dict) else {}
    backup = LIBRARY.with_name(f"Guided_Builder_Master_Word_Bank.before_topic_link_sync_{datetime.now():%Y%m%d_%H%M%S}.json")
    shutil.copy2(LIBRARY, backup)
    linked = 0
    for topic, values in topics.items():
        if not isinstance(values, list):
            continue
        for raw in values:
            word = clean(raw)
            if not word:
                continue
            profile = profiles.setdefault(word, {"topics": [], "families": [], "related_topics": [], "related_families": []})
            if not isinstance(profile, dict):
                profile = {"topics": [], "families": [], "related_topics": [], "related_families": []}; profiles[word] = profile
            for key in ("topics", "related_topics"):
                current = profile.get(key) if isinstance(profile.get(key), list) else []
                if topic not in current:
                    profile[key] = [*current, topic]; linked += 1
    data["word_profiles"] = profiles
    capacities = data.get("topic_capacities") if isinstance(data.get("topic_capacities"), dict) else {}
    for topic, values in topics.items():
        capacity = capacities.setdefault(topic, {})
        if isinstance(capacity, dict):
            capacity["unique_words"] = len({clean(value) for value in values if clean(value)})
    data["topic_capacities"] = capacities
    temporary = LIBRARY.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(LIBRARY)
    print(f"Linked {linked} missing topic references across {len(profiles)} word profiles.")
    print(f"Backup: {backup.name}")


if __name__ == "__main__":
    main()
