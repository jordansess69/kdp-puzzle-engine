"""Build fresh Signature Edition word-search books for the theme library.

These collections deliberately use narrower angles than the earlier broad
themes so they can stand alone as distinct books in the Slade Puzzles catalog.
"""
from __future__ import annotations

import json
from pathlib import Path


THEMES = Path(__file__).resolve().parent / "themes"
AUTHOR = "Slade Puzzles"

COMMON = [
    "DISCOVER", "EXPLORE", "LEARN", "MEMORY", "JOURNEY", "FAVORITE",
    "COLLECTION", "CHALLENGE", "RELAX", "CURIOUS", "WONDER", "STORY",
]

BOOKS = [
    {
        "filename": "signature_bible_stories.json",
        "title": "Bible Stories Word Search",
        "subtitle": "60 faith-filled puzzles from beloved Bible stories",
        "series": "Signature Editions: Faith and Inspiration",
        "label": "Bible Stories",
        "count": 60,
        "palette": "bible",
        "style": "classic",
        "topic": "Bible and Faith",
        "words": ["GENESIS", "EXODUS", "NOAH", "ARK", "MOSES", "DAVID", "GOLIATH", "RUTH", "ESTHER", "DANIEL", "LION", "JONAH", "WHALE", "BETHLEHEM", "MANGER", "PARABLE", "DISCIPLES", "MIRACLE", "PSALM", "PROVERBS", "PRAYER", "GRACE", "FAITH", "HOPE"],
        "facts": ["The Bible is made up of many books, written in different literary styles.", "Bible stories are often shared across generations through reading, study, and conversation.", "Psalms, Proverbs, parables, and historical accounts each offer a different way to explore faith."],
    },
    {
        "filename": "signature_birds_of_north_america.json",
        "title": "Birds of North America Word Search",
        "subtitle": "60 colorful birdwatching puzzles for curious nature lovers",
        "series": "Signature Editions: Nature Explorer",
        "label": "North American Birds",
        "count": 60,
        "palette": "birds",
        "style": "gallery",
        "topic": "Birdwatching",
        "words": ["ROBIN", "CARDINAL", "BLUEJAY", "EAGLE", "HAWK", "FALCON", "OSPREY", "HERON", "EGRET", "OWLET", "SPARROW", "FINCH", "WARBLER", "WREN", "ORIOLE", "SWALLOW", "WOODPECKER", "HUMMINGBIRD", "MIGRATION", "FEATHER", "NEST", "WINGSPAN", "SONGBIRD", "BIRDWATCHING"],
        "facts": ["Birdwatching can be enjoyed from a backyard, park, trail, or window.", "Birds use feathers for flight, insulation, display, and protection.", "Many bird species migrate seasonally between nesting and wintering areas."],
    },
    {
        "filename": "signature_american_history_teens.json",
        "title": "US History for Teens",
        "subtitle": "48 engaging puzzles about people, places, and turning points",
        "series": "Signature Editions: American History",
        "label": "US History for Teens",
        "count": 48,
        "palette": "patriotic",
        "style": "bold",
        "topic": "American History",
        "words": ["COLONIES", "LIBERTY", "CONSTITUTION", "ELECTION", "CAPITOL", "PRESIDENT", "PIONEER", "RAILROAD", "INVENTION", "TELEGRAPH", "SUFFRAGE", "CIVILRIGHTS", "APOLLO", "MOONLANDING", "NATIONALPARK", "IMMIGRATION", "MONUMENT", "MUSEUM", "FRONTIER", "FREEDOM", "CITIZEN", "DEMOCRACY", "HERITAGE", "TIMELINE"],
        "facts": ["History is often studied through primary sources such as letters, photos, newspapers, and objects.", "A timeline helps show the order in which events happened.", "American history includes many perspectives, communities, and regional stories."],
    },
    {
        "filename": "signature_american_history_defining_moments.json",
        "title": "US History for Adults",
        "subtitle": "60 defining-moments puzzles for history lovers",
        "series": "Signature Editions: American History",
        "label": "US History for Adults",
        "count": 60,
        "palette": "midnight-gold",
        "style": "ticket",
        "topic": "American History",
        "words": ["REVOLUTION", "UNION", "RECONSTRUCTION", "INDUSTRY", "DEPRESSION", "NEWDEAL", "SUFFRAGE", "JAZZAGE", "DUSTBOWL", "CIVILRIGHTS", "VOTING", "SUPREMECOURT", "SPACEPROGRAM", "INTERSTATE", "CONSERVATION", "LABORMOVEMENT", "IMMIGRATION", "JOURNALISM", "LANDMARK", "ARCHIVE", "LEGISLATURE", "INNOVATION", "HERITAGE", "DEBATE"],
        "facts": ["Historical interpretation considers evidence, context, and differing viewpoints.", "Museums and archives preserve records that help people study the past.", "Major national events are often experienced differently by people in different places and communities."],
    },
    {
        "filename": "signature_wwii_history_for_men.json",
        "title": "World War II History for Men",
        "subtitle": "60 military-history puzzles about service, strategy, and home fronts",
        "series": "Signature Editions: Military History",
        "label": "World War II History",
        "count": 60,
        "palette": "forest-cabin",
        "style": "stripe",
        "topic": "World War II History",
        "words": ["ALLIES", "AXIS", "EUROPE", "PACIFIC", "D-DAY", "NORMANDY", "MIDWAY", "IWOJIMA", "BATTLESHIP", "AIRCRAFT", "SUBMARINE", "RADAR", "CODEBREAKERS", "RESISTANCE", "RATIONS", "HOMEFRONT", "LIBERATION", "VETERANS", "MEDICS", "PARATROOPERS", "CONVOY", "VICTORY", "MEMORIAL", "HISTORY"],
        "facts": ["World War II affected military personnel, civilians, industry, and families across the world.", "The home front included factory work, rationing, volunteer efforts, and community support.", "Museums, memorials, and oral histories help preserve personal stories from the era."],
    },
    {
        "filename": "signature_christmas_traditions.json",
        "title": "Christmas Traditions Word Search",
        "subtitle": "60 cozy holiday puzzles for joyful winter moments",
        "series": "Signature Editions: Seasonal Celebrations",
        "label": "Christmas Traditions",
        "count": 60,
        "palette": "christmas",
        "style": "playful",
        "topic": "Holidays",
        "words": ["ORNAMENT", "WREATH", "STOCKING", "CAROL", "CANDLE", "GINGERBREAD", "COCOA", "MISTLETOE", "SNOWFLAKE", "EVERGREEN", "NATIVITY", "SLEIGH", "REINDEER", "FIREPLACE", "PRESENT", "HOLLY", "JINGLE", "TRADITION", "FAMILY", "COOKIE", "WONDER", "JOYFUL", "WINTER", "CELEBRATE"],
        "facts": ["Christmas traditions can include foods, music, decorations, gatherings, and acts of giving.", "Holiday customs vary widely by family, region, and culture.", "A puzzle book can make a simple, screen-free addition to a winter gathering."],
    },
    {
        "filename": "signature_great_journeys.json",
        "title": "Great Journeys Word Search",
        "subtitle": "60 travel-inspired puzzles for explorers at heart",
        "series": "Signature Editions: Explore and Discover",
        "label": "Great Journeys",
        "count": 60,
        "palette": "coastal-blue",
        "style": "sunburst",
        "topic": "Travel and Geography",
        "words": ["PASSPORT", "AIRPORT", "TRAIN", "HIGHWAY", "MAP", "ATLAS", "COMPASS", "SUITCASE", "BACKPACK", "JOURNEY", "LANDMARK", "MUSEUM", "MARKET", "MOUNTAIN", "COASTLINE", "ISLAND", "CAPITAL", "VILLAGE", "ROADTRIP", "POSTCARD", "ITINERARY", "ADVENTURE", "EXPLORER", "DESTINATION"],
        "facts": ["Travel can include nearby day trips as well as faraway destinations.", "Maps, guidebooks, and local museums can add context to a journey.", "Keeping a travel journal is one way to remember places, sounds, and small discoveries."],
    },
    {
        "filename": "signature_all_star_sports.json",
        "title": "All-Star Sports Word Search",
        "subtitle": "60 action-packed puzzles for sports fans",
        "series": "Signature Editions: Hobbies and Interests",
        "label": "All-Star Sports",
        "count": 60,
        "palette": "sports",
        "style": "bold",
        "topic": "Sports and Hobbies",
        "words": ["BASEBALL", "BASKETBALL", "FOOTBALL", "SOCCER", "HOCKEY", "TENNIS", "GOLF", "SWIMMING", "RUNNING", "CYCLING", "SKATING", "VOLLEYBALL", "ATHLETE", "COACH", "TEAMWORK", "STADIUM", "SCOREBOARD", "CHAMPION", "TOURNAMENT", "TRAINING", "ENDURANCE", "SEASON", "WHISTLE", "MEDAL"],
        "facts": ["Sports can be enjoyed as a player, spectator, volunteer, coach, or fan.", "Team sports often depend on communication, practice, and shared strategy.", "Individual sports can build focus, confidence, and personal goal setting."],
    },
    {
        "filename": "signature_natures_wonders.json",
        "title": "Nature's Wonders Word Search",
        "subtitle": "60 peaceful puzzles inspired by the natural world",
        "series": "Signature Editions: Nature Explorer",
        "label": "Nature's Wonders",
        "count": 60,
        "palette": "nature",
        "style": "halo",
        "topic": "Nature",
        "words": ["WATERFALL", "MEADOW", "FOREST", "CANYON", "GLACIER", "RAINBOW", "THUNDER", "WILDFLOWER", "BUTTERFLY", "DRAGONFLY", "MOUNTAIN", "RIVER", "OCEAN", "DESERT", "SUNRISE", "MOONLIGHT", "STARGAZING", "SEASHELL", "PINECONE", "FERN", "MOSS", "TRAIL", "WILDLIFE", "WONDER"],
        "facts": ["Nature can be explored in a local park, garden, neighborhood, or national park.", "Seasonal changes affect plants, animals, weather, and daylight.", "Observing nature closely can turn an ordinary walk into a small adventure."],
    },
    {
        "filename": "signature_flavors_of_the_world.json",
        "title": "Flavors of the World Word Search",
        "subtitle": "60 delicious puzzles for curious food lovers",
        "series": "Signature Editions: Food and Home",
        "label": "Flavors of the World",
        "count": 60,
        "palette": "food",
        "style": "colorblock",
        "topic": "Baking and Food",
        "words": ["SPICES", "BASIL", "GINGER", "SAFFRON", "CINNAMON", "NOODLES", "RICE", "BREAD", "SOUP", "SALAD", "DUMPLING", "TACO", "CURRY", "PASTA", "OLIVE", "LEMON", "GARLIC", "MARKET", "RECIPE", "KITCHEN", "FLAVOR", "SAVORY", "SWEET", "FEAST"],
        "facts": ["Food traditions often reflect local ingredients, climate, migration, and family customs.", "Spices and herbs can add aroma, color, and flavor to a meal.", "Trying a new recipe can be a simple way to learn about another place or tradition."],
    },
]


def clean(word: str) -> str:
    return "".join(char for char in word.upper() if char.isalpha())


def make_puzzles(label: str, words: list[str], count: int) -> list[dict[str, object]]:
    bank: list[str] = []
    for word in words + COMMON:
        cleaned = clean(word)
        if cleaned and cleaned not in bank:
            bank.append(cleaned)
    puzzles: list[dict[str, object]] = []
    for number in range(1, count + 1):
        start = ((number - 1) * 5) % len(bank)
        selected: list[str] = []
        for offset in range(len(bank)):
            candidate = bank[(start + offset) % len(bank)]
            if candidate not in selected:
                selected.append(candidate)
            if len(selected) == 12:
                break
        puzzles.append({"name": f"{label} Puzzle {number:03d}", "words": selected})
    return puzzles


def main() -> None:
    THEMES.mkdir(exist_ok=True)
    for book in BOOKS:
        count = int(book["count"])
        data = {
            "title": book["title"],
            "subtitle": book["subtitle"],
            "author": AUTHOR,
            "series": book["series"],
            "palette": book["palette"],
            "cover_style": book["style"],
            "detected_topic": book["topic"],
            "clipart_search_terms": f"{book['topic']} illustration clipart transparent background",
            "signature_edition": {
                "enabled": True,
                "passport_title": f"{book['label']} Passport",
                "achievement_title": "Signature Edition",
                "achievement_message": "A calm challenge, one puzzle at a time.",
                "facts_title": "DID YOU KNOW?",
                "fact_cards": book["facts"],
            },
            "puzzles": make_puzzles(str(book["label"]), list(book["words"]), count),
        }
        path = THEMES / str(book["filename"])
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Created {path.name} ({count} puzzles)")


if __name__ == "__main__":
    main()
