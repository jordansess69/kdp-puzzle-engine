"""Safely refresh active themes so a word never repeats within a book."""
from __future__ import annotations

import json
import random
import shutil
from datetime import datetime
from pathlib import Path

from word_search_creator import APP_DIR, THEMES_DIR, USED_THEMES_DIR, WORD_BANKS_DIR, saved_theme_files

MASTER_FILE = WORD_BANKS_DIR / "Guided_Builder_Master_Word_Bank.json"

# Ordered by topical closeness.  The source theme's own distinct words are
# always retained first; these groups only fill the missing unique slots.
RELATED_TOPICS = {
    "Sports and Hobbies": ["General Interest", "Pop Culture & Entertainment", "Video Games & Gaming", "Vehicles & Automotive"],
    "Travel and Geography": ["National Parks", "Nature", "Ocean Life", "General Interest", "Vehicles & Automotive"],
    "National Parks": ["Nature", "Travel and Geography", "Gardening", "Homesteading", "Ocean Life"],
    "General Interest": ["Pop Culture & Entertainment", "Video Games & Gaming", "Sports and Hobbies", "Travel and Geography", "Nature"],
    "Holidays": ["Baking and Food", "Nature", "General Interest", "Pop Culture & Entertainment"],
    "Ocean Life": ["Nature", "Travel and Geography", "National Parks", "Animals & Pets"],
    "Nature": ["National Parks", "Ocean Life", "Birdwatching", "Gardening", "Travel and Geography"],
    "Baking and Food": ["Herbs Fruits and Vegetables", "Gardening", "Homesteading", "General Interest"],
    "Bible and Faith": ["Mindfulness", "General Interest"],
    "American History": ["World War II History", "Travel and Geography", "General Interest"],
    "World War II History": ["American History", "Travel and Geography", "General Interest"],
    "Animals & Pets": ["Nature", "Ocean Life", "Birdwatching", "General Interest"],
    "Birdwatching": ["Nature", "National Parks", "Ocean Life"],
    "Gardening": ["Herbs Fruits and Vegetables", "Homesteading", "Nature", "Baking and Food"],
    "Homesteading": ["Gardening", "Herbs Fruits and Vegetables", "Nature", "Baking and Food"],
    "Mindfulness": ["Nature", "General Interest"],
    "Positive Parenting": ["General Interest", "Homesteading", "Baking and Food"],
}


def clean(word: object) -> str:
    return "".join(char for char in str(word).upper() if char.isalpha())


def unique_words(data: dict) -> list[str]:
    return list(dict.fromkeys(clean(word) for puzzle in data.get("puzzles", []) if isinstance(puzzle, dict) for word in puzzle.get("words", []) if 3 <= len(clean(word)) <= 18))


def needs_refresh(data: dict) -> bool:
    words = [clean(word) for puzzle in data.get("puzzles", []) if isinstance(puzzle, dict) for word in puzzle.get("words", [])]
    return len(words) != len(set(words))


def source_pool(data: dict, master: dict) -> tuple[list[str], list[str]]:
    topic = str(data.get("detected_topic") or "General Interest")
    topics = master.get("topics", {})
    source_names = [topic, *RELATED_TOPICS.get(topic, ["General Interest", "Nature", "Travel and Geography"])]
    pool: list[str] = unique_words(data)
    for name in source_names:
        pool.extend(topics.get(name, []))
    pool = list(dict.fromkeys(clean(word) for word in pool if 3 <= len(clean(word)) <= 18))
    return pool, source_names


def backup(paths: list[Path]) -> Path:
    root = APP_DIR / "out" / "backups" / f"no_repeat_refresh_{datetime.now():%Y%m%d_%H%M%S}"
    for path in paths:
        destination = root / path.relative_to(THEMES_DIR)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    return root


def refresh(path: Path, master: dict) -> tuple[bool, str]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    puzzles = data.get("puzzles", [])
    required = sum(len(item.get("words", [])) for item in puzzles if isinstance(item, dict))
    pool, sources = source_pool(data, master)
    if len(pool) < required:
        # A final fallback is deliberately broad but still saved in metadata so
        # the owner can review the source decision in the app later.
        pool.extend(master.get("words", []))
        pool = list(dict.fromkeys(clean(word) for word in pool if 3 <= len(clean(word)) <= 18))
        sources.append("Everything Library (capacity fallback)")
    if len(pool) < required:
        return False, f"needs {required} unique words; only {len(pool)} available"
    random.Random(f"{data.get('title', path.stem)}|no-repeat-refresh").shuffle(pool)
    offset = 0
    for puzzle in puzzles:
        if not isinstance(puzzle, dict):
            continue
        count = len(puzzle.get("words", []))
        puzzle["words"] = pool[offset:offset + count]
        offset += count
    data["no_repeat_words"] = True
    data["cover_badge"] = "NO REPEATED WORDS"
    data["no_repeat_refresh"] = {"refreshed": datetime.now().isoformat(timespec="seconds"), "sources": sources}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True, f"{required} unique words from {' + '.join(sources)}"


def main() -> None:
    master = json.loads(MASTER_FILE.read_text(encoding="utf-8-sig"))
    candidates = []
    for path in saved_theme_files():
        try:
            if needs_refresh(json.loads(path.read_text(encoding="utf-8-sig"))): candidates.append(path)
        except (OSError, json.JSONDecodeError):
            continue
    saved = backup(candidates)
    refreshed, failed = [], []
    for path in candidates:
        ok, message = refresh(path, master)
        (refreshed if ok else failed).append(f"{path.name}: {message}")
    print(f"Backup: {saved}")
    print(f"Refreshed: {len(refreshed)}")
    print(f"Failed: {len(failed)}")
    for line in failed: print(line)


if __name__ == "__main__":
    main()
