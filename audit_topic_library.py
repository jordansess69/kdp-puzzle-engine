"""Create an honest, repeatable content audit for every word-bank topic.

This checks spelling against the locally supplied dictionary and familiarity
against wordfreq.  It intentionally does not pretend that a spelling
dictionary can establish topical relevance.  Instead it records transparent
review counts so only curated direct-topic lists feed automatic books.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from wordfreq import zipf_frequency


APP_DIR = Path(__file__).resolve().parent
MASTER = APP_DIR / "word_banks" / "Guided_Builder_Master_Word_Bank.json"
DICTIONARY = APP_DIR / "word_banks" / "source_data" / "dwyl_words_alpha.txt"
OUTPUT = APP_DIR / "word_banks" / "TOPIC_WORD_AUDIT.json"


def main() -> None:
    bank = json.loads(MASTER.read_text(encoding="utf-8"))
    dictionary = {
        line.strip().upper() for line in DICTIONARY.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip().isalpha()
    }
    profiles = bank.get("word_profiles", {})
    records = []
    all_review = []
    for topic, words in sorted(bank.get("topics", {}).items()):
        direct = [word for word in words if topic in profiles.get(word, {}).get("topics", [])]
        exact = [word for word in direct if word in dictionary]
        familiar = [word for word in direct if zipf_frequency(word.lower(), "en") >= 2.6]
        review = sorted(word for word in direct if word not in dictionary and zipf_frequency(word.lower(), "en") < 2.6)
        records.append({
            "topic": topic,
            "direct_topic_words": len(direct),
            "dictionary_confirmed": len(exact),
            "familiarity_confirmed": len(familiar),
            "compound_or_specialist_terms_to_review": len(review),
            "review_examples": review[:25],
            "policy": "Dictionary spelling is supporting evidence only. Curated direct-topic membership remains required for automatic generation.",
        })
        all_review.extend(review)
    summary = {
        "topics": len(records),
        "direct_topic_entries": sum(row["direct_topic_words"] for row in records),
        "dictionary_confirmed_entries": sum(row["dictionary_confirmed"] for row in records),
        "familiarity_confirmed_entries": sum(row["familiarity_confirmed"] for row in records),
        "entries_needing_human_or_source_review": len(set(all_review)),
    }
    payload = {
        "schema_version": 1,
        "created": datetime.now().isoformat(timespec="seconds"),
        "purpose": "Topic library spelling/familiarity audit. It prevents a general dictionary from being mistaken for a topic classifier.",
        "rules": {
            "dictionary": "The local dwyl list confirms common spelling coverage.",
            "familiarity": "wordfreq Zipf score >= 2.6 is a screen for reader-recognizable English words, not a topic label.",
            "automatic_generation": "Uses only direct curated topic words; review candidates are never added automatically."
        },
        "summary": summary,
        "topics": records,
        "review_term_frequency": Counter(all_review).most_common(),
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}: {summary}")


if __name__ == "__main__":
    main()
