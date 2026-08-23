"""Create research-led, evergreen word-search themes for Slade Puzzles."""
from __future__ import annotations

import json
from pathlib import Path


THEMES = Path(__file__).resolve().parent / "themes"

# Specific interest niches are more useful to buyers than generic "word search" topics.
BOOKS = [
    ("Dog Breeds", "48 tail-wagging dog breed word search puzzles", "animals", "playful", ["GOLDEN RETRIEVER", "LABRADOR", "GERMAN SHEPHERD", "BEAGLE", "POODLE", "DACHSHUND", "BULLDOG", "BOXER", "PUG", "HUSKY", "BORDER COLLIE", "CHIHUAHUA", "DALMATIAN", "POMERANIAN", "MASTIFF", "TERRIER"]),
    ("Cat Lover", "48 purr-fect feline word search puzzles", "candy-pop", "playful", ["TABBY", "SIAMESE", "PERSIAN", "MAINE COON", "CALICO", "TUXEDO CAT", "WHISKERS", "PAWS", "KITTEN", "CATNIP", "SCRATCHER", "PURR", "FELINE", "TOMCAT", "LITTER", "SUNBEAM"]),
    ("Horse Lover", "48 equestrian word search puzzles", "espresso-cream", "classic", ["THOROUGHBRED", "QUARTER HORSE", "MUSTANG", "ARABIAN", "STABLE", "SADDLE", "BRIDLE", "GALLOP", "TROT", "CANTER", "PASTURE", "MANE", "HOOF", "RIDING", "EQUESTRIAN", "FOAL"]),
    ("Birdwatching", "48 backyard and wild bird word search puzzles", "ocean-breeze", "gallery", ["CARDINAL", "BLUE JAY", "ROBIN", "GOLDFINCH", "HUMMINGBIRD", "EAGLE", "OSPREY", "OWL", "SPARROW", "WARBLER", "NEST", "FEATHER", "BINOCULARS", "MIGRATION", "SONGBIRD", "BIRDFEEDER"]),
    ("Farm Animals", "48 barnyard word search puzzles", "autumn-harvest", "colorblock", ["COW", "PIG", "SHEEP", "GOAT", "CHICKEN", "HORSE", "DONKEY", "ROOSTER", "DUCKLING", "BARN", "TRACTOR", "HAYBALE", "PASTURE", "MILKING", "EGG BASKET", "SCARECROW"]),
    ("Books of the Bible", "48 faith-filled Bible word search puzzles", "bible", "classic", ["GENESIS", "EXODUS", "PSALMS", "PROVERBS", "ISAIAH", "MATTHEW", "MARK", "LUKE", "JOHN", "ACTS", "ROMANS", "REVELATION", "APOSTLE", "SCRIPTURE", "COVENANT", "GOSPEL"]),
    ("Faith and Encouragement", "48 uplifting Christian word search puzzles", "lavender-pop", "halo", ["FAITH", "HOPE", "GRACE", "PRAYER", "BLESSING", "MERCY", "JOY", "PEACE", "PATIENCE", "KINDNESS", "LOVE", "PRAISE", "WORSHIP", "MIRACLE", "HEAVEN", "PROMISE"]),
    ("World Countries and Capitals", "48 geography word search puzzles", "coastal-blue", "stripe", ["CANADA", "MEXICO", "BRAZIL", "FRANCE", "JAPAN", "KENYA", "INDIA", "AUSTRALIA", "LONDON", "PARIS", "TOKYO", "OTTAWA", "CAIRO", "ROME", "SEOUL", "CAPITAL"]),
    ("American Road Trip", "48 USA travel word search puzzles", "usa", "retro", ["ROUTE SIXTY SIX", "HIGHWAY", "MOTEL", "DINER", "ROADMAP", "NATIONAL PARK", "COASTLINE", "MOUNTAIN", "DESERT", "ROAD TRIP", "GAS STATION", "SCENIC BYWAY", "STATE LINE", "SUITCASE", "CAMERA", "ADVENTURE"]),
    ("Gardening", "48 relaxing garden word search puzzles", "spring-meadow", "gallery", ["SUNFLOWER", "ROSE", "TULIP", "DAFFODIL", "LAVENDER", "TOMATO", "BASIL", "COMPOST", "TROWEL", "SEEDLING", "GREENHOUSE", "BUTTERFLY", "BEE", "SOIL", "WATERING CAN", "HARVEST"]),
    ("Baking", "48 sweet kitchen word search puzzles", "food", "ticket", ["FLOUR", "SUGAR", "BUTTER", "VANILLA", "CINNAMON", "CUPCAKE", "BROWNIE", "PIECRUST", "WHISK", "OVEN", "MEASURING CUP", "COOKIE", "MUFFIN", "FROSTING", "DOUGH", "SPRINKLES"]),
    ("Coffee and Tea", "48 cozy cafe word search puzzles", "espresso-cream", "minimal", ["ESPRESSO", "LATTE", "CAPPUCCINO", "MOCHA", "COFFEE BEAN", "TEAPOT", "EARL GREY", "CHAMOMILE", "HONEY", "BISCUIT", "CAFE", "MUG", "STEAM", "BARISTA", "TEA LEAF", "ROAST"]),
    ("Wine and Cheese", "48 gourmet word search puzzles", "berry-blush", "bold", ["MERLOT", "CHARDONNAY", "CABERNET", "PROSECCO", "BRIE", "CHEDDAR", "GOUDA", "PARMESAN", "VINEYARD", "TASTING", "CORKSCREW", "CHARCUTERIE", "GRAPES", "BOTTLE", "SOMMELIER", "CRACKERS"]),
    ("Fishing", "48 lake and river word search puzzles", "ocean-life", "stripe", ["BASS", "TROUT", "SALMON", "CATFISH", "LURE", "REEL", "FISHING ROD", "TACKLE BOX", "BOBBER", "BAIT", "RIVERBANK", "LAKE", "CASTING", "ANGLER", "WADERS", "DOCK"]),
    ("Golf", "48 fairway word search puzzles", "nature", "minimal", ["TEE BOX", "FAIRWAY", "GREEN", "BUNKER", "PUTTER", "DRIVER", "BIRDIE", "EAGLE", "PAR", "CADDIE", "CLUBHOUSE", "FLAGSTICK", "GOLF CART", "NINETEENTH HOLE", "HANDICAP", "ROUGH"]),
    ("Quilting", "48 cozy quilting word search puzzles", "valentine-rose", "colorblock", ["QUILT BLOCK", "PATCHWORK", "THIMBLE", "NEEDLE", "THREAD", "FABRIC", "BATTING", "BINDING", "APPLIQUE", "SEWING", "ROTARY CUTTER", "SPOOL", "STITCH", "PATTERN", "SCRAPS", "QUILTER"]),
    ("Sewing and Crafts", "48 creative hobby word search puzzles", "easter-pastel", "playful", ["SEWING MACHINE", "SCISSORS", "YARN", "CROCHET", "KNITTING", "GLUE GUN", "PAPERCRAFT", "RIBBON", "BUTTON", "EMBROIDERY", "PAINTBRUSH", "SKETCHBOOK", "CRAFT TABLE", "BEADS", "PROJECT", "CREATIVE"]),
    ("Classic Literature", "48 timeless bookish word search puzzles", "midnight-gold", "classic", ["NOVEL", "POETRY", "AUTHOR", "LIBRARY", "BOOKMARK", "CHAPTER", "PROTAGONIST", "MYSTERY", "ADVENTURE", "ROMANCE", "FABLE", "MYTHOLOGY", "SHAKESPEARE", "AUSTEN", "DICKENS", "PAPERBACK"]),
    ("Mindfulness and Gratitude", "48 calming word search puzzles for adults", "lavender-pop", "halo", ["MINDFULNESS", "GRATITUDE", "BREATHE", "CALM", "BALANCE", "STILLNESS", "KINDNESS", "JOURNAL", "REFLECT", "PRESENT", "SERENITY", "WELLNESS", "SUNSHINE", "GENTLE", "REST", "JOYFUL"]),
    ("Cozy Autumn", "48 fall favorites word search puzzles", "autumn-harvest", "ticket", ["PUMPKIN", "APPLE CIDER", "SWEATER", "BONFIRE", "FALL LEAVES", "HARVEST", "HAYRIDE", "CORN MAZE", "MAPLE", "ACORN", "COZY", "THANKFUL", "ORCHARD", "SCARF", "CHILLY", "AUTUMN"]),
]

FILLER = ["WORD SEARCH", "PUZZLE TIME", "RELAX", "DISCOVER", "BRAIN GAME", "FAVORITE", "HOBBY", "COLLECTION", "LEISURE", "WEEKEND", "ENJOY", "SOLVE", "FIND", "LETTER", "CHALLENGE", "INTEREST", "MEMORY", "SMILE", "QUIET TIME", "FREETIME"]


def clean(text: str) -> str:
    return "".join(letter for letter in text.upper() if letter.isalpha())


def build_puzzles(topic: str, words: list[str]) -> list[dict[str, object]]:
    bank = [clean(word) for word in words + FILLER]
    result: list[dict[str, object]] = []
    for number in range(48):
        start = (number * 5) % len(bank)
        chosen = [bank[(start + offset) % len(bank)] for offset in range(12)]
        result.append({"name": f"{topic} Puzzle {number + 1:03d}", "words": chosen})
    return result


def main() -> None:
    THEMES.mkdir(exist_ok=True)
    for number, (topic, subtitle, palette, style, words) in enumerate(BOOKS, start=1):
        data = {
            "title": f"{topic} Word Search",
            "subtitle": subtitle,
            "author": "Slade Puzzles",
            "series": "Slade Puzzles Popular Themes",
            "series_rank": number,
            "palette": palette,
            "cover_style": style,
            "puzzles": build_puzzles(topic, words),
        }
        filename = f"popular_{number:02d}_{clean(topic).lower()}.json"
        (THEMES / filename).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Created {filename}")


if __name__ == "__main__":
    main()
