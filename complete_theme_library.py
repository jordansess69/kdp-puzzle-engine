#!/usr/bin/env python3
"""Safely make active themes production-ready without removing their originals.

Each active theme is checked for the Slade standard: at least 48 puzzles,
at least 12 usable words in each puzzle, and no repeated word within a book.
Missing words come from the local Master Library; this script never downloads
anything and writes a timestamped backup before changing a theme file.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
THEMES = ROOT / "themes"
MASTER = ROOT / "word_banks" / "Guided_Builder_Master_Word_Bank.json"
BACKUPS = ROOT / "backups" / "theme_completion"
TARGET_PUZZLES = 48
WORDS_PER_PUZZLE = 12


TOPIC_RULES = {
    "animal": ("Animals & Pets", "Birdwatching, Backyards & Wildlife", "Backyard Birds & Nature"),
    "wildlife": ("Animals & Pets", "Birdwatching, Backyards & Wildlife", "Backyard Birds & Nature"),
    "ocean": ("Ocean Life", "Coastal & Ocean Adventure"),
    "sea": ("Ocean Life", "Coastal & Ocean Adventure"),
    "cooking": ("Food, Baking & Kitchen", "Garden to Table", "Family & Home"),
    "baking": ("Food, Baking & Kitchen", "Garden to Table", "Family & Home"),
    "food": ("Food, Baking & Kitchen", "Garden to Table", "Family & Home"),
    "travel": ("Travel & World Discovery", "Family Road Trips & Travel", "National Parks & Outdoors"),
    "road": ("Travel & World Discovery", "Family Road Trips & Travel", "Nostalgia Through the Decades"),
    "nostalgia": ("Nostalgia Through the Decades", "Throwback Pop Culture", "American Heritage"),
    "american": ("American Heritage", "Presidents, History & Americana", "Nostalgia Through the Decades"),
    "history": ("American Heritage", "Presidents, History & Americana", "American History"),
    "movie": ("Movies, TV & Entertainment", "Throwback Pop Culture", "Game Night & Pop Culture"),
    "garden": ("Garden, Flowers & Growing Things", "Garden to Table", "Homestead Living"),
    "summer": ("Travel & World Discovery", "Family Road Trips & Travel", "Coastal & Ocean Adventure"),
    "beach": ("Coastal & Ocean Adventure", "Travel & World Discovery"),
    "outdoor": ("National Parks & Outdoors", "Travel & World Discovery", "Backyard Birds & Nature"),
    "childhood": ("Nostalgia Through the Decades", "Throwback Pop Culture", "Game Night & Pop Culture"),
}


def clean(value: object) -> str:
    word = re.sub(r"[^A-Z]", "", str(value).upper())
    return word if 3 <= len(word) <= 18 else ""


def vocabulary_topics(title: str, topics: dict[str, list[str]]) -> list[str]:
    grade = re.search(r"grade\s*(\d+)", title, flags=re.I)
    if grade:
        number = int(grade.group(1))
        choices = [f"Grade {candidate} Vocabulary" for candidate in range(max(5, number - 1), min(12, number + 3) + 1)]
        choices += ["Grade School Vocabulary" if number <= 6 else "Middle School Vocabulary" if number <= 8 else "High School Vocabulary", "Vocabulary Ladder Collection"]
    elif "middle" in title.lower():
        choices = ["Middle School Vocabulary", "Grade 6 Vocabulary", "Grade 7 Vocabulary", "Grade 8 Vocabulary", "Grade 9 Vocabulary", "Vocabulary Ladder Collection"]
    elif "high" in title.lower():
        choices = ["High School Vocabulary", "Grade 9 Vocabulary", "Grade 10 Vocabulary", "Grade 11 Vocabulary", "Grade 12 Vocabulary", "Vocabulary Ladder Collection"]
    else:
        choices = ["Grade School Vocabulary", "Grade 5 Vocabulary", "Grade 6 Vocabulary", "Grade 7 Vocabulary", "Middle School Vocabulary", "Vocabulary Ladder Collection"]
    return [choice for choice in choices if choice in topics]


def source_topics(data: dict, path: Path, topics: dict[str, list[str]]) -> list[str]:
    title = f"{path.stem} {data.get('title', '')} {data.get('detected_topic', '')}".lower()
    if "vocabulary" in title or "vocab" in title:
        return vocabulary_topics(title, topics)
    selected: list[str] = []
    for keyword, matches in TOPIC_RULES.items():
        if keyword in title:
            selected.extend(topic for topic in matches if topic in topics)
    detected = str(data.get("detected_topic") or "")
    if detected in topics:
        selected.append(detected)
    return list(dict.fromkeys(selected))


def candidate_words(data: dict, path: Path, topics: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    selected = source_topics(data, path, topics)
    words: list[str] = []
    for topic in selected:
        words.extend(clean(word) for word in topics.get(topic, []))
    # A local fallback ensures an incomplete older theme can become a book, but
    # it is recorded visibly so the publisher can refine it later if desired.
    if len(set(words)) < 700:
        for topic_words in topics.values():
            words.extend(clean(word) for word in topic_words)
        selected.append("Master Library supplement")
    return list(dict.fromkeys(word for word in words if word)), selected


def complete_theme(path: Path, topics: dict[str, list[str]], backup_root: Path) -> tuple[bool, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False, f"Skipped invalid JSON: {path.name}"
    puzzles = data.get("puzzles")
    if not isinstance(puzzles, list):
        return False, f"Skipped non-book file: {path.name}"
    pool, sources = candidate_words(data, path, topics)
    used: set[str] = set()
    cursor = 0

    def next_word() -> str | None:
        nonlocal cursor
        while cursor < len(pool):
            word = pool[cursor]; cursor += 1
            if word not in used:
                used.add(word)
                return word
        return None

    changed = False
    normalized: list[dict] = []
    for index, raw in enumerate(puzzles, start=1):
        puzzle = dict(raw) if isinstance(raw, dict) else {}
        clean_words: list[str] = []
        for value in puzzle.get("words", []) if isinstance(puzzle.get("words"), list) else []:
            word = clean(value)
            if word and word not in used:
                clean_words.append(word); used.add(word)
            elif word:
                changed = True
        while len(clean_words) < WORDS_PER_PUZZLE:
            word = next_word()
            if not word:
                break
            clean_words.append(word); changed = True
        puzzle["name"] = str(puzzle.get("name") or f"{data.get('title', path.stem)} Puzzle {index:03d}")
        puzzle["words"] = clean_words
        normalized.append(puzzle)

    base_name = re.sub(r"\s+", " ", str(data.get("title") or path.stem).replace("Word Search", "")).strip() or "Word Search"
    while len(normalized) < TARGET_PUZZLES:
        group: list[str] = []
        while len(group) < WORDS_PER_PUZZLE:
            word = next_word()
            if not word:
                break
            group.append(word)
        if len(group) < WORDS_PER_PUZZLE:
            break
        normalized.append({"name": f"{base_name} Word Quest {len(normalized) + 1:03d}", "words": group})
        changed = True

    ready = len(normalized) >= TARGET_PUZZLES and all(len(item.get("words", [])) >= WORDS_PER_PUZZLE for item in normalized)
    metadata = {
        "minimum_puzzles": TARGET_PUZZLES,
        "target_words_per_puzzle": WORDS_PER_PUZZLE,
        "puzzle_count": len(normalized),
        "unique_words_in_book": len({word for item in normalized for word in item.get("words", [])}),
        "production_ready": ready,
        "completion_sources": sources,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }
    if data.get("production_readiness") != metadata:
        changed = True
    if not changed:
        return False, f"Already ready: {path.name}"
    backup = backup_root / path.relative_to(THEMES)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    data["puzzles"] = normalized
    data["no_repeat_words"] = True
    data["production_readiness"] = metadata
    if ready:
        data["cover_badge"] = str(data.get("cover_badge") or "NO REPEATED WORDS")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    state = "ready" if ready else "needs more topic words"
    return True, f"{state}: {path.name} ({len(normalized)} puzzles, {metadata['unique_words_in_book']} unique words)"


def main() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8-sig"))
    topics = {str(key): list(value) for key, value in master.get("topics", {}).items() if isinstance(value, list)}
    backup_root = BACKUPS / datetime.now().strftime("%Y%m%d_%H%M%S")
    changed = ready = 0
    reports: list[str] = []
    for path in sorted(THEMES.rglob("*.json")):
        if "Used Themes" in path.parts:
            continue
        did_change, report = complete_theme(path, topics, backup_root)
        reports.append(report)
        if did_change:
            changed += 1
        if report.startswith("ready:") or report.startswith("Already ready:"):
            ready += 1
    report_file = ROOT / "theme_completion_report.txt"
    report_file.write_text("\n".join(reports) + "\n", encoding="utf-8")
    print(f"Completed scan: {changed} theme(s) updated; {ready} active theme(s) production-ready.")
    print(f"Originals backed up under: {backup_root}")
    print(f"Report: {report_file}")


if __name__ == "__main__":
    main()
