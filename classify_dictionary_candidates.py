"""Create a transparent candidate map for the supplied 100k-word dictionary.

It never promotes a dictionary entry straight into a buyer-facing niche.
Entries receive one of three outcomes: proven existing topic membership,
high-confidence root-based suggestion, or unassigned review candidate.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from wordfreq import zipf_frequency


APP_DIR = Path(__file__).resolve().parent
SOURCE = APP_DIR / "word_banks" / "source_data" / "dwyl_words_alpha.txt"
MASTER = APP_DIR / "word_banks" / "Guided_Builder_Master_Word_Bank.json"
OUTPUT = APP_DIR / "word_banks" / "source_data" / "dwyl_topic_candidate_catalog.json"

# These are deliberately strong signals. A word is suggested only when its
# spelling itself contains a clear subject signal; ambiguous words stay in the
# unassigned candidate pool instead of contaminating a topic.
TOPIC_ROOTS = {
    "Space & Astronomy": ("astro", "planet", "galax", "nebula", "comet", "meteor", "orbit", "lunar", "solar", "cosmo", "telescope", "satellit", "rocket"),
    "Vehicles & Automotive": ("autom", "vehicle", "motor", "engine", "truck", "tire", "brake", "wheel", "road", "drive"),
    "Gardening and Garden Life": ("garden", "flower", "plant", "seed", "herb", "soil", "bloom", "orchid", "tulip"),
    "National Parks": ("trail", "canyon", "forest", "mountain", "glacier", "wildlife", "ranger", "campsite", "campground", "hike"),
    "Ocean Life": ("ocean", "marine", "coral", "whale", "dolphin", "shark", "fish", "tide"),
    "Pets and Animal Care": ("puppy", "kitten", "canine", "feline", "rabbit", "hamster", "parrot", "aquarium", "veterin"),
    "Weather and Climate": ("weather", "climate", "storm", "rain", "snow", "cloud", "wind", "thunder", "lightning", "hurricane", "tornado"),
    "Bible and Faith": ("bible", "scripture", "prayer", "gospel", "psalm", "faith", "worship"),
    "Word Skills and Brain Games": ("vocab", "word", "letter", "spell", "read", "write", "grammar", "language"),
    # Expanded discovery map.  These are *review leads*, not approval rules:
    # a word stays out of book generation until it has topic evidence.
    "World War II History": ("allied", "axis", "battle", "bomber", "convoy", "dday", "evac", "frontline", "liberat", "militar", "naval", "paratroop", "ration", "resistan", "wartime"),
    "American History": ("american", "colon", "constitution", "declaration", "founding", "frontier", "independ", "presiden", "revolution", "settler"),
    "US Geography and Landmarks": ("america", "appalach", "capital", "coast", "geograph", "landmark", "monument", "state", "territor"),
    "Science and Discovery": ("biology", "chem", "experiment", "fossil", "geology", "laborator", "microscope", "physics", "scient", "specimen"),
    "Faith Inspiration and Kindness": ("bless", "compassion", "encourag", "forgiv", "gratitud", "kindness", "mindful", "peace", "seren", "thank"),
    "Careers Community and Everyday Life": ("baker", "builder", "cashier", "dentist", "doctor", "firefight", "librar", "mechanic", "nurs", "plumb", "teacher", "veterinar"),
    "Coastal Lake and River Life": ("beach", "coast", "harbor", "kayak", "lakeside", "marina", "riverside", "sail", "seashore", "shoreline"),
    "Hobbies Crafts and Pastimes": ("bead", "ceramic", "crochet", "embroid", "knit", "paint", "photograph", "quilt", "scrapbook", "sewing", "woodwork"),
    "Sports and Hobbies": ("baseball", "basketball", "cycling", "football", "golf", "hockey", "soccer", "sport", "tennis", "volleyball"),
    "Farm Country and Rural Life": ("barn", "cattle", "country", "farm", "harvest", "livestock", "pasture", "poultry", "ranch", "tractor"),
    "Outdoor Adventure": ("backpack", "camp", "climb", "hiking", "kayak", "outdoor", "paddle", "tent", "trail", "wilderness"),
    "Arts Creativity and Making": ("art", "canvas", "collage", "craft", "draw", "easel", "mosaic", "pottery", "sketch", "watercolor"),
    "Wellness and Self Care": ("breath", "calm", "exercise", "journaling", "meditat", "relax", "selfcare", "sleep", "stretch", "wellness", "yoga"),
    "Music and Instruments": ("acoustic", "banjo", "chorus", "concert", "guitar", "melody", "music", "orchestra", "piano", "rhythm", "violin"),
    "Travel Road Trips and Getaways": ("airport", "destination", "hotel", "itinerary", "journey", "luggage", "passport", "roadtrip", "sightseeing", "tourism", "vacation"),
    "Mindfulness": ("balance", "breath", "calm", "gratitud", "meditat", "mindful", "peace", "reflect", "relax", "stillness"),
    "Home and Household": ("bedroom", "clean", "cook", "cupboard", "furniture", "household", "kitchen", "laundry", "pantry", "pillow"),
    "Books Reading and Libraries": ("author", "book", "chapter", "fiction", "librar", "literature", "novel", "poet", "reading", "writer"),
    "Birdwatching": ("aviary", "bird", "feather", "migration", "nest", "ornith", "plumage", "songbird", "waterbird", "woodpecker"),
    "Dog Breeds": ("beagle", "bulldog", "canine", "dachshund", "dog", "poodle", "puppy", "retriever", "terrier", "shepherd"),
    "Cat Lover": ("cat", "feline", "kitten", "meow", "purr", "tabby", "whisker"),
    "Nature": ("ecolog", "habitat", "landscape", "native", "natural", "wildflower", "wildlife", "woodland"),
    "Forest Wildlife and Outdoors": ("canopy", "conifer", "forest", "mammal", "prairie", "redwood", "wildlife", "woodland"),
    "Baking and Food": ("baking", "bread", "cake", "cooking", "dessert", "flavor", "kitchen", "recipe", "spice", "vegetable"),
    "Ocean Life": ("cephalopod", "crustace", "dolphin", "jellyfish", "marine", "ocean", "reef", "seahorse", "shark", "whale"),
    "Positive Parenting": ("caregiv", "childhood", "family", "parent", "playtime", "routine", "schoolday", "storytime"),
    "Seasonal Celebrations": ("autumn", "celebrat", "easter", "festival", "holiday", "spring", "summer", "valentine", "winter"),
    "Halloween Autumn and Harvest": ("autumn", "candy", "costume", "ghost", "halloween", "harvest", "pumpkin", "spooky", "witch"),
    "Christmas and Winter": ("carol", "christmas", "evergreen", "gingerbread", "ornament", "reindeer", "snow", "winter", "yuletide"),
    "Thanksgiving": ("cornucop", "gratitud", "harvest", "thanksgiving", "turkey"),
    "Easter and Spring": ("blossom", "easter", "garden", "spring", "tulip"),
    "Holidays": ("celebrat", "festival", "holiday", "parade", "tradition"),
    "Nostalgia Through the Decades": ("arcade", "cassette", "juke", "nostalgia", "retro", "throwback", "vinyl"),
    "Video Games & Gaming": ("arcade", "console", "game", "gamer", "gaming", "joystick", "multiplayer", "puzzle", "retrogame"),
    "Pop Culture & Entertainment": ("celebrity", "cinema", "concert", "entertain", "film", "media", "movie", "popculture", "television"),
    "Homesteading": ("beekeep", "canning", "chicken", "homestead", "preserv", "sourdough", "vegetable", "woodstove"),
    "Herbs Fruits and Vegetables": ("apple", "basil", "berry", "carrot", "fruit", "herb", "lettuce", "pepper", "tomato", "vegetable"),
}


def has_strong_root(word: str, root: str) -> bool:
    """Avoid substring accidents such as SCAR -> car or BRAIN -> rain."""
    root = root.upper()
    return word == root or word.startswith(root)


def main() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    profiles = master.get("word_profiles", {})
    proven = {str(word).upper(): sorted(str(topic) for topic in profile.get("topics", [])) for word, profile in profiles.items() if isinstance(profile, dict) and profile.get("topics")}
    all_words = [line.strip().upper() for line in SOURCE.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip().isalpha()]
    suggested: dict[str, list[str]] = {}
    unassigned: list[str] = []
    quality: dict[str, float] = {}
    for word in all_words:
        score = zipf_frequency(word.lower(), "en")
        if score >= 2.6:
            quality[word] = round(score, 2)
        # A word already proven for one topic may still be a legitimate lead
        # for another.  Keep its established membership, but surface only the
        # *new* root-matched topics as suggestions for review.  The old early
        # return here accidentally hid those useful cross-topic connections.
        current_topics = set(proven.get(word, []))
        hits = [topic for topic, roots in TOPIC_ROOTS.items()
                if topic not in current_topics and any(has_strong_root(word, root) for root in roots)]
        if hits and score >= 2.6:
            suggested[word] = hits
        else:
            unassigned.append(word)
    by_topic: dict[str, list[str]] = defaultdict(list)
    for word, topics in suggested.items():
        for topic in topics:
            by_topic[topic].append(word)
    payload = {
        "schema_version": 1,
        "source": "dwyl/english-words local spelling dictionary with wordfreq familiarity scores",
        "policy": "Only proven membership or high-confidence spelling-root suggestions may be reviewed for a topic. Unassigned words are not eligible for automatic niche books.",
        "counts": {"dictionary_entries": len(all_words), "proven_topic_words": len(proven), "root_suggested_words": len(suggested), "unassigned_candidates": len(unassigned)},
        "proven_topic_membership": proven,
        "root_suggestions": suggested,
        "suggestions_by_topic": {topic: sorted(words) for topic, words in sorted(by_topic.items())},
        "frequency_scores": quality,
        "unassigned_candidates": unassigned,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Cataloged {len(all_words)} dictionary entries: {len(proven)} proven, {len(suggested)} high-confidence suggestions, {len(unassigned)} unassigned.")


if __name__ == "__main__":
    main()
