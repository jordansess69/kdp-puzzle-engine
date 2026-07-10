#!/usr/bin/env python3
"""preflight.py — KDP compliance pre-flight for a built book BEFORE upload.

Catches the exact issues that have triggered Amazon review flags (author set to
the imprint name; spine text too close to the edge on thin books) plus the basic
print-spec checks, so a book is never uploaded only to bounce back.

Checks per book folder (expects interior.pdf + wrap.pdf):
  - interior page size == 8.5 x 11 in (612 x 792 pt)
  - interior page count is sane (>0)
  - interior /Author is a PERSON, not the imprint "Evergreen Puzzle Press"
  - wrap.pdf dimensions == KDP full-wrap formula for the actual page count:
        width  = TRIM_W*2 + pages*SPINE_FACTOR + BLEED*2
        height = TRIM_H + BLEED*2
  - thin book (<100 pages): KDP requires a BLANK spine — flag to verify

Usage:
    /usr/bin/python3 preflight.py out/auto/0001_lp_sudoku_v1
    /usr/bin/python3 preflight.py            # scan every out/auto/* book
Exit code is nonzero if any book FAILS, so auto_factory can gate on it.
"""
import os
import sys
import glob

from pypdf import PdfReader

HERE = os.path.dirname(os.path.abspath(__file__))

# Must match wrap_cover.py exactly.
TRIM_W, TRIM_H = 8.5, 11.0
BLEED = 0.125
SPINE_FACTOR = 0.002252  # white paper, B&W
PT = 72.0                 # points per inch
TOL_PT = 4.0             # ~0.055" tolerance for rounding/raster

IMPRINT = "evergreen puzzle press"  # must NOT be the author


def _pages(reader):
    return len(reader.pages)


def _page_size_pt(reader):
    box = reader.pages[0].mediabox
    return float(box.width), float(box.height)


def preflight(book_dir):
    """Return (ok: bool, results: list[str]). Each result is 'PASS .' / 'FAIL .' / 'WARN .'."""
    res = []
    interior = os.path.join(book_dir, "interior.pdf")
    wrap = os.path.join(book_dir, "wrap.pdf")

    if not os.path.isfile(interior):
        return False, [f"FAIL missing interior.pdf in {book_dir}"]
    if not os.path.isfile(wrap):
        return False, [f"FAIL missing wrap.pdf in {book_dir}"]

    ir = PdfReader(interior)
    pages = _pages(ir)

    # 1) page count sane
    if pages > 0:
        res.append(f"PASS interior has {pages} pages")
    else:
        res.append("FAIL interior has 0 pages")

    # 2) interior trim size
    w, h = _page_size_pt(ir)
    exp_w, exp_h = TRIM_W * PT, TRIM_H * PT
    if abs(w - exp_w) <= TOL_PT and abs(h - exp_h) <= TOL_PT:
        res.append(f"PASS interior trim {w/PT:.3f}x{h/PT:.3f} in (8.5x11)")
    else:
        res.append(f"FAIL interior trim {w/PT:.3f}x{h/PT:.3f} in, expected 8.5x11")

    # 3) author must be a person, not the imprint
    author = (ir.metadata.author if ir.metadata else None) or ""
    if not author.strip():
        res.append("WARN interior /Author metadata is empty (set the pen name, e.g. 'E. P. Greenwood')")
    elif IMPRINT in author.lower():
        res.append(f"FAIL interior /Author is the imprint ('{author}') — Amazon flags this; use a person/pen name")
    else:
        res.append(f"PASS interior /Author is a person-style name ('{author}')")

    # 4) wrap dimensions vs the KDP full-wrap formula for THIS page count
    wr = PdfReader(wrap)
    ww, wh = _page_size_pt(wr)
    exp_full_w = (TRIM_W * 2 + pages * SPINE_FACTOR + BLEED * 2) * PT
    exp_full_h = (TRIM_H + BLEED * 2) * PT
    if abs(ww - exp_full_w) <= TOL_PT and abs(wh - exp_full_h) <= TOL_PT:
        res.append(f"PASS wrap {ww/PT:.3f}x{wh/PT:.3f} in matches formula for {pages}pp")
    else:
        res.append(f"FAIL wrap {ww/PT:.3f}x{wh/PT:.3f} in, expected "
                   f"{exp_full_w/PT:.3f}x{exp_full_h/PT:.3f} for {pages}pp")

    # 5) thin-book spine rule
    if pages < 100:
        res.append(f"WARN {pages}pp < 100 — KDP requires a BLANK spine (no text); verify wrap has no spine text")
    else:
        res.append(f"PASS {pages}pp >= 100 — spine text allowed")

    ok = not any(r.startswith("FAIL") for r in res)
    return ok, res


def _scan_dirs(argv):
    if len(argv) > 1:
        return [argv[1]]
    return sorted(glob.glob(os.path.join(HERE, "out", "auto", "*")))


def main():
    dirs = _scan_dirs(sys.argv)
    if not dirs:
        print("No book folders found.")
        return 1
    all_ok = True
    for d in dirs:
        if not os.path.isdir(d):
            continue
        ok, results = preflight(d)
        all_ok = all_ok and ok
        flag = "OK  " if ok else "FAIL"
        print(f"\n[{flag}] {os.path.basename(d)}")
        for r in results:
            print(f"    {r}")
    print(f"\n{'ALL PASSED' if all_ok else 'SOME BOOKS FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
