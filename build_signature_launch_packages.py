"""Create two verified 100-puzzle Vocabulary Ladder Signature Edition packages.

This is deliberately non-destructive: it packages the project’s existing,
quality-gated Grade 5 and Grade 8 Signature source themes into a new dated
output folder.  It never alters a saved theme or an earlier book package.
"""
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
OUTPUT_DIR = APP_DIR / "out" / f"Signature Editions - {STAMP}"

BOOKS = (
    {
        "rank": 1,
        "slug": "grade_5_vocabulary",
        "theme": APP_DIR / "themes" / "Vocabulary Ladder Collection" / "Grades 5 to 12" / "vocabulary_ladder_grade_5_signature_edition.json",
        "art": APP_DIR / "cover_assets" / "background_photos" / "school_elementary_learning_v1.png",
        "palette": "kids",
        "difficulty": "Relaxing",
        "description": "Build stronger words and brighter confidence—one satisfying puzzle at a time. Vocabulary Ladder: Grade 5 Word Quest - Signature Edition is an expanded collection of 100 large-print word searches created around meaningful Grade 5 vocabulary. Each puzzle offers a fresh, screen-free way to practice words that support reading, writing, and everyday learning. With 1,200 words, no repeated words across the book, clear layouts, and complete solutions, it is a rewarding companion for independent practice, quiet classroom time, homeschool routines, and curious young readers.",
    },
    {
        "rank": 2,
        "slug": "grade_8_vocabulary",
        "theme": APP_DIR / "themes" / "Vocabulary Ladder Collection" / "Grades 5 to 12" / "vocabulary_ladder_grade_8_signature_edition.json",
        "art": APP_DIR / "cover_assets" / "background_photos" / "school_middle_learning_v1.png",
        "palette": "kids",
        "difficulty": "Standard",
        "description": "Level up vocabulary with a challenge that feels more like fun than homework. Vocabulary Ladder: Grade 8 Word Quest - Signature Edition brings together 100 large-print word searches built around meaningful Grade 8 vocabulary. Every puzzle has a fresh word list, helping students encounter 1,200 words without repeats across the book. Clear grids and complete solutions make this an inviting choice for independent study, classroom enrichment, homeschool learning, or any young reader ready to sharpen their word power.",
    },
)


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=APP_DIR, capture_output=True, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "A package command stopped unexpectedly.")


def start_here(folder: Path, title: str) -> None:
    (folder / "START_HERE.txt").write_text(
        f"SIGNATURE EDITION BOOK PACKAGE\n{'=' * 52}\n\nBook: {title}\n\n"
        "UPLOAD TO KDP\n1. interior.pdf - book inside pages\n2. kdp_full_wrap.pdf - full print cover\n\n"
        "FINISH THE LISTING\n- KDP_LISTING_KIT.txt\n- KDP_UPLOAD_CHECKLIST.txt\n"
        "- SIGNATURE_LISTING_DESCRIPTION.txt\n\n"
        "REVIEW FIRST\n- proof_review\\PROOF_REVIEW.txt\n- proof_review\\buyer_thumbnail.png\n- kdp_full_wrap_preview.png\n\n"
        "Always run KDP Print Previewer before publishing.\n", encoding="utf-8")


def package(book: dict[str, object]) -> Path:
    theme = Path(book["theme"])
    art = Path(book["art"])
    if not theme.is_file() or not art.is_file():
        raise RuntimeError(f"Missing Signature Edition source file: {theme if not theme.is_file() else art}")
    data = json.loads(theme.read_text(encoding="utf-8-sig"))
    title, subtitle = str(data["title"]), str(data["subtitle"])
    settings = {
        "theme": str(theme), "title": title, "subtitle": subtitle, "author": "Slade Puzzles",
        "imprint": "Slade Puzzles", "badge": "100 LARGE-PRINT PUZZLES - NO REPEATED WORDS",
        "difficulty": str(book["difficulty"]), "palette": str(book["palette"]), "style": "photo",
        "art": str(art), "art_focus": "center", "format_label": "LARGE PRINT", "signature_edition": True,
    }
    seed = 910000 + int(book["rank"])
    errors, warnings, _notes = studio.production_stop_errors(theme, seed, settings)
    if errors:
        raise RuntimeError(f"{title} failed the production stop: {' | '.join(errors)}")
    folder = OUTPUT_DIR / f"{book['rank']:02d}_{book['slug']}"
    folder.mkdir(parents=True, exist_ok=False)
    python = studio.WINDOWS_VENV_PYTHON if studio.WINDOWS_VENV_PYTHON.exists() else Path(sys.executable)
    interior, front, wrap = folder / "interior.pdf", folder / "front_cover.png", folder / "kdp_full_wrap.pdf"
    run([str(python), str(studio.ENGINE), "--themes", str(theme), "--out", str(interior), "--title", title, "--subtitle", subtitle, "--author", "Slade Puzzles", "--seed", str(seed), "--signature-edition"])
    run([str(python), str(studio.COVER_ENGINE), "--title", title, "--subtitle", subtitle, "--author", "Slade Puzzles", "--badge", settings["badge"], "--difficulty", settings["difficulty"], "--format-label", settings["format_label"], "--palette", settings["palette"], "--style", "photo", "--theme-file", str(theme), "--art", str(art), "--art-focus", "center", "--out", str(front)])
    pages = len(PdfReader(str(interior)).pages)
    package_data = studio.package_data_from_settings(data, settings)
    listing = studio.listing_kit_text(package_data)
    listing += "\n\nSIGNATURE EDITION — COPY-READY PREMIUM DESCRIPTION\n" + "=" * 56 + "\n\n" + str(book["description"]) + "\n"
    (folder / "KDP_LISTING_KIT.txt").write_text(listing, encoding="utf-8")
    (folder / "SIGNATURE_LISTING_DESCRIPTION.txt").write_text(str(book["description"]) + "\n", encoding="utf-8")
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
    warnings = list(warnings) + list(studio.publisher_safety_report(package_data)["warnings"])
    (folder / "PACKAGE_SCORECARD.txt").write_text(studio.package_scorecard_text(package_data, folder, pages, warnings), encoding="utf-8")
    start_here(folder, title)
    return folder


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    packages = [package(book) for book in BOOKS]
    (OUTPUT_DIR / "README.txt").write_text("Two verified 100-puzzle Vocabulary Ladder Signature Edition packages. Open each numbered folder and start with START_HERE.txt.\n", encoding="utf-8")
    print("\n".join(str(folder) for folder in packages))


if __name__ == "__main__":
    main()
