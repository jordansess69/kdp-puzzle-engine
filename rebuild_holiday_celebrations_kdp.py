"""Create a non-destructive KDP-safe replacement for Holiday Celebrations."""
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
THEME = APP_DIR / "themes" / "Production Launch 5" / "top5_04_holiday_celebrations_20260822_195201.json"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT = APP_DIR / "out" / f"Holiday Celebrations KDP Fixed - {STAMP}"


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=APP_DIR, capture_output=True, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "A package command stopped unexpectedly.")


def main() -> None:
    data = json.loads(THEME.read_text(encoding="utf-8-sig"))
    title = str(data["title"]); subtitle = str(data["subtitle"]); author = "Slade Puzzles"
    art = APP_DIR / str(data["cover_art_path"])
    if not art.is_file():
        raise RuntimeError(f"Missing original cover artwork: {art}")
    settings = {"theme": str(THEME), "title": title, "subtitle": subtitle, "author": author,
                "imprint": author, "badge": str(data["cover_badge"]),
                "difficulty": str(data["difficulty_label"]), "palette": str(data["palette"]),
                "style": "photo", "art": str(art), "art_focus": str(data.get("cover_art_focus") or "center"),
                "format_label": "LARGE PRINT", "signature_edition": False}
    # Verified against every puzzle: this deterministic seed places all words.
    seed = 700001
    errors, warnings, _notes = studio.quality_gate(THEME, seed)
    if errors:
        raise RuntimeError("The saved Holiday theme needs attention: " + " | ".join(errors))
    metadata_errors, metadata_warnings = studio.kdp_metadata_compliance_report(studio.package_data_from_settings(data, settings))
    if metadata_errors:
        raise RuntimeError("KDP metadata needs attention: " + " | ".join(metadata_errors))
    OUTPUT.mkdir(parents=True, exist_ok=False)
    python = studio.WINDOWS_VENV_PYTHON if studio.WINDOWS_VENV_PYTHON.exists() else Path(sys.executable)
    interior, front, wrap = OUTPUT / "interior.pdf", OUTPUT / "front_cover.png", OUTPUT / "kdp_full_wrap.pdf"
    run([str(python), str(studio.ENGINE), "--themes", str(THEME), "--out", str(interior), "--title", title, "--subtitle", subtitle, "--author", author, "--seed", str(seed)])
    run([str(python), str(studio.COVER_ENGINE), "--title", title, "--subtitle", subtitle, "--author", author,
         "--badge", settings["badge"], "--difficulty", settings["difficulty"], "--format-label", "LARGE PRINT",
         "--palette", settings["palette"], "--style", "photo", "--theme-file", str(THEME), "--art", str(art),
         "--art-focus", settings["art_focus"], "--out", str(front)])
    pages = len(PdfReader(str(interior)).pages)
    package_data = studio.package_data_from_settings(data, settings)
    (OUTPUT / "KDP_LISTING_KIT.txt").write_text(studio.listing_kit_text(package_data), encoding="utf-8")
    (OUTPUT / "KDP_UPLOAD_CHECKLIST.txt").write_text(studio.kdp_upload_checklist_text(package_data, pages), encoding="utf-8")
    studio.write_kdp_compliance_report(OUTPUT, package_data, pages)
    run([str(python), str(studio.WRAP_ENGINE), "--front", str(front), "--pages", str(pages),
         "--palette", settings["palette"], "--title", title, "--author", author,
         "--back", studio.package_blurb(data, package_data), "--out", str(wrap),
         "--preview-out", str(OUTPUT / "kdp_full_wrap_preview.png")])
    with Image.open(front) as image:
        image.thumbnail((510, 660), Image.LANCZOS)
        image.save(OUTPUT / "front_cover_thumbnail.png")
    studio.WordSearchCreator._write_proof_bundle(OUTPUT, settings, seed, pages, package_data)
    preflight_ok, messages = studio.preflight(OUTPUT)
    (OUTPUT / "PUBLISHER_PREFLIGHT.txt").write_text(studio.package_preflight_text(OUTPUT), encoding="utf-8")
    if not preflight_ok:
        raise RuntimeError("Print preflight needs attention: " + " | ".join(messages))
    warnings.extend(metadata_warnings)
    (OUTPUT / "PACKAGE_SCORECARD.txt").write_text(studio.package_scorecard_text(package_data, OUTPUT, pages, warnings), encoding="utf-8")
    (OUTPUT / "START_HERE.txt").write_text(
        "KDP-SAFE REPLACEMENT PACKAGE\n" + "=" * 52 + f"\n\nBook: {title}\n\n"
        "Upload interior.pdf and kdp_full_wrap.pdf from this folder.\n"
        "This replacement has the automatic safe-heading and even-page fixes.\n"
        "Review KDP_COMPLIANCE_REPORT.txt, then run KDP Print Previewer before publishing.\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
