"""Create the current top-three launch books and full Grade 5-12 packages.

This is intentionally non-destructive: it creates dated output folders and
new source themes for the launch books / rebuilt 100-puzzle signatures.
"""
from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

import word_search_creator as studio


APP_DIR = Path(__file__).resolve().parent
MASTER_FILE = APP_DIR / "word_banks" / "Guided_Builder_Master_Word_Bank.json"
GRADE_DIR = APP_DIR / "themes" / "Vocabulary Ladder Collection" / "Grades 5 to 12"
LAUNCH_DIR = APP_DIR / "themes" / "Launch Collection"
SIGNATURE_DIR = GRADE_DIR / "Signature 100 Puzzle Editions"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = APP_DIR / "out" / f"Top 3 and School Series - {STAMP}"

PUZZLES = 48
WORDS_PER_PUZZLE = 12
SIGNATURE_PUZZLES = 100

LAUNCH_BOOKS = (
    {
        "slug": "space_astronomy",
        "title": "Space and Astronomy Word Search",
        "subtitle": "48 large-print puzzles about planets, stars and exploration",
        "topics": ("Space & Astronomy",),
        "palette": "midnight-gold",
        "style": "halo",
        "difficulty": "Standard",
        "detected_topic": "Space & Astronomy",
        "art_terms": "space planets stars astronomy",
    },
    {
        "slug": "cars_trucks_road_trips",
        "title": "Cars, Trucks and Road Trips Word Search",
        "subtitle": "48 large-print puzzles for vehicle and travel fans",
        "topics": ("Vehicles & Automotive", "Travel Road Trips and Getaways"),
        "palette": "retro-drive",
        "style": "ticket",
        "difficulty": "Standard",
        "detected_topic": "Vehicles & Automotive",
        "art_terms": "cars trucks road trips scenic highway",
    },
    {
        "slug": "nostalgia_through_decades",
        "title": "Through the Decades Word Search",
        "subtitle": "48 large-print throwback puzzles for fans of classic culture and memories",
        "topics": ("Nostalgia Through the Decades", "Pop Culture & Entertainment", "Music and Instruments"),
        "palette": "retro-pop",
        "style": "retro",
        "difficulty": "Standard",
        "detected_topic": "Nostalgia Through the Decades",
        "art_terms": "retro nostalgia cassette vinyl arcade",
    },
)


def clean_word(value: object) -> str:
    return re.sub(r"[^A-Z]", "", str(value).upper())


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=APP_DIR, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "A package command stopped unexpectedly.")


def words_from_theme(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return [clean_word(word) for puzzle in data.get("puzzles", []) if isinstance(puzzle, dict) for word in puzzle.get("words", []) if clean_word(word)]


def make_puzzles(title: str, words: list[str], count: int) -> list[dict[str, object]]:
    needed = count * WORDS_PER_PUZZLE
    if len(words) < needed or len(set(words)) != len(words):
        raise ValueError(f"{title} needs {needed} unique words; received {len(words)}.")
    return [
        {"name": f"{title} Puzzle {number + 1:03d}", "words": words[number * WORDS_PER_PUZZLE:(number + 1) * WORDS_PER_PUZZLE]}
        for number in range(count)
    ]


def launch_themes(master: dict[str, object]) -> list[Path]:
    topics: dict[str, list[str]] = master["topics"]  # type: ignore[assignment]
    LAUNCH_DIR.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for record in LAUNCH_BOOKS:
        pool: list[str] = []
        seen: set[str] = set()
        for topic in record["topics"]:
            for raw in topics.get(str(topic), []):
                word = clean_word(raw)
                if 3 <= len(word) <= 15 and word not in seen:
                    seen.add(word); pool.append(word)
        # A dated launch run receives a fresh, still topic-pure selection.
        # This prevents a second production run from recreating the exact same
        # book and correctly tripping the app's duplicate-book safeguard.
        random.Random(f"{record['title']}:{STAMP}").shuffle(pool)
        data = {
            "title": record["title"], "subtitle": record["subtitle"], "author": "Slade Puzzles",
            "series": "Slade Puzzles Launch Collection", "audience": "Adults and Teens",
            "palette": record["palette"], "cover_style": record["style"],
            "cover_badge": "48 LARGE-PRINT PUZZLES - NO REPEATED WORDS",
            "cover_imprint": "Slade Puzzles", "no_repeat_words": True,
            "difficulty_label": record["difficulty"], "detected_topic": record["detected_topic"],
            "source_word_bank": {"name": "Guided Builder Master Word Bank", "topics": list(record["topics"])},
            "clipart_search_terms": record["art_terms"],
            "puzzles": make_puzzles(str(record["title"]), pool, PUZZLES),
        }
        path = LAUNCH_DIR / f"launch_{record['slug']}_{STAMP}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        created.append(path)
    return created


def rebuilt_signature_theme(grade: int, master: dict[str, object]) -> Path:
    """Make a real 100-puzzle signature edition from clean, familiar words.

    The existing 48-puzzle Signature-named files are preserved.  This new file
    uses the grade's original vocabulary first, then plain alphabetic words
    already in the reviewed Master Library.  Adjacent-grade overlap is
    deliberate: the books use a "core plus stretch" vocabulary progression.
    """
    base = words_from_theme(GRADE_DIR / f"vocabulary_ladder_grade_{grade}.json")
    dictionary = {
        line.strip().upper()
        for line in (APP_DIR / "word_banks" / "source_data" / "dwyl_words_alpha.txt").read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip().isalpha()
    }
    all_words = [clean_word(word) for word in master.get("words", [])]
    # Keep supplementary terms recognizable enough for a school puzzle: normal
    # alphabetic dictionary words, no short fragments, and no long compounds.
    lengths = {5: (4, 8), 6: (4, 9), 7: (5, 10), 8: (5, 11), 9: (6, 12), 10: (6, 13), 11: (7, 14), 12: (7, 15)}[grade]
    extras = [word for word in all_words if lengths[0] <= len(word) <= lengths[1] and word in dictionary and word not in set(base)]
    random.Random(f"Vocabulary Ladder Grade {grade} Signature").shuffle(extras)
    words = list(dict.fromkeys(base + extras))[:SIGNATURE_PUZZLES * WORDS_PER_PUZZLE]
    if len(words) < SIGNATURE_PUZZLES * WORDS_PER_PUZZLE:
        raise ValueError(f"Grade {grade} does not have enough clean vocabulary for a 100-puzzle Signature Edition.")
    standard = json.loads((GRADE_DIR / f"vocabulary_ladder_grade_{grade}.json").read_text(encoding="utf-8-sig"))
    title = f"Vocabulary Ladder: Grade {grade} Word Quest - Signature Edition"
    data = {
        **standard,
        "title": title,
        "subtitle": f"100 vocabulary word searches for stronger reading, writing and word confidence",
        "cover_style": "photo",
        "cover_badge": "100 LARGE-PRINT PUZZLES - NO REPEATED WORDS",
        "signature_edition": {
            "enabled": True, "passport_title": f"Grade {grade} Word Passport", "achievement_title": "Vocabulary Achievement",
            "achievement_message": "Every new word is a tool you can use for life.", "facts_title": "WORDS TO REMEMBER",
            "fact_cards": ["Vocabulary grows through reading, listening, writing, and using new words.", "The Signature Edition combines Grade {grade} core words with carefully chosen stretch vocabulary.", "Use one favorite word from every puzzle in a real sentence."],
            "challenge": "Word Power Challenge: choose one new word and use it in a real sentence today.",
        },
        "vocabulary_scope": "Grade-aligned core vocabulary with adjacent-level stretch words from the clean Master Library.",
        "source_word_bank": {"name": "Guided Builder Master Word Bank", "topics": [f"Grade {grade} Vocabulary", "Word Skills and Brain Games"]},
        "puzzles": make_puzzles(title, words, SIGNATURE_PUZZLES),
    }
    SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)
    path = SIGNATURE_DIR / f"vocabulary_ladder_grade_{grade}_signature_100_puzzles_{STAMP}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def build_package(theme: Path, seed: int, category: str) -> Path:
    data = json.loads(theme.read_text(encoding="utf-8-sig"))
    errors, warnings, _notes = studio.quality_gate(theme, seed)
    if errors:
        raise RuntimeError(f"{theme.name} failed the quality gate: {' | '.join(errors)}")
    title = str(data["title"]); target = OUTPUT_DIR / category / re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")
    target.mkdir(parents=True, exist_ok=False)
    choice = studio.recommend_background_photo(data)
    art = APP_DIR / str(choice.get("file") or "") if choice else None
    palette = studio.photo_choice_palette(choice, str(data.get("palette") or "nature")) if choice else str(data.get("palette") or "nature")
    style = "photo" if art and art.is_file() else str(data.get("cover_style") or "gallery")
    badge = str(data.get("cover_badge") or f"INCLUDES {len(data.get('puzzles', []))} PUZZLES")
    signature = studio.is_signature_edition(data)
    settings = {
        "theme": str(theme), "title": title, "subtitle": str(data.get("subtitle") or ""), "author": str(data.get("author") or "Slade Puzzles"),
        "imprint": str(data.get("cover_imprint") or "Slade Puzzles"), "badge": badge, "difficulty": studio.puzzle_difficulty_label(data),
        "palette": palette, "style": style, "art": str(art) if art and art.is_file() else "", "art_focus": str(choice.get("focus") or "center") if choice else "center",
        "format_label": "LARGE PRINT" if studio.book_format_label(data) == "LARGE PRINT PUZZLES" else "WORD SEARCH", "signature_edition": signature,
    }
    python = studio.WINDOWS_VENV_PYTHON if studio.WINDOWS_VENV_PYTHON.exists() else Path(sys.executable)
    interior, front, wrap = target / "interior.pdf", target / "front_cover.png", target / "kdp_full_wrap.pdf"
    engine = [str(python), str(studio.ENGINE), "--themes", str(theme), "--out", str(interior), "--title", title, "--subtitle", settings["subtitle"], "--author", settings["author"], "--seed", str(seed)]
    if signature:
        engine.append("--signature-edition")
    run(engine)
    cover = [str(python), str(studio.COVER_ENGINE), "--title", title, "--subtitle", settings["subtitle"], "--author", settings["author"], "--badge", badge, "--difficulty", settings["difficulty"], "--format-label", settings["format_label"], "--palette", palette, "--style", style, "--theme-file", str(theme), "--out", str(front)]
    if settings["art"]:
        cover.extend(["--art", settings["art"], "--art-focus", settings["art_focus"]])
    run(cover)
    pages = len(PdfReader(str(interior)).pages)
    package_data = studio.package_data_from_settings(data, settings)
    (target / "KDP_UPLOAD_CHECKLIST.txt").write_text(studio.kdp_upload_checklist_text(package_data, pages), encoding="utf-8")
    (target / "KDP_LISTING_KIT.txt").write_text(studio.listing_kit_text(package_data), encoding="utf-8")
    run([str(python), str(studio.WRAP_ENGINE), "--front", str(front), "--pages", str(pages), "--palette", palette, "--title", title, "--author", settings["imprint"], "--back", studio.package_blurb(data, package_data), "--out", str(wrap), "--preview-out", str(target / "kdp_full_wrap_preview.png")])
    with Image.open(front) as image:
        image.thumbnail((510, 660), Image.LANCZOS); image.save(target / "front_cover_thumbnail.png")
    matches = studio.cross_book_similarity_report(theme, data)
    original = ["ORIGINALITY CHECK", "=" * 48, "This is a production similarity signal, not copyright clearance.", ""]
    original.extend(f"- {item['title']}: {float(item['overlap']):.0%} shared vocabulary ({item['level']})" for item in matches[:5])
    if not matches: original.append("PASS - no meaningful overlap with saved books was found.")
    (target / "ORIGINALITY_CHECK.txt").write_text("\n".join(original) + "\n", encoding="utf-8")
    studio.WordSearchCreator._write_proof_bundle(target, settings, seed, pages, package_data)
    ok, lines = studio.preflight(target)
    (target / "PUBLISHER_PREFLIGHT.txt").write_text(studio.package_preflight_text(target), encoding="utf-8")
    if not ok:
        raise RuntimeError(f"{title} failed print preflight: {' | '.join(lines)}")
    warnings.extend(studio.publisher_safety_report(package_data)["warnings"])
    (target / "PACKAGE_SCORECARD.txt").write_text(studio.package_scorecard_text(package_data, target, pages, warnings), encoding="utf-8")
    return target


def main() -> None:
    master = json.loads(MASTER_FILE.read_text(encoding="utf-8"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    themes = [(path, "Top 3 Launch Books") for path in launch_themes(master)]
    themes.extend((GRADE_DIR / f"vocabulary_ladder_grade_{grade}.json", "School Series - Standard") for grade in range(5, 13))
    themes.extend((rebuilt_signature_theme(grade, master), "School Series - Signature 100 Puzzle") for grade in range(5, 13))
    built = [build_package(path, 9200 + number, category) for number, (path, category) in enumerate(themes, start=1)]
    (OUTPUT_DIR / "BUILD_SUMMARY.txt").write_text("Created and preflight-checked packages:\n" + "\n".join(str(path.relative_to(OUTPUT_DIR)) for path in built) + "\n", encoding="utf-8")
    print(f"Created {len(built)} complete packages in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
