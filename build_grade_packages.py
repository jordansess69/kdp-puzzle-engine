"""Build complete, proofed KDP packages for the standard Grade 5-12 series."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

import word_search_creator as studio


APP_DIR = Path(__file__).resolve().parent
THEMES_DIR = APP_DIR / "themes" / "Vocabulary Ladder Collection" / "Grades 5 to 12"
OUTPUT_DIR = APP_DIR / "out" / "Vocabulary Ladder - Grades 5 to 12 - Final Corrected Photo Covers"


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=APP_DIR, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def build(theme: Path, seed: int) -> Path:
    data = json.loads(theme.read_text(encoding="utf-8-sig"))
    title = str(data["title"])
    target = OUTPUT_DIR / f"Grade_{data['detected_topic'].split()[1]}"
    target.mkdir(parents=True, exist_ok=False)
    art = studio.recommend_background_photo(data)
    art_path = str(APP_DIR / art["file"]) if art else ""
    palette = str(data.get("palette") or "kids")
    # This companion package set demonstrates the automatically selected
    # artwork; the original classic-cover package set remains untouched.
    style = "photo" if art else str(data.get("cover_style") or "gallery")
    badge = str(data.get("cover_badge") or f"INCLUDES {len(data.get('puzzles', []))} PUZZLES")
    interior, front, wrap = target / "interior.pdf", target / "front_cover.png", target / "kdp_full_wrap.pdf"
    python = studio.WINDOWS_VENV_PYTHON if studio.WINDOWS_VENV_PYTHON.exists() else Path(sys.executable)
    run([str(python), str(studio.ENGINE), "--themes", str(theme), "--out", str(interior), "--title", title, "--subtitle", str(data.get("subtitle") or ""), "--author", str(data.get("author") or "Slade Puzzles"), "--seed", str(seed)])
    cover = [str(python), str(studio.COVER_ENGINE), "--title", title, "--subtitle", str(data.get("subtitle") or ""), "--author", str(data.get("author") or "Slade Puzzles"), "--badge", badge, "--difficulty", str(data.get("difficulty_label") or "Standard"), "--palette", palette, "--style", style, "--theme-file", str(theme), "--out", str(front)]
    if art_path:
        cover.extend(["--art", art_path, "--art-focus", str(art.get("focus") or "center")])
    run(cover)
    pages = len(PdfReader(str(interior)).pages)
    settings = {"title": title, "subtitle": str(data.get("subtitle") or ""), "author": str(data.get("author") or "Slade Puzzles"), "palette": palette, "style": style, "badge": badge}
    package_data = studio.package_data_from_settings(data, settings)
    run([str(python), str(studio.WRAP_ENGINE), "--front", str(front), "--pages", str(pages), "--palette", palette, "--title", title, "--author", "Slade Puzzles", "--back", studio.package_blurb(data, package_data), "--out", str(wrap), "--preview-out", str(target / "kdp_full_wrap_preview.png")])
    (target / "KDP_UPLOAD_CHECKLIST.txt").write_text(studio.kdp_upload_checklist_text(package_data, pages), encoding="utf-8")
    (target / "KDP_LISTING_KIT.txt").write_text(studio.listing_kit_text(package_data), encoding="utf-8")
    ok, details = studio.preflight(target)
    (target / "PUBLISHER_PREFLIGHT.txt").write_text(studio.package_preflight_text(target), encoding="utf-8")
    if not ok:
        raise RuntimeError("Preflight failed: " + " | ".join(details))
    (target / "PACKAGE_SCORECARD.txt").write_text(studio.package_scorecard_text(package_data, target, pages), encoding="utf-8")
    return target


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for grade in range(5, 13):
        theme = THEMES_DIR / f"vocabulary_ladder_grade_{grade}.json"
        print(build(theme, 5000 + grade))
    print(f"Completed Grade 5-12 package set at {datetime.now():%Y-%m-%d %H:%M}")


if __name__ == "__main__":
    main()
