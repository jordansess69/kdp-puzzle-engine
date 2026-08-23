"""Create five fresh, market-led, topic-pure KDP book packages.

This run is non-destructive: it writes new dated themes and a dated package
folder.  Every book must clear the normal production stop and print preflight.
"""
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
THEME_DIR = APP_DIR / "themes" / "Production Launch 5"
OUTPUT_DIR = APP_DIR / "out" / f"Market Top 5 - {STAMP}"
PUZZLES, WORDS = 48, 12

BOOKS = (
    {
        "rank": 1, "slug": "national_parks", "title": "America's National Parks Word Search",
        "subtitle": "48 large-print puzzles about trails, wildlife and scenic wonders",
        "topics": ("National Parks",), "detected": "National Parks",
        "palette": "forest-cabin", "art": "cover_assets/background_photos/national_parks_forest_v3.png",
        "search": "national parks forests trails wildlife mountains", "difficulty": "Standard",
    },
    {
        "rank": 2, "slug": "gardening", "title": "Garden Lovers Word Search",
        "subtitle": "48 large-print puzzles about flowers, plants and homegrown joy",
        "topics": ("Gardening and Garden Life", "Nature"), "detected": "Gardening & Garden Life",
        "palette": "spring-meadow", "art": "cover_assets/background_photos/gardening_greenhouse_v2.png",
        "search": "gardening flowers greenhouse vegetables plants", "difficulty": "Relaxing",
    },
    {
        "rank": 3, "slug": "thanksgiving", "title": "Thanksgiving Word Search",
        "subtitle": "48 cozy large-print puzzles for gratitude, harvest and family time",
        "topics": ("Halloween Autumn and Harvest", "Holiday and Seasonal Life", "Seasonal Celebrations", "Baking and Food", "Gardening and Garden Life"), "detected": "Thanksgiving",
        "palette": "autumn-harvest", "art": "cover_assets/background_photos/autumn_harvest_v3.png",
        "search": "thanksgiving harvest autumn family table", "difficulty": "Relaxing",
    },
    {
        "rank": 4, "slug": "holiday_celebrations", "title": "Holiday Celebrations Word Search",
        "subtitle": "48 large-print puzzles for festive traditions and cozy moments",
        "topics": ("Holiday and Seasonal Life", "Christmas and Winter", "Halloween Autumn and Harvest", "Seasonal Celebrations", "Weather and Climate", "Baking and Food"), "detected": "Holidays",
        "palette": "winter-frost", "art": "cover_assets/background_photos/winter_fireplace_v3.png",
        "search": "holiday celebrations winter christmas festive traditions", "difficulty": "Relaxing",
    },
    {
        "rank": 5, "slug": "easter_spring", "title": "Easter and Spring Word Search",
        "subtitle": "48 cheerful large-print puzzles for blossoms, renewal and springtime",
        "topics": ("Holiday and Seasonal Life", "Seasonal Celebrations", "Gardening and Garden Life", "Weather and Climate", "Baking and Food"), "detected": "Easter and Spring",
        "palette": "spring-meadow", "art": "cover_assets/background_photos/gardening.png",
        "search": "easter spring blossoms garden renewal", "difficulty": "Relaxing",
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
            if 3 <= len(word) <= 18 and word not in seen:
                seen.add(word); pool.append(word)
    needed = PUZZLES * WORDS
    if len(pool) < needed:
        raise RuntimeError(f"{book['title']} has only {len(pool)} topic-pure words; it needs {needed}.")
    data = {
        "title": book["title"], "subtitle": book["subtitle"], "author": "Slade Puzzles",
        "series": "Slade Puzzles Seasonal and Evergreen Collection", "series_rank": book["rank"],
        "audience": "Adults and Teens", "palette": book["palette"], "cover_style": "photo",
        "recommended_palette": book["palette"], "recommended_cover_style": "photo",
        "cover_badge": "48 LARGE-PRINT PUZZLES - NO REPEATED WORDS", "cover_imprint": "Slade Puzzles",
        "no_repeat_words": True, "difficulty_label": book["difficulty"], "detected_topic": book["detected"],
        "source_word_bank": {"name": "Guided Builder Master Word Bank", "topics": list(book["topics"])},
        "cover_art_path": str(book["art"]), "cover_art_focus": "center", "clipart_search_terms": book["search"],
        "market_research_note": "Selected from current demand signals for large-print adult word searches, seasonal timing, and evergreen giftable themes. This is not a guarantee of sales.",
        "market_research_sources": ["Amazon Word Search Best Sellers", "KDP paperback requirements"],
        "draft": True,
        "puzzles": [],
    }
    THEME_DIR.mkdir(parents=True, exist_ok=True)
    path = THEME_DIR / f"top5_{book['rank']:02d}_{book['slug']}_{STAMP}.json"
    # A valid word list can occasionally create an awkward grid arrangement.
    # Shuffle the same approved words until all 48 exact grids pass; no word is
    # replaced with an off-topic filler.
    for attempt in range(1, 41):
        ordered = list(pool)
        random.Random(f"Slade Puzzles Production Launch {STAMP} {book['title']} {attempt}").shuffle(ordered)
        selected = ordered[:needed]
        data["puzzles"] = [
            {"name": f"{book['title']} Puzzle {number + 1:03d}", "words": selected[number * WORDS:(number + 1) * WORDS]}
            for number in range(PUZZLES)
        ]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        errors, _warnings, _notes = studio.audit_theme(path, 730000 + int(book["rank"]))
        if not errors:
            return path
    raise RuntimeError(f"{book['title']} could not find a fully placeable arrangement after 40 topic-pure attempts.")


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=APP_DIR, capture_output=True, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "A package command stopped unexpectedly.")


def start_here(folder: Path, title: str) -> None:
    (folder / "START_HERE.txt").write_text(
        f"YOUR WORD SEARCH BOOK PACKAGE\n{'=' * 52}\n\nBook: {title}\n\n"
        "UPLOAD TO KDP\n1. interior.pdf - book inside pages\n2. kdp_full_wrap.pdf - full print cover\n\n"
        "FINISH THE LISTING\n- KDP_LISTING_KIT.txt\n- KDP_UPLOAD_CHECKLIST.txt\n\n"
        "REVIEW FIRST\n- proof_review\\PROOF_REVIEW.txt\n- proof_review\\buyer_thumbnail.png\n- kdp_full_wrap_preview.png\n\n"
        "Always run KDP Print Previewer before publishing.\n", encoding="utf-8")


def package(theme: Path, book: dict[str, object]) -> Path:
    data = json.loads(theme.read_text(encoding="utf-8-sig"))
    art = APP_DIR / str(book["art"])
    settings = {
        "theme": str(theme), "title": str(book["title"]), "subtitle": str(book["subtitle"]), "author": "Slade Puzzles",
        "imprint": "Slade Puzzles", "badge": "48 LARGE-PRINT PUZZLES - NO REPEATED WORDS",
        "difficulty": str(book["difficulty"]), "palette": str(book["palette"]), "style": "photo",
        "art": str(art), "art_focus": "center", "format_label": "LARGE PRINT", "signature_edition": False,
    }
    if not art.is_file():
        raise RuntimeError(f"Missing cover background for {book['title']}: {art}")
    seed = 730000 + int(book["rank"])
    errors, warnings, notes = studio.production_stop_errors(theme, seed, settings)
    if errors:
        raise RuntimeError(f"{book['title']} failed the production stop: {' | '.join(errors)}")
    folder = OUTPUT_DIR / f"{book['rank']:02d}_{book['slug']}"
    folder.mkdir(parents=True, exist_ok=False)
    python = studio.WINDOWS_VENV_PYTHON if studio.WINDOWS_VENV_PYTHON.exists() else Path(sys.executable)
    interior, front, wrap = folder / "interior.pdf", folder / "front_cover.png", folder / "kdp_full_wrap.pdf"
    run([str(python), str(studio.ENGINE), "--themes", str(theme), "--out", str(interior), "--title", settings["title"], "--subtitle", settings["subtitle"], "--author", settings["author"], "--seed", str(seed)])
    run([str(python), str(studio.COVER_ENGINE), "--title", settings["title"], "--subtitle", settings["subtitle"], "--author", settings["author"], "--badge", settings["badge"], "--difficulty", settings["difficulty"], "--format-label", settings["format_label"], "--palette", settings["palette"], "--style", "photo", "--theme-file", str(theme), "--art", str(art), "--art-focus", "center", "--out", str(front)])
    pages = len(PdfReader(str(interior)).pages)
    package_data = studio.package_data_from_settings(data, settings)
    (folder / "KDP_UPLOAD_CHECKLIST.txt").write_text(studio.kdp_upload_checklist_text(package_data, pages), encoding="utf-8")
    (folder / "KDP_LISTING_KIT.txt").write_text(studio.listing_kit_text(package_data), encoding="utf-8")
    run([str(python), str(studio.WRAP_ENGINE), "--front", str(front), "--pages", str(pages), "--palette", settings["palette"], "--title", settings["title"], "--author", settings["imprint"], "--back", studio.package_blurb(data, package_data), "--out", str(wrap), "--preview-out", str(folder / "kdp_full_wrap_preview.png")])
    with Image.open(front) as image:
        image.thumbnail((510, 660), Image.LANCZOS); image.save(folder / "front_cover_thumbnail.png")
    studio.WordSearchCreator._write_proof_bundle(folder, settings, seed, pages, package_data)
    ok, lines = studio.preflight(folder)
    (folder / "PUBLISHER_PREFLIGHT.txt").write_text(studio.package_preflight_text(folder), encoding="utf-8")
    if not ok:
        raise RuntimeError(f"{book['title']} failed print preflight: {' | '.join(lines)}")
    warnings = list(warnings) + list(studio.publisher_safety_report(package_data)["warnings"])
    (folder / "PACKAGE_SCORECARD.txt").write_text(studio.package_scorecard_text(package_data, folder, pages, warnings), encoding="utf-8")
    start_here(folder, str(book["title"]))
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
    (OUTPUT_DIR / "README.txt").write_text("Five market-led, quality-gated KDP packages. Open each numbered folder and begin with START_HERE.txt.\n", encoding="utf-8")
    print("\n".join(str(path) for path in packages))


if __name__ == "__main__":
    main()
