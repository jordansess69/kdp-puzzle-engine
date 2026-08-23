"""One reusable metadata engine for every marketplace."""
from __future__ import annotations

import re


def _clean_words(value: str) -> list[str]:
    return [word for word in re.findall(r"[A-Za-z0-9]+", value.lower()) if len(word) > 2]


def _unique(values: list[str], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip()
        if cleaned and cleaned.casefold() not in seen:
            result.append(cleaned); seen.add(cleaned.casefold())
        if len(result) >= limit:
            break
    return result


def build_metadata(source: dict) -> dict:
    """Make accurate defaults once; a locked record is never overwritten automatically."""
    title = str(source.get("title") or "Untitled Puzzle Book").strip()
    subtitle = str(source.get("subtitle") or "").strip()
    author = str(source.get("author") or "Jordan M. Slade").strip()
    series = str(source.get("series") or "").strip()
    topic = str(source.get("detected_topic") or source.get("theme") or series or "themed puzzles").strip()
    puzzles = source.get("puzzles") if isinstance(source.get("puzzles"), list) else []
    count = int(source.get("puzzle_count") or len(puzzles) or 0)
    difficulty = str(source.get("difficulty_label") or "Standard").title()
    words = _clean_words(f"{topic} {title} {subtitle} {series}")
    amazon = _unique([f"{topic} word search", f"{topic} puzzle book", f"{difficulty.lower()} word puzzles", "puzzles with solutions", "screen free activity", "gift for puzzle lovers", "relaxing brain games"], 7)
    etsy = _unique([topic, "word search", "printable puzzle", "puzzle book", *words], 13)
    short = f"{count} themed puzzles with complete solutions." if count else "A themed puzzle collection with complete solutions."
    description = (f"{title}" + (f": {subtitle}" if subtitle else "") + f" is a {count}-puzzle collection inspired by {topic}. "
                   "Clear pages, satisfying word play, and complete solutions make it a relaxing screen-free activity.")
    return {"title": title, "subtitle": subtitle, "author": author, "series": series, "theme": topic,
            "audience": str(source.get("audience") or "Adults and teens"), "difficulty": difficulty,
            "short_description": short, "description": description, "amazon_keywords": amazon, "etsy_tags": etsy,
            "website_tags": _unique([topic, "word search", "puzzle book", *words], 20),
            "ingram_subjects": ["Games & Activities / Word & Word Search"],
            "barnes_noble_metadata": {"category": "Games & Activities / Word & Word Search"}}
