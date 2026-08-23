"""Create two fresh, 100-puzzle special Signature Edition KDP packages."""
from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

import word_search_creator as studio


APP_DIR = Path(__file__).resolve().parent
MASTER = APP_DIR / "word_banks" / "Guided_Builder_Master_Word_Bank.json"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
THEME_DIR = APP_DIR / "themes" / "Signature Editions"
OUTPUT_DIR = APP_DIR / "out" / f"Special Signature Editions - {STAMP}"
PUZZLES, WORDS = 100, 12

BOOKS = (
    {
        "rank": 1,
        "slug": "garden_homestead_harvest",
        "title": "Garden, Homestead and Harvest Word Search - Signature Edition",
        "subtitle": "100 large-print puzzles for gardeners, homesteaders and makers",
        # These are the Master Library's direct source labels. The friendly
        # names are still presented in the app, while this mapping keeps the
        # automatic topic-quality check accurate.
        "topics": ("Gardening and Garden Life", "Homesteading"),
        "detected": "Gardening and Homesteading",
        "series": "Signature Editions: Food and Home",
        "palette": "spring-meadow",
        "art": "cover_assets/background_photos/gardening_vegetables_v3.png",
        "difficulty": "Relaxing",
        "search": "garden homestead harvest vegetables orchard farmhouse",
        "passport": "Garden and Homestead Discovery Passport",
        "achievement": "Harvest Keeper",
        "facts": [
            "A healthy garden can grow food, flowers, herbs, and habitat for pollinators in the same small space.",
            "Preserving a harvest can include drying, freezing, pickling, fermenting, or canning food.",
            "Compost returns useful organic material to the soil and can support healthy garden beds.",
        ],
        "description": "Some people dream of a flourishing garden, a pantry full of jars, a warm loaf cooling on the counter, and a life built a little closer to the land. Garden, Homestead and Harvest Word Search - Signature Edition brings that entire world to the page in a grand 100-puzzle collection made for people who understand the joy of homegrown living. Wander through vegetable beds, orchards, chicken coops, beehives, country kitchens, food preservation, farm chores, and harvest traditions. With 1,200 fresh, topic-rich words and no repeated words across the book, every puzzle is a new visit to the life you love—or the life you are dreaming of building.",
    },
    {
        "rank": 2,
        "slug": "space_planets_astronomy",
        "title": "Space, Planets and Astronomy Word Search - Signature Edition",
        "subtitle": "100 large-print puzzles for stargazers, explorers and curious minds",
        "topics": ("Space & Astronomy",),
        # Keep the display title broad, but use the library's exact topic
        # label for the automated source-fit check.
        "detected": "Space & Astronomy",
        "series": "Signature Editions: Explore and Discover",
        "palette": "cosmic-night",
        "art": "cover_assets/background_photos/space_planet_v2.png",
        "difficulty": "Standard",
        "search": "space planets astronomy solar system galaxy stars telescope",
        "passport": "Cosmic Discovery Passport",
        "achievement": "Star Navigator",
        "facts": [
            "Our solar system includes the Sun, eight planets, dwarf planets, moons, asteroids, and comets.",
            "A light-year measures distance—the distance light travels in one year—not time.",
            "Planets outside our solar system are called exoplanets.",
        ],
        "description": "The universe is too extraordinary for a small puzzle book. Space, Planets and Astronomy Word Search - Signature Edition is a full-scale journey through the solar system, the night sky, and the thrilling language of exploration. Travel from Mercury to Neptune. Meet moons, asteroids, constellations, galaxies, rockets, telescopes, space missions, and distant worlds beyond our solar system. With 1,200 fresh space-themed words and no repeated words across the entire book, this 100-puzzle edition gives every page its own new mission.",
    },
)


def clean(value: object) -> str:
    return re.sub(r"[^A-Z]", "", str(value).upper())


def make_theme(book: dict[str, object], master: dict[str, object]) -> Path:
    topic_map: dict[str, list[str]] = master["topics"]  # type: ignore[assignment]
    pool, seen = [], set()
    for topic in book["topics"]:  # type: ignore[index]
        for raw in topic_map.get(str(topic), []):
            word = clean(raw)
            if 3 <= len(word) <= 21 and word not in seen:
                seen.add(word)
                pool.append(word)
    needed = PUZZLES * WORDS
    if len(pool) < needed:
        raise RuntimeError(f"{book['title']} has only {len(pool)} clean topic words; it needs {needed}.")
    data = {
        "title": book["title"], "subtitle": book["subtitle"], "author": "Slade Puzzles",
        "series": book["series"], "series_rank": book["rank"], "audience": "Adults and Teens",
        "palette": book["palette"], "cover_style": "photo", "recommended_palette": book["palette"],
        "recommended_cover_style": "photo", "cover_badge": "100 LARGE-PRINT PUZZLES - NO REPEATED WORDS",
        "cover_imprint": "Slade Puzzles", "no_repeat_words": True, "difficulty_label": book["difficulty"],
        "detected_topic": book["detected"], "source_word_bank": {"name": "Guided Builder Master Word Bank", "topics": list(book["topics"])},
        "cover_art_path": str(book["art"]), "cover_art_focus": "center", "clipart_search_terms": book["search"],
        "signature_edition": {"enabled": True, "passport_title": book["passport"], "achievement_title": book["achievement"], "achievement_message": "Complete the collection one satisfying puzzle at a time.", "facts_title": "DISCOVER MORE", "fact_cards": book["facts"]},
        "draft": True, "puzzles": [],
    }
    THEME_DIR.mkdir(parents=True, exist_ok=True)
    path = THEME_DIR / f"signature_{book['slug']}_{STAMP}.json"
    for attempt in range(1, 41):
        ordered = list(pool)
        random.Random(f"Slade Signature {STAMP} {book['title']} {attempt}").shuffle(ordered)
        selected = ordered[:needed]
        data["puzzles"] = [{"name": f"{book['detected']} Puzzle {number + 1:03d}", "words": selected[number * WORDS:(number + 1) * WORDS]} for number in range(PUZZLES)]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        errors, _warnings, _notes = studio.audit_theme(path, 950000 + int(book["rank"]))
        if not errors:
            return path
    raise RuntimeError(f"{book['title']} could not find a fully placeable 100-puzzle layout.")


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=APP_DIR, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "A package command stopped unexpectedly.")


def package(theme: Path, book: dict[str, object]) -> Path:
    data = json.loads(theme.read_text(encoding="utf-8-sig"))
    art = APP_DIR / str(book["art"])
    settings = {"theme": str(theme), "title": str(book["title"]), "subtitle": str(book["subtitle"]), "author": "Slade Puzzles", "imprint": "Slade Puzzles", "badge": "100 LARGE-PRINT PUZZLES - NO REPEATED WORDS", "difficulty": str(book["difficulty"]), "palette": str(book["palette"]), "style": "photo", "art": str(art), "art_focus": "center", "format_label": "LARGE PRINT", "signature_edition": True}
    if not art.is_file():
        raise RuntimeError(f"Missing cover background for {book['title']}: {art}")
    seed = 950000 + int(book["rank"])
    errors, warnings, _notes = studio.production_stop_errors(theme, seed, settings)
    if errors:
        raise RuntimeError(f"{book['title']} failed the production stop: {' | '.join(errors)}")
    folder = OUTPUT_DIR / f"{book['rank']:02d}_{book['slug']}"
    folder.mkdir(parents=True, exist_ok=False)
    python = studio.WINDOWS_VENV_PYTHON if studio.WINDOWS_VENV_PYTHON.exists() else Path(sys.executable)
    interior, front, wrap = folder / "interior.pdf", folder / "front_cover.png", folder / "kdp_full_wrap.pdf"
    run([str(python), str(studio.ENGINE), "--themes", str(theme), "--out", str(interior), "--title", settings["title"], "--subtitle", settings["subtitle"], "--author", "Slade Puzzles", "--seed", str(seed), "--signature-edition"])
    run([str(python), str(studio.COVER_ENGINE), "--title", settings["title"], "--subtitle", settings["subtitle"], "--author", "Slade Puzzles", "--badge", settings["badge"], "--difficulty", settings["difficulty"], "--format-label", settings["format_label"], "--palette", settings["palette"], "--style", "photo", "--theme-file", str(theme), "--art", str(art), "--art-focus", "center", "--out", str(front)])
    pages = len(PdfReader(str(interior)).pages)
    package_data = studio.package_data_from_settings(data, settings)
    listing = studio.listing_kit_text(package_data) + "\n\nSIGNATURE EDITION — PREMIUM DESCRIPTION\n" + "=" * 52 + "\n\n" + str(book["description"]) + "\n"
    (folder / "KDP_LISTING_KIT.txt").write_text(listing, encoding="utf-8")
    (folder / "SIGNATURE_LISTING_DESCRIPTION.txt").write_text(str(book["description"]) + "\n", encoding="utf-8")
    (folder / "KDP_UPLOAD_CHECKLIST.txt").write_text(studio.kdp_upload_checklist_text(package_data, pages), encoding="utf-8")
    studio.write_kdp_compliance_report(folder, package_data, pages)
    run([str(python), str(studio.WRAP_ENGINE), "--front", str(front), "--pages", str(pages), "--palette", settings["palette"], "--title", settings["title"], "--author", "Slade Puzzles", "--back", studio.package_blurb(data, package_data), "--out", str(wrap), "--preview-out", str(folder / "kdp_full_wrap_preview.png")])
    with Image.open(front) as image:
        image.thumbnail((510, 660), Image.LANCZOS)
        image.save(folder / "front_cover_thumbnail.png")
    studio.WordSearchCreator._write_proof_bundle(folder, settings, seed, pages, package_data)
    ok, lines = studio.preflight(folder)
    (folder / "PUBLISHER_PREFLIGHT.txt").write_text(studio.package_preflight_text(folder), encoding="utf-8")
    if not ok:
        raise RuntimeError(f"{book['title']} failed print preflight: {' | '.join(lines)}")
    warnings = list(warnings) + list(studio.publisher_safety_report(package_data)["warnings"])
    (folder / "PACKAGE_SCORECARD.txt").write_text(studio.package_scorecard_text(package_data, folder, pages, warnings), encoding="utf-8")
    (folder / "START_HERE.txt").write_text(f"SIGNATURE EDITION KDP PACKAGE\n{'=' * 52}\n\nBook: {book['title']}\n\nUPLOAD: interior.pdf and kdp_full_wrap.pdf\n\nLISTING: KDP_LISTING_KIT.txt and SIGNATURE_LISTING_DESCRIPTION.txt\n\nREVIEW: proof_review\\PROOF_REVIEW.txt and kdp_full_wrap_preview.png\n\nAlways run KDP Print Previewer before publishing.\n", encoding="utf-8")
    return folder


def main() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8-sig"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    themes = [make_theme(book, master) for book in BOOKS]
    packages = [package(theme, book) for theme, book in zip(themes, BOOKS)]
    for theme in themes:
        data = json.loads(theme.read_text(encoding="utf-8-sig"))
        data["draft"] = False
        theme.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "README.txt").write_text("Two special 100-puzzle Signature Edition KDP packages. Open each numbered folder and start with START_HERE.txt.\n", encoding="utf-8")
    print("\n".join(str(path) for path in packages))


if __name__ == "__main__":
    main()
