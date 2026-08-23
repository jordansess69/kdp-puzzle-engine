"""Build a market-informed, evergreen Word Search collection.

This creates theme JSON files only.  It never overwrites an existing book and
does not claim that any topic is guaranteed profitable: Amazon does not
publish sales or profit by niche.  Each book instead uses a current,
market-informed direction and a clean, topic-mapped Master Library selection.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
MASTER = APP_DIR / "word_banks" / "Guided_Builder_Master_Word_Bank.json"
DESTINATION = APP_DIR / "themes" / "Market Opportunity Collection"
WORDS_PER_PUZZLE = 12
PUZZLES_PER_BOOK = 48


# These are evergreen, clearly describable niches.  The source topics are
# deliberately narrow; avoid General Interest so the finished puzzles stay on
# subject.  The final title and cover claim should still be reviewed in the
# app before publication.
BOOKS = [
    ("Bible Word Search: Faith and Encouragement", "48 large-print faith-filled puzzles for quiet reflection", ["Bible and Faith", "Faith Inspiration and Kindness", "Mindfulness"], "warm-faith", "halo", "Relaxing", "Faith & Encouragement"),
    ("Mindfulness and Gratitude Word Search", "48 calming large-print puzzles for peaceful moments", ["Mindfulness", "Faith Inspiration and Kindness", "Positive Parenting"], "ocean-breeze", "halo", "Relaxing", "Mindfulness & Wellness"),
    ("Gardening Word Search: Flowers and Homegrown Fun", "48 large-print garden puzzles for plant lovers", ["Gardening", "Gardening and Garden Life", "Nature"], "spring-meadow", "gallery", "Relaxing", "Gardening & Garden Life"),
    ("National Parks Word Search: Trails and Wonders", "48 large-print outdoor puzzles for park and travel lovers", ["National Parks", "Nature", "Travel and Geography"], "forest-cabin", "gallery", "Standard", "National Parks & Outdoors"),
    ("Travel the World Word Search", "48 large-print puzzles inspired by places, journeys and discovery", ["Travel and Geography", "National Parks", "Ocean Life"], "coastal-blue", "postcard", "Standard", "Travel & World Discovery"),
    ("Ocean Life Word Search", "48 large-print sea life puzzles for adults and teens", ["Ocean Life", "Nature", "Travel and Geography"], "ocean-breeze", "wave", "Standard", "Ocean Life"),
    ("Dog Lover Word Search", "48 large-print tail-wagging puzzles for dog fans", ["Dog Breeds"], "animals", "playful", "Relaxing", "Dogs & Pets"),
    ("Cat Lover Word Search", "48 large-print cozy puzzles for cat fans", ["Cat Lover"], "lavender-pop", "playful", "Relaxing", "Cats & Pets"),
    ("Birdwatching Word Search", "48 large-print bird and backyard nature puzzles", ["Birdwatching", "Nature"], "spring-meadow", "gallery", "Relaxing", "Birdwatching & Wildlife"),
    ("Homesteading Word Search", "48 large-print puzzles about simple living and self-sufficiency", ["Homesteading", "Gardening", "Baking and Food"], "farmhouse", "classic", "Standard", "Homestead Living"),
    ("Baking and Dessert Word Search", "48 large-print sweet and savory kitchen puzzles", ["Baking and Food", "Herbs Fruits and Vegetables"], "espresso-cream", "recipe", "Relaxing", "Baking & Food"),
    ("Herbs Fruits and Vegetables Word Search", "48 large-print garden-to-table puzzles", ["Herbs Fruits and Vegetables", "Gardening", "Baking and Food"], "spring-meadow", "gallery", "Relaxing", "Garden to Table"),
    ("American History Word Search", "48 large-print puzzles about people, places and defining moments", ["American History", "Travel and Geography"], "heritage", "ticket", "Standard", "American Heritage"),
    ("World War II History Word Search", "48 large-print history puzzles for curious adult solvers", ["World War II History", "American History"], "heritage", "classic", "Challenging", "World War II History"),
    ("Space and Astronomy Word Search", "48 large-print puzzles about planets, stars and exploration", ["Space & Astronomy"], "midnight-gold", "halo", "Standard", "Space & Astronomy"),
    ("Cars Trucks and Road Trips Word Search", "48 large-print automotive puzzles for vehicle enthusiasts", ["Vehicles & Automotive", "Travel and Geography"], "retro-drive", "ticket", "Standard", "Vehicles & Automotive"),
    ("Video Game Culture Word Search", "48 large-print puzzles for retro and modern gaming fans", ["Video Games & Gaming"], "neon-arcade", "playful", "Standard", "Video Games & Gaming"),
    ("Sports and Hobbies Word Search", "48 large-print puzzles for fans of games, activities and pastimes", ["Sports and Hobbies", "Hobbies Crafts and Pastimes"], "stadium", "colorblock", "Standard", "Sports & Hobbies"),
    ("Seasonal Celebrations Word Search", "48 large-print puzzles for holidays, traditions and cozy moments", ["Holidays", "Seasonal Celebrations", "Baking and Food"], "holiday-cheer", "playful", "Relaxing", "Seasonal Celebrations"),
    ("Through the Decades Word Search", "48 large-print throwback puzzles for fans of classic culture and memories", ["Pop Culture & Entertainment", "Video Games & Gaming"], "retro-pop", "retro", "Standard", "Nostalgia Through the Decades"),
]


def clean(value: object) -> str:
    return "".join(character for character in str(value).upper() if character.isalpha())


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def select_words(topics: list[str], seed: str, master: dict[str, object]) -> list[str]:
    source_topics: dict[str, list[str]] = master["topics"]  # type: ignore[assignment]
    pool: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        for value in source_topics.get(topic, []):
            word = clean(value)
            if 3 <= len(word) <= 18 and word not in seen:
                seen.add(word)
                pool.append(word)
    required = PUZZLES_PER_BOOK * WORDS_PER_PUZZLE
    if len(pool) < required:
        raise ValueError(f"{topics} contains {len(pool)} usable words; {required} are required.")
    random.Random(seed).shuffle(pool)
    return pool[:required]


def create_book(index: int, record: tuple[object, ...], master: dict[str, object]) -> Path:
    title, subtitle, topics, palette, layout, difficulty, group = record
    words = select_words(list(topics), str(title), master)
    puzzles = []
    for number in range(PUZZLES_PER_BOOK):
        start = number * WORDS_PER_PUZZLE
        puzzles.append({
            "name": f"{title} Puzzle {number + 1:03d}",
            "words": words[start:start + WORDS_PER_PUZZLE],
        })
    data = {
        "title": title,
        "subtitle": subtitle,
        "author": "Slade Puzzles",
        "series": "Slade Puzzles Market Opportunity Collection",
        "series_rank": index,
        "audience": "Adults and Teens",
        "palette": palette,
        "cover_style": layout,
        "cover_badge": "48 LARGE-PRINT PUZZLES • NO REPEATED WORDS",
        "cover_imprint": "Slade Puzzles",
        "no_repeat_words": True,
        "difficulty_label": difficulty,
        "detected_topic": group,
        "source_word_bank": {"name": "Guided Builder Master Word Bank", "topics": topics},
        "market_research_note": "Market-informed evergreen direction; not a guarantee of sales or profit.",
        "clipart_search_terms": f"{group.lower()} friendly illustrated cover clipart transparent background",
        "puzzles": puzzles,
    }
    filename = f"market_{index:02d}_{slugify(str(title))}.json"
    path = DESTINATION / filename
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing market collection book: {path}")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    DESTINATION.mkdir(parents=True, exist_ok=True)
    created = [create_book(index, record, master) for index, record in enumerate(BOOKS, start=1)]
    print(f"Created {len(created)} market-informed theme files in {DESTINATION}")


if __name__ == "__main__":
    main()
