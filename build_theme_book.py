#!/usr/bin/env python3
"""End-to-end builder for a themed word-search book -- the piece
auto_factory.py doesn't cover, since that one only knows its hardcoded
Sudoku/Maze recipes and ignores the theme JSONs.

Feed it a theme JSON and it produces a full KDP book folder (interior.pdf,
cover.png, wrap.pdf, LISTING.md), then runs it through the same preflight gate
auto_factory uses so nothing gets marked ready until it actually passes.

    python3 build_theme_book.py --theme themes/beach-vacation.json

On author fields specifically (KDP guideline G201953870): the interior
/Author and front-cover author have to be the pen name -- a person, pulled
from the theme JSON's "author" field -- never the imprint. The build aborts
if it isn't. The imprint name only appears on the back cover."""
import argparse
import json
import os
import re
import subprocess
import sys

KDP = os.path.dirname(os.path.abspath(__file__))
PY = "/usr/bin/python3"
IMPRINT = "Evergreen Puzzle Press"          # brand — back cover only
PRESS_FLAG = "evergreen puzzle press"       # must NOT be the /Author


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def run(cmd):
    subprocess.run(cmd, check=True, cwd=KDP)


def page_count(pdf):
    from pypdf import PdfReader
    return len(PdfReader(pdf).pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", required=True, help="path to a theme JSON")
    ap.add_argument("--slug", help="output folder name under out/ (default: from theme filename)")
    ap.add_argument("--palette", help="cover palette (default: theme JSON 'palette' or the slug)")
    ap.add_argument("--seed", type=int, default=20260630)
    ap.add_argument("--badge", help="cover badge (default: '<N> LARGE PRINT PUZZLES')")
    a = ap.parse_args()

    theme_path = a.theme if os.path.isabs(a.theme) else os.path.join(KDP, a.theme)
    data = json.load(open(theme_path))
    title = data["title"]
    subtitle = data.get("subtitle", "")
    author = data.get("author", "").strip()
    n_puzzles = len(data["puzzles"])

    # --- defective-content rail: the /Author must be a person, never the imprint ---
    if not author:
        sys.exit(f"ABORT: theme {a.theme} has no 'author' — set the pen name 'E. P. Greenwood'.")
    if PRESS_FLAG in author.lower():
        sys.exit(f"ABORT: theme 'author' is the imprint ('{author}') — Amazon flags this (G201953870). "
                 f"Set it to a person/pen name (E. P. Greenwood) before building.")

    slug = a.slug or slugify(os.path.splitext(os.path.basename(theme_path))[0])
    palette = a.palette or data.get("palette") or slug
    badge = a.badge or f"{n_puzzles} LARGE PRINT PUZZLES"

    outdir = os.path.join(KDP, "out", slug)
    os.makedirs(outdir, exist_ok=True)
    interior = os.path.join(outdir, "interior.pdf")
    cover = os.path.join(outdir, "cover.png")
    wrap = os.path.join(outdir, "wrap.pdf")

    print(f"== {title} ==  ({n_puzzles} puzzles, palette={palette}, author={author})")

    run([PY, "wordsearch.py", "--themes", theme_path, "--out", interior, "--seed", str(a.seed)])
    pages = page_count(interior)

    run([PY, "cover.py", "--title", title, "--subtitle", subtitle, "--author", author,
         "--badge", badge, "--palette", palette, "--out", cover])

    back = _back_blurb(data, n_puzzles)
    run([PY, "wrap_cover.py", "--front", cover, "--pages", str(pages), "--palette", palette,
         "--title", title, "--author", IMPRINT, "--back", back, "--out", wrap])

    _write_listing(outdir, data, pages, author)

    # --- preflight compliance gate ---
    import preflight
    ok, results = preflight.preflight(outdir)
    print(f"\nPRE-FLIGHT: {'PASS' if ok else 'FAIL'}")
    for line in results:
        print(f"    {line}")
    if not ok:
        print("\n  DO NOT UPLOAD — fix the FAIL items above and rebuild.")
        sys.exit(1)

    print(f"\nDONE -> out/{slug}/  ({pages}pp)  interior.pdf + cover.png + wrap.pdf + LISTING.md")


def _back_blurb(data, n):
    return (f"Relax with {n} large print word search puzzles in a theme you'll love.\n\n"
            "Every puzzle is printed big and clear with generous spacing — one per page, easy on the eyes.\n\n"
            "Inside this book:\n"
            f"- {n} large print word searches, one per page\n"
            "- Big, easy-to-read letters and roomy grids\n"
            "- COMPLETE solutions for every puzzle at the back\n"
            "- A calm, screen-free way to relax and keep your mind active\n\n"
            "A wonderful gift for parents, grandparents, and anyone who loves a good puzzle.")


def _write_listing(outdir, data, pages, author):
    md = f"""# {data['title']}

**Title:** `{data['title']}`
**Subtitle:** `{data.get('subtitle','')}`
**Author (pen name):** `{author}`
**Imprint (cover/back only):** `{IMPRINT}`
**Files:** `interior.pdf` (manuscript) · `wrap.pdf` (print-ready cover) · `cover.png` (front)
**Pages:** {pages}  ·  8.5×11  ·  B&W  ·  white paper  ·  no bleed  ·  matte

## Settings (same every book)
Free KDP ISBN · Large-print CHECKED · Low-content UNCHECKED · AI-Generated: **No** (algorithmic
generation, not generative AI) · barcode UNCHECKED · all territories · **$9.99** (60% royalty tier).
"""
    open(os.path.join(outdir, "LISTING.md"), "w").write(md)


if __name__ == "__main__":
    main()
