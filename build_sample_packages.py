"""Non-destructive visual smoke test for three existing Word Search Creator themes."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

from preflight import preflight, report_text
from word_search_creator import (
    APP_DIR, COVER_ENGINE, ENGINE, OUTPUT_DIR, WRAP_ENGINE,
    listing_kit_text, package_blurb, package_data_from_settings,
    photo_choice_palette, puzzle_difficulty_label, quality_gate,
    recommend_background_photo,
)

SAMPLES = (
    Path("themes/Market Opportunity Collection/market_13_american_history_word_search.json"),
    Path("themes/Market Opportunity Collection/market_15_space_and_astronomy_word_search.json"),
    Path("themes/Market Opportunity Collection/market_16_cars_trucks_and_road_trips_word_search.json"),
)


def run(command: list[str]) -> None:
    completed = subprocess.run(command, cwd=APP_DIR, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Generator stopped unexpectedly.")


def main() -> None:
    root = OUTPUT_DIR / "sample_package_review"
    root.mkdir(parents=True, exist_ok=True)
    for number, relative in enumerate(SAMPLES, 1):
        theme = APP_DIR / relative
        data = json.loads(theme.read_text(encoding="utf-8-sig"))
        errors, warnings, notes = quality_gate(theme, 8100 + number)
        if errors:
            raise RuntimeError(f"{theme.name} did not pass the normal quality gate: {' | '.join(errors)}")
        folder = root / f"sample_{number}_{theme.stem}"
        folder.mkdir(parents=True, exist_ok=True)
        interior = folder / "interior.pdf"
        cover = folder / "front_cover.png"
        wrap = folder / "kdp_full_wrap.pdf"
        title = str(data.get("title") or theme.stem)
        subtitle = str(data.get("subtitle") or "")
        author = str(data.get("author") or "Slade Puzzles")
        choice = recommend_background_photo(data)
        art = APP_DIR / str(choice.get("file") or "") if choice else None
        palette = photo_choice_palette(choice, str(data.get("palette") or "nature")) if choice else str(data.get("palette") or "nature")
        style = "photo" if art and art.exists() else str(data.get("cover_style") or "playful")
        badge = str(data.get("cover_badge") or f"{len(data.get('puzzles', []))} WORD SEARCH PUZZLES")
        run([sys.executable, str(ENGINE), "--themes", str(theme), "--out", str(interior), "--title", title, "--subtitle", subtitle, "--author", author, "--seed", str(8100 + number)])
        pages = len(PdfReader(str(interior)).pages)
        cover_command = [sys.executable, str(COVER_ENGINE), "--title", title, "--subtitle", subtitle, "--author", author,
             "--badge", badge, "--difficulty", puzzle_difficulty_label(data), "--palette", palette,
             "--style", style, "--theme-file", str(theme), "--out", str(cover)]
        if art and art.exists():
            cover_command.extend(["--art", str(art), "--art-focus", str(choice.get("focus") or "center")])
        run(cover_command)
        package_data = package_data_from_settings(data, {"title": title, "subtitle": subtitle, "author": author, "palette": palette, "style": style, "badge": badge})
        run([sys.executable, str(WRAP_ENGINE), "--front", str(cover), "--pages", str(pages), "--palette", palette,
             "--title", title, "--author", author, "--back", package_blurb(data, package_data), "--out", str(wrap), "--preview-out", str(folder / "kdp_full_wrap_preview.png")])
        ok, lines = preflight(folder)
        (folder / "PUBLISHER_PREFLIGHT.txt").write_text(report_text(folder), encoding="utf-8")
        (folder / "KDP_LISTING_KIT.txt").write_text(listing_kit_text(package_data), encoding="utf-8")
        (folder / "SAMPLE_REVIEW.txt").write_text(
            f"Sample {number}: {title}\nPages: {pages}\nCover: {palette} / {style}\n"
            f"Warnings: {len(warnings)}\nPreflight: {'PASS' if ok else 'REVIEW'}\n\n" + "\n".join(notes + warnings + lines) + "\n",
            encoding="utf-8",
        )
        print(f"Created {folder} ({pages} pages; preflight={'PASS' if ok else 'REVIEW'})")


if __name__ == "__main__":
    main()
