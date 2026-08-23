"""Build large, distinct school-vocabulary source pools from the local dictionary.

The supplied dwyl list is used as a spelling candidate source, never as an
automatic topic tag.  ``wordfreq`` supplies an English familiarity signal.
The resulting records are conservative grade bands for puzzle publishing, not
a substitute for a district's official curriculum list.
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path

from wordfreq import zipf_frequency


APP_DIR = Path(__file__).resolve().parent
SOURCE = APP_DIR / "word_banks" / "source_data" / "dwyl_words_alpha.txt"
OUTPUT = APP_DIR / "word_banks" / "source_data" / "education_grade_word_bands.json"
WORDS_PER_GRADE = 1_350  # supports 100 x 12 with a small clean reserve

# The dictionary is a spelling source, so proper names and sensitive terms are
# never suitable for automatic school-book use. This list is deliberately
# conservative; words not cleared here remain candidates for review, not
# automatic puzzle vocabulary.
EXCLUDED_AUTO_WORDS = {
    "aaron", "abraham", "abbott", "abortion", "abuse", "abusive", "addiction", "adultery", "affair", "alcoholic",
    "assault", "bikini", "cancer", "cocaine", "condom", "corpse", "crime", "criminal", "death", "depression",
    "divorce", "drug", "drugs", "execution", "gambling", "gun", "guns", "heroin", "homicide", "murder",
    "naked", "nude", "porn", "pregnancy", "prison", "rape", "sex", "sexual", "suicide", "tobacco", "violence",
}

# A practical publishing heuristic: shorter, more frequent words begin in
# lower bands; later bands admit longer and less frequent academic vocabulary.
# A small neighbor overlap makes the progression feel natural without creating
# near-duplicate books.
GRADE_RULES = {
    5: {"length": (4, 8), "minimum_zipf": 4.0, "neighbor_overlap": 0},
    6: {"length": (4, 9), "minimum_zipf": 3.8, "neighbor_overlap": 90},
    7: {"length": (5, 10), "minimum_zipf": 3.6, "neighbor_overlap": 90},
    8: {"length": (5, 11), "minimum_zipf": 3.4, "neighbor_overlap": 90},
    9: {"length": (6, 12), "minimum_zipf": 3.2, "neighbor_overlap": 90},
    10: {"length": (6, 13), "minimum_zipf": 3.0, "neighbor_overlap": 90},
    11: {"length": (7, 14), "minimum_zipf": 2.8, "neighbor_overlap": 90},
    12: {"length": (7, 15), "minimum_zipf": 2.6, "neighbor_overlap": 90},
}


def candidates() -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    for raw in SOURCE.read_text(encoding="utf-8", errors="ignore").splitlines():
        word = raw.strip().lower()
        if not word.isascii() or not word.isalpha() or len(word) < 4 or word in EXCLUDED_AUTO_WORDS:
            continue
        score = zipf_frequency(word, "en")
        if score >= 2.6:
            rows.append((word.upper(), score))
    return rows


def build() -> dict[str, object]:
    available = candidates()
    assigned: set[str] = set()
    previous: list[str] = []
    bands: dict[str, list[str]] = {}
    metadata: dict[str, dict[str, object]] = {}
    for grade, rule in GRADE_RULES.items():
        low, high = rule["length"]
        eligible = [word for word, score in available if low <= len(word) <= high and score >= rule["minimum_zipf"]]
        # Preserve a limited bridge from the preceding grade, then assign new
        # words only.  This prevents the 80-98% overlap found in the old set.
        bridge = [word for word in previous if word in eligible][: int(rule["neighbor_overlap"])]
        fresh = [word for word in eligible if word not in assigned]
        random.Random(f"Slade Puzzles Grade {grade} vocabulary").shuffle(fresh)
        words = list(dict.fromkeys(bridge + fresh))[:WORDS_PER_GRADE]
        if len(words) < WORDS_PER_GRADE:
            raise ValueError(f"Grade {grade} only has {len(words)} screened candidates; need {WORDS_PER_GRADE}.")
        assigned.update(words)
        previous = words
        bands[f"Grade {grade} Vocabulary"] = sorted(words)
        metadata[f"Grade {grade} Vocabulary"] = {
            "word_count": len(words), "length_range": list(rule["length"]), "minimum_zipf_frequency": rule["minimum_zipf"],
            "intentional_neighbor_overlap": len(bridge),
        }
    return {
        "schema_version": 1,
        "name": "Slade Puzzles Frequency-Screened Grade Vocabulary Bands",
        "created": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "dictionary": "dwyl/english-words local word list",
            "screening": "wordfreq English Zipf familiarity filter plus alphabetic and length checks",
            "note": "Conservative publishing bands, not a replacement for an official school curriculum.",
        },
        "bands": bands,
        "metadata": metadata,
    }


def main() -> None:
    payload = build()
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} with {sum(len(words) for words in payload['bands'].values())} grade-mapped words.")


if __name__ == "__main__":
    main()
