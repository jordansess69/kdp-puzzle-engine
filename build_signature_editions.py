"""Enrich existing themes and create new self-contained Signature Edition themes."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "themes"

NEW_BOOKS = [
    ("Homesteading Word Search", "60 self-sufficient living word search puzzles", "forest-cabin", "gallery", "Homestead Skills Passport", "Homestead Explorer", "Celebrate every small skill learned along the way.", ["Homesteading often combines food growing, food preservation, practical skills, and care for home resources.", "Extension services are a reliable local source for region-specific growing and food-safety guidance.", "Keeping a simple garden or harvest journal helps record what works in your own climate."], ["CANNING", "PRESERVING", "CHICKENCOOP", "RAISEDBED", "COMPOST", "RAINBARREL", "PANTRY", "ORCHARD", "BEESWAX", "SEEDSTART", "ROOTCELLAR", "SOURDOUGH", "FORAGING", "FIREWOOD", "GOAT", "HEN", "HARVEST", "HOMESTEAD"]),
    ("Signature Gardening Word Search", "60 peaceful garden word search puzzles", "spring-meadow", "gallery", "Garden Discovery Passport", "Garden Companion", "Enjoy each season, one page and one puzzle at a time.", ["A basic vegetable garden plan includes site selection, soil preparation, planting, maintenance, and harvest.", "Many herbs can be grown at home, including in containers or sunny indoor spaces.", "Local Extension resources can help gardeners choose varieties for their growing conditions."], ["SEEDLING", "SUNFLOWER", "TROWEL", "COMPOST", "GREENHOUSE", "WATERINGCAN", "MARIGOLD", "TOMATO", "BASIL", "LAVENDER", "POLLINATOR", "MULCH", "SOIL", "ROSE", "PEONY", "HARVEST", "GARDEN", "WILDFLOWER"]),
    ("Herbs Fruits and Vegetables Word Search", "60 fresh garden word search puzzles", "food", "ticket", "Grow and Harvest Passport", "Kitchen Garden Explorer", "Celebrate the colors, flavors, and skills of a home garden.", ["Home gardens can include annual vegetables along with perennial foods such as berries, rhubarb, and asparagus.", "Herbs are commonly grown at home for fresh flavor and can be started in containers.", "Planning, site selection, soil preparation, planting, care, and harvest are key garden stages."], ["ROSEMARY", "THYME", "MINT", "BASIL", "PARSLEY", "TOMATO", "CUCUMBER", "CARROT", "PEPPER", "STRAWBERRY", "BLUEBERRY", "APPLE", "ZUCCHINI", "LETTUCE", "RADISH", "POTATO", "HARVEST", "ORCHARD"]),
    ("Positive Parenting Word Search", "48 encouraging family word search puzzles", "lavender-pop", "halo", "Family Connection Passport", "Family Connection Champion", "Celebrate the caring moments that help families grow together.", ["Positive parenting resources describe nurturing, protecting, and guiding children as core parts of parenting.", "Strong communication and active listening can support secure parent-child relationships.", "Clear family rules work best when caregivers are consistent, predictable, and follow through."], ["LISTENING", "KINDNESS", "PATIENCE", "ROUTINE", "PLAYTIME", "READING", "PRAISE", "EMPATHY", "BOUNDARIES", "TEAMWORK", "BEDTIME", "FAMILY", "TRUST", "SAFETY", "GUIDANCE", "RESPECT", "SUPPORT", "LAUGHTER"]),
]
FILL = ["PUZZLETIME", "RELAX", "DISCOVER", "FAVORITE", "COLLECTION", "LEISURE", "ENJOY", "SOLVE", "CHALLENGE", "MEMORY", "QUIETTIME", "OUTDOORS"]

def clean(text: str) -> str:
    return "".join(char for char in text.upper() if char.isalpha())

def signature(passport: str, achievement: str, message: str, facts: list[str]) -> dict:
    return {"enabled": True, "passport_title": passport, "achievement_title": achievement, "achievement_message": message, "facts_title": "DID YOU KNOW?", "fact_cards": facts}

def puzzles(topic: str, words: list[str], count: int) -> list[dict]:
    bank = [clean(word) for word in words + FILL]
    return [{"name": f"{topic} Puzzle {n:03d}", "words": [bank[(n * 5 + i) % len(bank)] for i in range(12)]} for n in range(1, count + 1)]

def main() -> None:
    # Give every existing puzzle book a usable Signature Edition configuration.
    for path in ROOT.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data.get("puzzles"), list):
            continue
        if not isinstance(data.get("signature_edition"), dict):
            data["signature_edition"] = signature("Puzzle Passport", "Signature Edition", "A calm challenge, one puzzle at a time.", [])
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for title, subtitle, palette, style, passport, achievement, message, facts, words in NEW_BOOKS:
        count = 48 if "Parenting" in title else 60
        data = {"title": title, "subtitle": subtitle, "author": "Slade Puzzles", "palette": palette, "cover_style": style, "detected_topic": title.replace(" Word Search", ""), "signature_edition": signature(passport, achievement, message, facts), "puzzles": puzzles(title.replace(" Word Search", ""), words, count)}
        data["clipart_search_terms"] = title.replace(" Word Search", "") + " illustration clipart transparent background"
        filename = "signature_" + clean(title).lower() + ".json"
        (ROOT / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Created {filename}")

if __name__ == "__main__":
    main()
