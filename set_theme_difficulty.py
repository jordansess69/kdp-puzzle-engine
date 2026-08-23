"""Add or refresh the saved difficulty label for every usable theme JSON."""
from __future__ import annotations

import json
from pathlib import Path

from word_search_creator import THEMES_DIR, puzzle_difficulty_label


def main() -> None:
    updated = 0
    for path in THEMES_DIR.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("puzzles"), list):
            continue
        label = puzzle_difficulty_label({"puzzles": data["puzzles"]})
        if data.get("difficulty_label") != label:
            data["difficulty_label"] = label
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            updated += 1
    print(f"Updated {updated} theme file(s).")


if __name__ == "__main__":
    main()
