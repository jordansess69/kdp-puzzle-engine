"""Create the standard and Signature Edition Vocabulary Ladder books."""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from vocabulary_series_data import GRADE_VOCABULARY, PUZZLE_NAMES, words_for

APP_DIR = Path(__file__).resolve().parent
THEMES_DIR = APP_DIR / "themes" / "Vocabulary Ladder Collection"
MASTER_LIBRARY = APP_DIR / "word_banks" / "Guided_Builder_Master_Word_Bank.json"

BOOKS = {
    "Grade School Vocabulary": ("Vocabulary Adventures: Grade School", "A friendly word search journey for grades 3–5", "Kids & Families", "kids"),
    "Middle School Vocabulary": ("Word Wise: Middle School Vocabulary", "A confidence-building word search collection for grades 6–8", "Teens", "coastal-blue"),
    "High School Vocabulary": ("Vocabulary Mastery: High School", "A smart word search collection for grades 9–12", "Teens & Adults", "royal-plum"),
}


def puzzle_groups(topic: str) -> list[dict[str, object]]:
    words = words_for(topic)
    count = min(len(PUZZLE_NAMES), len(words) // 12)
    return [{"name": PUZZLE_NAMES[index], "words": words[index * 12:(index + 1) * 12]} for index in range(count)]


def save_book(topic: str, signature: bool) -> Path:
    title, subtitle, audience, palette = BOOKS[topic]
    if signature:
        title += " — Signature Edition"
        subtitle = subtitle.replace("word search collection", "Signature Edition word search collection")
    data: dict[str, object] = {
        "title": title,
        "subtitle": subtitle,
        "author": "Slade Puzzles",
        "audience": audience,
        "series": "Vocabulary Ladder Collection",
        "palette": palette,
        "cover_style": "halo" if signature else "gallery",
        "cover_badge": "NO REPEATED WORDS",
        "cover_imprint": "Slade Puzzles • Vocabulary Ladder",
        "series_design": {"family": "Vocabulary Ladder", "layout": "halo" if signature else "gallery", "signature_accent": bool(signature)},
        "no_repeat_words": True,
        "detected_topic": topic,
        "difficulty_label": "Relaxing" if topic == "Grade School Vocabulary" else ("Standard" if topic == "Middle School Vocabulary" else "Challenging"),
        "clipart_search_terms": f"{topic.lower()} books pencils learning illustration transparent background",
        "welcome_message": "Welcome to a word-building adventure designed to make new vocabulary feel friendly and fun.",
        "collection_features": ["Find 12 carefully chosen words in every puzzle.", "Use one favorite word in a sentence after each puzzle.", "Build confidence for reading, writing, and everyday conversation."],
        "puzzles": puzzle_groups(topic),
    }
    if signature:
        data["signature_edition"] = {
            "enabled": True,
            "passport_title": f"{topic} Puzzle Passport",
            "achievement_title": "Vocabulary Achievement",
            "achievement_message": "Every puzzle solved is another set of words ready to use.",
            "facts_title": "WORDS TO REMEMBER",
            "fact_cards": [
                "Vocabulary grows through reading, conversation, and using new words in context.",
                "Try using one favorite word from each puzzle in a sentence this week.",
                "Keep this Passport as a record of every vocabulary challenge you completed.",
            ],
            "challenge": "Word Power Challenge: use one new word in a sentence today.",
        }
    filename = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") + ".json"
    THEMES_DIR.mkdir(parents=True, exist_ok=True)
    path = THEMES_DIR / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


GRADE_LEVELS = {
    5: ("Grade School Vocabulary", "Kids & Families", "kids", "Relaxing"),
    6: ("Grade School Vocabulary Middle School Vocabulary", "Teens", "ocean-breeze", "Standard"),
    7: ("Middle School Vocabulary", "Teens", "coastal-blue", "Standard"),
    8: ("Middle School Vocabulary High School Vocabulary", "Teens", "lavender-pop", "Standard"),
    9: ("High School Vocabulary", "Teens & Adults", "royal-plum", "Challenging"),
    10: ("High School Vocabulary Middle School Vocabulary", "Teens & Adults", "midnight-gold", "Challenging"),
    11: ("High School Vocabulary Middle School Vocabulary", "Teens & Adults", "midnight-gold", "Challenging"),
    12: ("High School Vocabulary Middle School Vocabulary", "Teens & Adults", "midnight-gold", "Challenging"),
}


def grade_words(grade: int, puzzle_count: int) -> list[str]:
    """Select only from the direct, frequency-screened grade source pool."""
    master = json.loads(MASTER_LIBRARY.read_text(encoding="utf-8"))
    topic = f"Grade {grade} Vocabulary"
    pool = list(dict.fromkeys(str(word).upper() for word in master.get("topics", {}).get(topic, [])))
    needed = puzzle_count * 12
    if len(pool) < needed:
        raise ValueError(f"{topic} has {len(pool)} direct words; {needed} are required.")
    random.Random(f"Slade Puzzles {topic} v2").shuffle(pool)
    return pool[:needed]


def save_grade_book(grade: int, signature: bool) -> Path:
    _source_topics, audience, palette, difficulty = GRADE_LEVELS[grade]
    title = f"Vocabulary Ladder: Grade {grade} Word Quest"
    puzzle_count = 100 if signature else 48
    subtitle = f"{puzzle_count} vocabulary word searches to build stronger reading and writing skills"
    if signature:
        title += " - Signature Edition"
        subtitle = f"100 vocabulary word searches for stronger reading, writing and word confidence"
    words = grade_words(grade, puzzle_count)
    puzzles = [{"name": f"Grade {grade} - {PUZZLE_NAMES[index % len(PUZZLE_NAMES)]} {index + 1:03d}", "words": words[index * 12:(index + 1) * 12]} for index in range(puzzle_count)]
    data: dict[str, object] = {
        "title": title, "subtitle": subtitle, "author": "Slade Puzzles", "audience": audience,
        "series": "Vocabulary Ladder: Grades 5–12", "palette": palette, "cover_style": "halo" if signature else "gallery",
        "cover_badge": f"{puzzle_count} LARGE-PRINT PUZZLES - NO REPEATED WORDS",
        "cover_imprint": "Slade Puzzles • Vocabulary Ladder", "series_design": {"family": "Vocabulary Ladder", "layout": "halo" if signature else "gallery", "signature_accent": bool(signature)},
        "no_repeat_words": True,
        "detected_topic": f"Grade {grade} Vocabulary", "difficulty_label": difficulty,
        "clipart_search_terms": f"grade {grade} vocabulary books pencils learning illustration transparent background",
        "welcome_message": f"Welcome to the Grade {grade} Word Quest—one puzzle at a time, build words you can use with confidence.",
        "collection_features": [f"{puzzle_count} Grade {grade} vocabulary challenges with 12 words in every puzzle.", "A calm, screen-free way to practice words for reading, writing, and class discussion.", "Try the Word Power Challenge after each completed puzzle."],
        "source_word_bank": {"name": "Guided Builder Master Word Bank", "topics": [f"Grade {grade} Vocabulary"], "selection_policy": "Direct frequency-screened grade pool only"},
        "puzzles": puzzles,
    }
    if signature:
        data["signature_edition"] = {
            "enabled": True, "passport_title": f"Grade {grade} Word Passport", "achievement_title": "Vocabulary Achievement",
            "achievement_message": "Every new word is a tool you can use for life.", "facts_title": "WORDS TO REMEMBER",
            "fact_cards": ["Vocabulary grows when you read, listen, write, and use new words.", "Try using one favorite word from each puzzle in a sentence.", "This Passport celebrates your vocabulary progress."],
            "challenge": "Word Power Challenge: choose one new word and use it in a real sentence.",
        }
    folder = THEMES_DIR / "Grades 5 to 12"; folder.mkdir(parents=True, exist_ok=True)
    filename = f"vocabulary_ladder_grade_{grade}{'_signature_edition' if signature else ''}.json"
    path = folder / filename; path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    created = [save_book(topic, signature) for topic in BOOKS for signature in (False, True)]
    created += [save_grade_book(grade, signature) for grade in GRADE_LEVELS for signature in (False, True)]
    print(f"Created {len(created)} Vocabulary Ladder books in {THEMES_DIR}")


if __name__ == "__main__":
    main()
