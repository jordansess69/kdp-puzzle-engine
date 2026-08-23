"""Rebuild KDP-safe school Signature Edition packages without touching originals."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

import word_search_creator as studio


APP_DIR = Path(__file__).resolve().parent
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = APP_DIR / "out" / f"Signature Editions KDP Fixed - {STAMP}"

BOOKS = (
    {
        "rank": 1,
        "slug": "grade_5_vocabulary",
        "theme": APP_DIR / "themes" / "Vocabulary Ladder Collection" / "Grades 5 to 12" / "vocabulary_ladder_grade_5_signature_edition.json",
        "art": APP_DIR / "cover_assets" / "background_photos" / "school_elementary_learning_v1.png",
        "palette": "kids",
        "difficulty": "Relaxing",
        "description": "A bigger word adventure for the reader ready to shine.\n\nThis is not another worksheet. It is a 100-puzzle word quest created to make Grade 5 vocabulary feel exciting, achievable, and worth celebrating.\n\nVocabulary Ladder: Grade 5 Word Quest - Signature Edition gives young readers 1,200 carefully chosen words to discover through a full-sized collection of large-print word searches. Every puzzle introduces a completely fresh word list—no repeated words anywhere in the book—so each new page feels like a real step forward.\n\nFrom a quiet after-school challenge to a homeschool staple, classroom enrichment activity, travel companion, or thoughtful educational gift, this Signature Edition turns screen-free time into a confidence-building achievement.\n\nInside this premium 100-puzzle edition:\n- 1,200 Grade 5 vocabulary words\n- 100 large-print word search puzzles\n- No repeated words across the entire book\n- Clear, easy-to-read grids for independent solving\n- Complete solutions at the back\n- A meaningful gift for curious readers and growing word lovers\n\nOpen the book. Find the words. Watch confidence grow.",
    },
    {
        "rank": 2,
        "slug": "grade_8_vocabulary",
        "theme": APP_DIR / "themes" / "Vocabulary Ladder Collection" / "Grades 5 to 12" / "vocabulary_ladder_grade_8_signature_edition.json",
        "art": APP_DIR / "cover_assets" / "background_photos" / "school_middle_learning_v1.png",
        "palette": "kids",
        "difficulty": "Standard",
        "description": "A serious word challenge for students ready to level up.\n\nBig vocabulary does not have to feel intimidating. Vocabulary Ladder: Grade 8 Word Quest - Signature Edition turns it into a satisfying challenge students can actually look forward to.\n\nWith 100 large-print puzzles and 1,200 Grade 8 words, this expanded Signature Edition offers a deeper, more rewarding way to strengthen reading comprehension, writing confidence, and word knowledge. Every puzzle delivers a new list to conquer—no repeated words across the entire book—so the challenge stays fresh from the first page to the last.\n\nIt is the kind of book that belongs on a student’s desk, in a homeschool library, in a classroom activity bin, or tucked into a backpack for a smart break from screens.\n\nInside this premium 100-puzzle edition:\n- 1,200 Grade 8 vocabulary words\n- 100 large-print word search puzzles\n- No repeated words across the entire book\n- A fun way to reinforce classroom and independent learning\n- Complete solutions at the back\n- A standout educational gift for middle-school readers\n\nMore words. More confidence. More ways to succeed.",
    },
)


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=APP_DIR, capture_output=True, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "A package command stopped unexpectedly.")


def package(book: dict[str, object]) -> Path:
    theme, art = Path(book["theme"]), Path(book["art"])
    if not theme.is_file() or not art.is_file():
        raise RuntimeError(f"Missing source: {theme if not theme.is_file() else art}")
    data = json.loads(theme.read_text(encoding="utf-8-sig"))
    title, subtitle = str(data["title"]), str(data["subtitle"])
    settings = {"theme": str(theme), "title": title, "subtitle": subtitle, "author": "Slade Puzzles", "imprint": "Slade Puzzles", "badge": "100 LARGE-PRINT PUZZLES - NO REPEATED WORDS", "difficulty": str(book["difficulty"]), "palette": str(book["palette"]), "style": "photo", "art": str(art), "art_focus": "center", "format_label": "LARGE PRINT", "signature_edition": True}
    seed = 910000 + int(book["rank"])
    errors, warnings, _notes = studio.production_stop_errors(theme, seed, settings)
    if errors:
        raise RuntimeError(f"{title} failed the production check: {' | '.join(errors)}")
    folder = OUTPUT_DIR / f"{book['rank']:02d}_{book['slug']}"
    folder.mkdir(parents=True, exist_ok=False)
    python = studio.WINDOWS_VENV_PYTHON if studio.WINDOWS_VENV_PYTHON.exists() else Path(sys.executable)
    interior, front, wrap = folder / "interior.pdf", folder / "front_cover.png", folder / "kdp_full_wrap.pdf"
    run([str(python), str(studio.ENGINE), "--themes", str(theme), "--out", str(interior), "--title", title, "--subtitle", subtitle, "--author", "Slade Puzzles", "--seed", str(seed), "--signature-edition"])
    run([str(python), str(studio.COVER_ENGINE), "--title", title, "--subtitle", subtitle, "--author", "Slade Puzzles", "--badge", settings["badge"], "--difficulty", settings["difficulty"], "--format-label", settings["format_label"], "--palette", settings["palette"], "--style", "photo", "--theme-file", str(theme), "--art", str(art), "--art-focus", "center", "--out", str(front)])
    pages = len(PdfReader(str(interior)).pages)
    package_data = studio.package_data_from_settings(data, settings)
    description = str(book["description"])
    (folder / "SIGNATURE_LISTING_DESCRIPTION.txt").write_text(description + "\n", encoding="utf-8")
    (folder / "KDP_LISTING_KIT.txt").write_text(studio.listing_kit_text(package_data) + "\n\nSIGNATURE EDITION — COPY-READY PREMIUM DESCRIPTION\n" + "=" * 56 + "\n\n" + description + "\n", encoding="utf-8")
    (folder / "KDP_UPLOAD_CHECKLIST.txt").write_text(studio.kdp_upload_checklist_text(package_data, pages), encoding="utf-8")
    studio.write_kdp_compliance_report(folder, package_data, pages)
    run([str(python), str(studio.WRAP_ENGINE), "--front", str(front), "--pages", str(pages), "--palette", settings["palette"], "--title", title, "--author", "Slade Puzzles", "--back", studio.package_blurb(data, package_data), "--out", str(wrap), "--preview-out", str(folder / "kdp_full_wrap_preview.png")])
    with Image.open(front) as image:
        image.thumbnail((510, 660), Image.LANCZOS)
        image.save(folder / "front_cover_thumbnail.png")
    studio.WordSearchCreator._write_proof_bundle(folder, settings, seed, pages, package_data)
    ok, lines = studio.preflight(folder)
    (folder / "PUBLISHER_PREFLIGHT.txt").write_text(studio.package_preflight_text(folder), encoding="utf-8")
    if not ok:
        raise RuntimeError(f"{title} failed print preflight: {' | '.join(lines)}")
    warnings.extend(studio.publisher_safety_report(package_data)["warnings"])
    (folder / "PACKAGE_SCORECARD.txt").write_text(studio.package_scorecard_text(package_data, folder, pages, warnings), encoding="utf-8")
    (folder / "START_HERE.txt").write_text(f"KDP-SAFE SIGNATURE EDITION PACKAGE\n{'=' * 52}\n\nBook: {title}\n\nUPLOAD\n1. interior.pdf\n2. kdp_full_wrap.pdf\n\nLISTING\n- KDP_LISTING_KIT.txt\n- SIGNATURE_LISTING_DESCRIPTION.txt\n\nThis replacement package keeps all visible content inside the KDP-safe page area. Always run KDP Print Previewer before publishing.\n", encoding="utf-8")
    return folder


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    packages = [package(book) for book in BOOKS]
    (OUTPUT_DIR / "README.txt").write_text("KDP-safe replacement packages for the Grade 5 and Grade 8 Vocabulary Ladder Signature Editions. Original packages are untouched.\n", encoding="utf-8")
    print("\n".join(str(folder) for folder in packages))


if __name__ == "__main__":
    main()
