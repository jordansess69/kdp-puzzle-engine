#!/usr/bin/env python3
"""Unattended book factory -- each run builds one complete, ready-to-upload
book into out/auto/<NNNN_slug>/: interior.pdf, cover.png, wrap.pdf, and a
LISTING.md with copy-paste fields.

Rotates across 6 genuinely different recipes (Sudoku/Mazes x easy/mixed/hard)
so scheduled runs don't spam near-identical titles, which Amazon penalizes.
After the 6th run it starts over as "Volume 2" with a fresh seed, so the
puzzles differ even when the recipe repeats. A state file tracks position in
the rotation. See com.evergreen.kdpfactory.plist for the launchd schedule."""
import os, re, csv, sys, subprocess, datetime

KDP = os.path.dirname(os.path.abspath(__file__))
PY = "/usr/bin/python3"
AUTO = os.path.join(KDP, "out", "auto")
AUTHOR = "E. P. Greenwood"

RECIPES = [
    dict(kind="sudoku", slug="lp_sudoku", profile="mixed", count=100,
         title="Large Print Sudoku",
         subtitle="100 Easy-to-Read Puzzles for Adults & Seniors, Easy to Hard, with Full Solutions",
         badge="100 LARGE PRINT PUZZLES",
         keywords=["large print sudoku for seniors", "sudoku puzzle book for adults",
                   "large print sudoku easy to hard", "brain games for seniors large print",
                   "sudoku books for adults", "easy to hard sudoku puzzle book", "sudoku gift"],
         categories="Crafts, Hobbies & Home → Games & Activities → Sudoku"),
    dict(kind="maze", slug="lp_mazes", profile="mixed", count=80,
         title="Large Print Mazes",
         subtitle="80 Relaxing Maze Puzzles for Adults & Seniors with Full Solutions",
         badge="80 LARGE PRINT MAZES",
         keywords=["large print mazes for adults", "maze puzzle book for seniors",
                   "large print maze book", "brain games for seniors", "mazes for adults",
                   "relaxing puzzle book large print", "maze gift book"],
         categories="Crafts, Hobbies & Home → Games & Activities → Mazes"),
    dict(kind="sudoku", slug="easy_sudoku", profile="easy", count=100,
         title="Easy Large Print Sudoku",
         subtitle="100 Gentle Puzzles for Beginners & Seniors with Big Numbers and Full Solutions",
         badge="100 EASY PUZZLES",
         keywords=["easy sudoku for seniors", "large print sudoku for beginners",
                   "easy sudoku puzzle book", "beginner sudoku large print",
                   "simple sudoku for adults", "easy brain games for seniors", "sudoku for beginners"],
         categories="Crafts, Hobbies & Home → Games & Activities → Sudoku"),
    dict(kind="maze", slug="easy_mazes", profile="easy", count=80,
         title="Easy Large Print Mazes",
         subtitle="80 Gentle Mazes for Beginners, Kids & Seniors with Full Solutions",
         badge="80 EASY MAZES",
         keywords=["easy mazes for kids", "large print mazes for seniors", "simple maze book",
                   "beginner maze puzzle book", "easy maze book for adults",
                   "mazes for kids ages 4-8", "large print easy mazes"],
         categories="Children's Books → Activity Books → Mazes  /  Crafts → Games & Activities"),
    dict(kind="sudoku", slug="hard_sudoku", profile="hard", count=100,
         title="Hard Large Print Sudoku",
         subtitle="100 Tough Puzzles for Experienced Solvers, Large Print, with Full Solutions",
         badge="100 HARD PUZZLES",
         keywords=["hard sudoku for adults", "difficult sudoku puzzle book",
                   "large print hard sudoku", "advanced sudoku book", "challenging sudoku for adults",
                   "expert sudoku puzzle book", "tough sudoku large print"],
         categories="Crafts, Hobbies & Home → Games & Activities → Sudoku"),
    dict(kind="maze", slug="hard_mazes", profile="hard", count=80,
         title="Challenging Large Print Mazes",
         subtitle="80 Tough Maze Puzzles for Adults Who Love a Challenge, with Full Solutions",
         badge="80 HARD MAZES",
         keywords=["hard mazes for adults", "difficult maze puzzle book", "challenging mazes",
                   "large print hard mazes", "complex maze book for adults",
                   "advanced maze puzzle book", "tough mazes large print"],
         categories="Crafts, Hobbies & Home → Games & Activities → Mazes"),
]


def page_count(pdf):
    # Use a real PDF parser, not a raw-byte regex (which miscounts on some PDFs).
    from pypdf import PdfReader
    return len(PdfReader(pdf).pages)


def run(cmd):
    subprocess.run(cmd, check=True, cwd=KDP, capture_output=True)


def blurb_for(r, item_word):
    prof = "" if r["profile"] == "mixed" else r["profile"] + " "
    return (f"Relax and enjoy {r['count']} {prof}LARGE PRINT "
            f"{item_word} made to be easy on the eyes.\n\n"
            f"Every puzzle is printed large and clear with plenty of room — one per page.\n\n"
            "Inside this book:\n"
            f"- {r['count']} large print {item_word}, one per page\n"
            f"- {'A gentle, beginner-friendly set' if r['profile']=='easy' else ('A tough set for experienced solvers' if r['profile']=='hard' else 'A relaxing mix of easy, medium and hard')}\n"
            "- Big, easy-to-read printing and generous spacing\n"
            "- COMPLETE solutions for every puzzle at the back\n"
            "- A calming, screen-free way to keep your mind active\n\n"
            "A wonderful gift for parents, grandparents, and anyone who loves a good brain game.")


def write_listing(outdir, r, title, pages):
    item = "Sudoku puzzles" if r["kind"] == "sudoku" else "mazes"
    kw = "  ·  ".join("`" + k + "`" for k in r["keywords"])
    md = f"""# {title}

**Title:** `{title}`
**Subtitle:** `{r['subtitle']}`
**Author (pen name):** `{AUTHOR}`
**Files:** `interior.pdf` (manuscript) · `wrap.pdf` (print-ready cover) · `cover.png` (front, for Cover Creator fallback)
**Pages:** {pages}  ·  8.5×11  ·  B&W  ·  white paper  ·  no bleed  ·  matte

## Description (paste into KDP)
{blurb_for(r, item)}

## Keywords (7)
{kw}

## Categories
{r['categories']}  ·  tick **Large Print**

## Settings (same every book)
Free KDP ISBN · Large-print CHECKED · Low-content UNCHECKED · AI-Generated: **No** (algorithmic generation,
not generative AI) · barcode UNCHECKED · all territories · **$9.99** (60% royalty tier) · NOT in KDP Select.
"""
    open(os.path.join(outdir, "LISTING.md"), "w").write(md)


def append_log(slug, r, pages, title, status="ready"):
    log = os.path.join(AUTO, "factory_log.csv")
    new = not os.path.exists(log)
    with open(log, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["date", "folder", "kind", "profile", "title", "pages", "status", "published?"])
        w.writerow([datetime.date.today().isoformat(), slug, r["kind"], r["profile"], title, pages, status, ""])


def main():
    os.makedirs(AUTO, exist_ok=True)
    idxfile = os.path.join(AUTO, ".run_index")
    idx = int(open(idxfile).read().strip()) if os.path.exists(idxfile) else 0
    r = RECIPES[idx % len(RECIPES)]
    vol = idx // len(RECIPES) + 1
    seed = 20260609 + idx * 7
    slug = f"{idx+1:04d}_{r['slug']}_v{vol}"
    outdir = os.path.join(AUTO, slug)
    os.makedirs(outdir, exist_ok=True)
    title = r["title"] + (f" — Volume {vol}" if vol > 1 else "")

    interior = os.path.join(outdir, "interior.pdf")
    cover = os.path.join(outdir, "cover.png")
    wrap = os.path.join(outdir, "wrap.pdf")

    gen = "sudoku.py" if r["kind"] == "sudoku" else "mazes.py"
    run([PY, gen, "--out", interior, "--title", title, "--author", AUTHOR,
         "--subtitle", r["subtitle"], "--count", str(r["count"]), "--profile", r["profile"], "--seed", str(seed)])
    pages = page_count(interior)

    covgen = "cover_sudoku.py" if r["kind"] == "sudoku" else "cover_maze.py"
    run([PY, covgen, "--title", r["title"], "--subtitle", r["subtitle"],
         "--author", AUTHOR, "--badge", r["badge"], "--out", cover])

    palette = "sudoku" if r["kind"] == "sudoku" else "maze"
    item = "Sudoku puzzles" if r["kind"] == "sudoku" else "mazes"
    run([PY, "wrap_cover.py", "--front", cover, "--pages", str(pages), "--palette", palette,
         "--title", title, "--author", AUTHOR, "--back", blurb_for(r, item), "--out", wrap])

    write_listing(outdir, r, title, pages)

    # Pre-flight compliance gate: catch the Amazon flags (author-as-imprint, spine
    # clearance, trim/spine math) BEFORE this book is treated as ready to upload.
    # A book is logged "ready" ONLY if it PASSES — a FAIL is logged as
    # "BLOCKED-preflight" so the defective book can never be picked up as ready.
    import preflight
    ok, results = preflight.preflight(outdir)
    print(f"  PRE-FLIGHT: {'PASS' if ok else 'FAIL'}")
    for line in results:
        if line.startswith(("FAIL", "WARN")):
            print(f"    {line}")
    if not ok:
        print("    DO NOT UPLOAD — this book FAILED pre-flight; logged BLOCKED-preflight, not ready.")

    append_log(slug, r, pages, title, status="ready" if ok else "BLOCKED-preflight")
    open(idxfile, "w").write(str(idx + 1))

    print(f"DONE -> out/auto/{slug}/  ({r['kind']} / {r['profile']} / {pages}pp)")
    print(f"  interior.pdf + cover.png + wrap.pdf + LISTING.md   (book #{idx+1}, next run builds a different one)")


if __name__ == "__main__":
    main()
