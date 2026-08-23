"""Build representative complete packages for a visual and print-readiness audit."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

import word_search_creator as studio


APP_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = APP_DIR / "out" / "3_6 Complete Product Audit Samples"
SAMPLES = {
    "01_zion_national_park": APP_DIR / "themes" / "national_parks_02_zion.json",
    "02_space_astronomy": APP_DIR / "themes" / "Market Opportunity Collection" / "market_15_space_and_astronomy_word_search.json",
    "03_christmas": APP_DIR / "themes" / "christmas_100.json",
}


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=APP_DIR, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def build(name: str, theme: Path, seed: int) -> Path:
    data = json.loads(theme.read_text(encoding="utf-8-sig"))
    choice = studio.recommend_background_photo(data)
    if not choice:
        raise RuntimeError(f"No photo match for {theme.name}")
    target = OUTPUT_DIR / name
    target.mkdir(parents=True, exist_ok=False)
    python = studio.WINDOWS_VENV_PYTHON if studio.WINDOWS_VENV_PYTHON.exists() else Path(sys.executable)
    title = str(data.get("title") or "Word Search")
    subtitle = str(data.get("subtitle") or "")
    # The brand belongs on the cover as an imprint, never as the KDP contributor.
    # Keep this standalone audit tool aligned with the app's contributor safeguard.
    author = str(data.get("author") or "Jordan M. Slade")
    if author.strip().casefold() == "slade puzzles":
        author = "Jordan M. Slade"
    count = len(data.get("puzzles", []))
    settings = {
        "title": title, "subtitle": subtitle, "author": author,
        "badge": str(data.get("cover_badge") or f"INCLUDES {count} PUZZLES"),
        "difficulty": studio.puzzle_difficulty_label(data),
        "palette": studio.photo_choice_palette(choice, str(data.get("palette") or "nature")),
        "style": "photo", "imprint": str(data.get("cover_imprint") or "Slade Puzzles"),
        "theme": str(theme), "art": str(APP_DIR / str(choice["file"])), "art_focus": str(choice.get("focus") or "center"),
    }
    interior = target / "interior.pdf"
    front = target / "front_cover.png"
    wrap = target / "kdp_full_wrap.pdf"
    run([str(python), str(studio.ENGINE), "--themes", str(theme), "--out", str(interior), "--title", title, "--subtitle", subtitle, "--author", author, "--seed", str(seed)])
    run([str(python), str(studio.COVER_ENGINE), "--title", title, "--subtitle", subtitle, "--author", author, "--badge", settings["badge"], "--difficulty", settings["difficulty"], "--palette", settings["palette"], "--style", settings["style"], "--theme-file", str(theme), "--art", settings["art"], "--art-focus", settings["art_focus"], "--out", str(front)])
    pages = len(PdfReader(str(interior)).pages)
    package_data = studio.package_data_from_settings(data, settings)
    run([str(python), str(studio.WRAP_ENGINE), "--front", str(front), "--pages", str(pages), "--palette", settings["palette"], "--title", title, "--author", author, "--back", studio.package_blurb(data, package_data), "--out", str(wrap), "--preview-out", str(target / "kdp_full_wrap_preview.png")])
    (target / "KDP_UPLOAD_CHECKLIST.txt").write_text(studio.kdp_upload_checklist_text(package_data, pages), encoding="utf-8")
    (target / "KDP_LISTING_KIT.txt").write_text(studio.listing_kit_text(package_data), encoding="utf-8")
    ok, lines = studio.preflight(target)
    (target / "PUBLISHER_PREFLIGHT.txt").write_text(studio.package_preflight_text(target), encoding="utf-8")
    (target / "PACKAGE_SCORECARD.txt").write_text(studio.package_scorecard_text(package_data, target, pages), encoding="utf-8")
    if not ok:
        raise RuntimeError("Preflight failed: " + " | ".join(lines))
    return target


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for number, (name, theme) in enumerate(SAMPLES.items(), start=1):
        target = OUTPUT_DIR / name
        print(f"Keeping completed package: {target}" if target.exists() else build(name, theme, 8200 + number))


if __name__ == "__main__":
    main()
