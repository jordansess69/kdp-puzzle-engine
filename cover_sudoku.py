#!/usr/bin/env python3
"""
cover_sudoku.py — print-ready front cover for the LARGE PRINT SUDOKU book.

Same professional layout as cover.py, but the hero element is a real, valid SUDOKU grid
(partially filled, bold 3x3 boxes) instead of a word-search grid. 2550x3300 @ 300 DPI
for an 8.5x11 front cover — feed to KDP Cover Creator, which builds the back + spine.

    /usr/bin/python3 cover_sudoku.py \
        --title "Large Print Sudoku" \
        --subtitle "100 Easy-to-Read Puzzles for Adults & Seniors, with Full Solutions" \
        --author "Evergreen Puzzle Press" --badge "100 LARGE PRINT PUZZLES" \
        --out out/sudoku_cover.png
"""
import argparse, os
from PIL import Image, ImageDraw, ImageFont

W, H = 2550, 3300

PALETTE = {  # calm blue/navy — deliberately distinct from the word-search line
    "bg":     (237, 242, 249),
    "accent": (72, 104, 156),
    "deep":   (22, 41, 78),
    "mute":   (108, 122, 148),
    "hi":     (255, 211, 84),
    "cell":   (252, 253, 255),
}

ARIALB = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
GEORGIA = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"
MONO = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

# A real, valid solved Sudoku grid (the classic). We show a subset as "givens".
SOLVED = [
    [5, 3, 4, 6, 7, 8, 9, 1, 2],
    [6, 7, 2, 1, 9, 5, 3, 4, 8],
    [1, 9, 8, 3, 4, 2, 5, 6, 7],
    [8, 5, 9, 7, 6, 1, 4, 2, 3],
    [4, 2, 6, 8, 5, 3, 7, 9, 1],
    [7, 1, 3, 9, 2, 4, 8, 5, 6],
    [9, 6, 1, 5, 3, 7, 2, 8, 4],
    [2, 8, 7, 4, 1, 9, 6, 3, 5],
    [3, 4, 5, 2, 8, 6, 1, 7, 9],
]
# Which cells are shown on the cover (1) vs blank (0) — a balanced, real-looking pattern.
GIVENS = [
    [1, 0, 0, 0, 1, 0, 0, 0, 1],
    [0, 1, 0, 1, 0, 1, 0, 1, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 0],
    [0, 1, 0, 1, 0, 0, 0, 1, 0],
    [1, 0, 0, 0, 1, 0, 0, 0, 1],
    [0, 1, 0, 0, 0, 1, 0, 1, 0],
    [0, 0, 1, 0, 0, 0, 1, 0, 0],
    [0, 1, 0, 1, 0, 1, 0, 1, 0],
    [1, 0, 0, 0, 1, 0, 0, 0, 1],
]


def f(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype(ARIALB, size)


def wrap(d, text, fnt, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def hero_sudoku(d, cx, cy, cell):
    P = PALETTE
    size = 9 * cell
    x0, y0 = cx - size // 2, cy - size // 2

    # cell background
    d.rectangle([x0, y0, x0 + size, y0 + size], fill=P["cell"])

    # subtle highlight behind the centre 3x3 box
    hx0, hy0 = x0 + 3 * cell, y0 + 3 * cell
    d.rectangle([hx0, hy0, hx0 + 3 * cell, hy0 + 3 * cell], fill=(255, 240, 196))

    # thin gridlines
    for i in range(10):
        d.line([(x0 + i * cell, y0), (x0 + i * cell, y0 + size)], fill=P["accent"], width=2)
        d.line([(x0, y0 + i * cell), (x0 + size, y0 + i * cell)], fill=P["accent"], width=2)
    # heavy 3x3 box lines
    for i in (0, 3, 6, 9):
        d.line([(x0 + i * cell, y0), (x0 + i * cell, y0 + size)], fill=P["deep"], width=8)
        d.line([(x0, y0 + i * cell), (x0 + size, y0 + i * cell)], fill=P["deep"], width=8)
    # outer border
    d.rectangle([x0, y0, x0 + size, y0 + size], outline=P["deep"], width=10)

    # numbers — fill EVERY cell (givens dark/bold, the rest muted) instead of leaving
    # blanks. A partly-blank 9x9 grid is a filled/empty matrix that KDP's cover scanner
    # mis-reads as a 2D barcode ("remove your custom barcode" -> Approve disabled). A
    # fully-inked grid still reads clearly as a sudoku but has no barcode-like matrix.
    nf = ImageFont.truetype(MONO, int(cell * 0.62))
    for r in range(9):
        for c in range(9):
            ch = str(SOLVED[r][c])
            tw = d.textlength(ch, font=nf)
            col = P["deep"] if GIVENS[r][c] else P["mute"]
            d.text((x0 + c * cell + (cell - tw) / 2, y0 + r * cell + cell * 0.14),
                   ch, font=nf, fill=col)


def corner_tile(d, cx, cy, s, num):
    P = PALETTE
    d.rounded_rectangle([cx - s, cy - s, cx + s, cy + s], radius=int(s * 0.28),
                        fill=None, outline=P["accent"], width=6)
    nf = f(MONO, int(s * 1.2))
    tw = d.textlength(num, font=nf)
    d.text((cx - tw / 2, cy - s * 0.78), num, font=nf, fill=P["accent"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="Large Print Sudoku")
    ap.add_argument("--subtitle", default="100 Easy-to-Read Puzzles for Adults & Seniors, with Full Solutions")
    ap.add_argument("--author", default="Evergreen Puzzle Press")
    ap.add_argument("--badge", default="100 LARGE PRINT PUZZLES")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    P = PALETTE
    img = Image.new("RGB", (W, H), P["bg"])
    d = ImageDraw.Draw(img)

    # double frame
    m = 120
    d.rectangle([m, m, W - m, H - m], outline=P["accent"], width=8)
    d.rectangle([m + 32, m + 32, W - m - 32, H - m - 32], outline=P["accent"], width=3)

    # corner number tiles (sudoku motif)
    for (fx, fy, num) in [(0.12, 0.10, "9"), (0.88, 0.10, "1"),
                          (0.12, 0.93, "4"), (0.88, 0.93, "7")]:
        corner_tile(d, int(W * fx), int(H * fy), 70, num)

    # "LARGE PRINT" bar
    lpf = f(IMPACT, 138)
    lp = "LARGE PRINT"
    lpw = d.textlength(lp, font=lpf)
    bar_pad_x, bar_pad_y = 60, 28
    bx0, by0 = (W - lpw) / 2 - bar_pad_x, 380 - bar_pad_y
    bx1, by1 = (W + lpw) / 2 + bar_pad_x, 380 + 138 + bar_pad_y
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=22, fill=P["deep"])
    d.text(((W - lpw) / 2, 380 - 6), lp, font=lpf, fill=P["hi"])

    # niche line ("SUDOKU")
    title_rest = a.title.upper()
    if title_rest.startswith("LARGE PRINT "):
        title_rest = title_rest[len("LARGE PRINT "):]
    tf = f(GEORGIA, 230)
    y = by1 + 70
    for ln in wrap(d, title_rest, tf, W - 2 * (m + 90)):
        tw = d.textlength(ln, font=tf)
        d.text(((W - tw) / 2, y), ln, font=tf, fill=P["deep"])
        y += 250

    # divider
    y += 6
    d.line([(W // 2 - 240, y), (W // 2 + 240, y)], fill=P["accent"], width=4)
    y += 56

    # subtitle
    sf = f(ARIAL, 62)
    for ln in wrap(d, a.subtitle, sf, W - 2 * (m + 170)):
        tw = d.textlength(ln, font=sf)
        d.text(((W - tw) / 2, y), ln, font=sf, fill=P["mute"])
        y += 86

    # hero sudoku grid
    grid_cell = 150
    grid_cy = 2010
    hero_sudoku(d, W // 2, grid_cy, grid_cell)

    # badge below grid
    grid_bottom = grid_cy + (9 * grid_cell) // 2
    if a.badge:
        vf = f(IMPACT, 104)
        vw = d.textlength(a.badge, font=vf)
        by = grid_bottom + 120
        bx = (W - vw) / 2
        pad = 64
        d.rounded_rectangle([bx - pad, by - 26, bx + vw + pad, by + 124], radius=30,
                            fill=P["hi"], outline=P["deep"], width=5)
        d.text((bx, by - 8), a.badge, font=vf, fill=P["deep"])

    # author
    if a.author:
        af = f(ARIALB, 70)
        aw = d.textlength(a.author, font=af)
        d.text(((W - aw) / 2, H - 290), a.author, font=af, fill=P["deep"])

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    img.save(a.out, "PNG")
    print(f"DONE -> {a.out}  ({W}x{H})")


if __name__ == "__main__":
    main()
