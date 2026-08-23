#!/usr/bin/env python3
"""Refresh existing local listing files with the current compliant KDP template.

Original listing text is preserved alongside each refreshed file with the
`.before_kdp_audit.txt` suffix. Files whose title cannot be safely matched to
an active theme are left unchanged and reported.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from word_search_creator import OUTPUT_DIR, THEMES_DIR, listing_kit_text


def title_from_text(text: str) -> str:
    match = re.search(r"(?:^|\n)TITLE\s*\n([^\n]+)", text, flags=re.I)
    return match.group(1).strip() if match else ""


def main() -> None:
    themes: dict[str, dict] = {}
    for path in THEMES_DIR.rglob("*.json"):
        if "Used Themes" in path.parts:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            title = str(data.get("title") or "").strip().casefold()
            if title and isinstance(data.get("puzzles"), list):
                themes[title] = data
        except (OSError, json.JSONDecodeError):
            continue
    changed = skipped = 0
    report: list[str] = []
    for path in OUTPUT_DIR.rglob("*.txt"):
        if path.name not in {"kdp_listing_kit.txt", "listing_notes.txt"}:
            continue
        try:
            old = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        title = title_from_text(old)
        data = themes.get(title.casefold())
        if not data:
            skipped += 1; report.append(f"Skipped (no exact active theme title): {path}"); continue
        backup = path.with_name(path.stem + ".before_kdp_audit.txt")
        if not backup.exists():
            backup.write_text(old, encoding="utf-8")
        path.write_text(listing_kit_text(data), encoding="utf-8")
        changed += 1; report.append(f"Refreshed: {path}")
    target = OUTPUT_DIR / "kdp_listing_audit_report.txt"
    target.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Refreshed {changed} listing file(s); skipped {skipped}. Report: {target}")


if __name__ == "__main__":
    main()
