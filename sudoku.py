#!/usr/bin/env python3
"""
sudoku.py — code-generated, print-ready LARGE PRINT Sudoku book for KDP.

Standard 9x9 Sudoku. Generates valid solved grids by applying random symmetry-preserving
transformations to a known base grid, then removes cells per difficulty level.

USAGE (run with /usr/bin/python3 for reportlab + PIL):
    /usr/bin/python3 sudoku.py --out out/sudoku_v1.pdf \
        --title "Large Print Sudoku" \
        --author "Evergreen Puzzle Press" \
        --count 100

Default: 100 puzzles, mixed difficulty (40 easy, 35 medium, 25 hard).
Each puzzle on its own page in large print. Full solutions at the back.
"""
import argparse, json, os, random
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

PAGE_W, PAGE_H = letter
MARGIN = 54

FONTS = {
    "Sans":  "/System/Library/Fonts/Supplemental/Arial.ttf",
    "SansB": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "MonoB": "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
}


def register_fonts():
    for name, path in FONTS.items():
        pdfmetrics.registerFont(TTFont(name, path))


# ---------------- Sudoku grid generation ----------------
BASE = [
    [1, 2, 3, 4, 5, 6, 7, 8, 9],
    [4, 5, 6, 7, 8, 9, 1, 2, 3],
    [7, 8, 9, 1, 2, 3, 4, 5, 6],
    [2, 3, 4, 5, 6, 7, 8, 9, 1],
    [5, 6, 7, 8, 9, 1, 2, 3, 4],
    [8, 9, 1, 2, 3, 4, 5, 6, 7],
    [3, 4, 5, 6, 7, 8, 9, 1, 2],
    [6, 7, 8, 9, 1, 2, 3, 4, 5],
    [9, 1, 2, 3, 4, 5, 6, 7, 8],
]


def make_solved(rng):
    """Apply random symmetry-preserving transforms to BASE; result is a fresh valid Sudoku solution."""
    g = [row[:] for row in BASE]

    # Permute digits 1-9
    perm = list(range(1, 10))
    rng.shuffle(perm)
    g = [[perm[v - 1] for v in row] for row in g]

    # Swap rows within each band (3 bands of 3 rows each)
    for band in range(3):
        rows = [band * 3 + i for i in range(3)]
        rng.shuffle(rows)
        new_rows = [g[r] for r in rows]
        for i in range(3):
            g[band * 3 + i] = new_rows[i]

    # Swap columns within each stack (3 stacks of 3 cols each)
    for stack in range(3):
        cols = [stack * 3 + i for i in range(3)]
        rng.shuffle(cols)
        for r in range(9):
            row = g[r]
            new_vals = [row[c] for c in cols]
            for i in range(3):
                g[r][stack * 3 + i] = new_vals[i]

    # Swap bands (the 3 row-bands as a whole)
    bands = [0, 1, 2]
    rng.shuffle(bands)
    new_g = []
    for b in bands:
        new_g.extend(g[b * 3:(b + 1) * 3])
    g = new_g

    # Swap stacks (the 3 col-stacks as a whole)
    stacks = [0, 1, 2]
    rng.shuffle(stacks)
    for r in range(9):
        row = g[r]
        new_row = []
        for s in stacks:
            new_row.extend(row[s * 3:(s + 1) * 3])
        g[r] = new_row

    # Optional transpose (50% chance) — rows<->cols, still valid Sudoku
    if rng.random() < 0.5:
        g = [[g[c][r] for c in range(9)] for r in range(9)]

    return g


ALL_BITS = 0b1111111110  # bits for digits 1..9 (bit 0 unused)


def count_solutions(grid, limit=2):
    """Count solutions (capped at `limit`) of a 9x9 grid (0 = empty) via MRV backtracking.
    Returns as soon as `limit` is reached. Used to GUARANTEE puzzle uniqueness."""
    rows = [0] * 9
    cols = [0] * 9
    boxes = [0] * 9
    for r in range(9):
        for c in range(9):
            v = grid[r][c]
            if v:
                b = 1 << v
                rows[r] |= b; cols[c] |= b; boxes[(r // 3) * 3 + c // 3] |= b

    cnt = 0

    def solve():
        nonlocal cnt
        # pick the empty cell with the fewest candidates (MRV) for speed
        best = None
        best_cands = 0
        best_n = 99
        for r in range(9):
            for c in range(9):
                if grid[r][c] == 0:
                    used = rows[r] | cols[c] | boxes[(r // 3) * 3 + c // 3]
                    cand = ALL_BITS & ~used
                    n = bin(cand).count("1")
                    if n == 0:
                        return            # dead end, no solution down this branch
                    if n < best_n:
                        best_n = n; best = (r, c); best_cands = cand
                        if n == 1:
                            break
            if best_n == 1:
                break
        if best is None:
            cnt += 1                       # all cells filled -> one full solution
            return
        r, c = best
        bi = (r // 3) * 3 + c // 3
        for v in range(1, 10):
            bit = 1 << v
            if best_cands & bit:
                grid[r][c] = v; rows[r] |= bit; cols[c] |= bit; boxes[bi] |= bit
                solve()
                grid[r][c] = 0; rows[r] &= ~bit; cols[c] &= ~bit; boxes[bi] &= ~bit
                if cnt >= limit:
                    return

    solve()
    return cnt


def make_puzzle(solved, difficulty, rng):
    """Carve a puzzle from a solved grid while GUARANTEEING a unique solution.
    A cell is only blanked if the puzzle still has exactly one solution afterward,
    so the printed `solved` grid is always THE answer. Difficulty caps how many
    blanks we aim for (easy=40, medium=48, hard=54); uniqueness may stop us short."""
    target_blanks = {"easy": 40, "medium": 48, "hard": 54}.get(difficulty, 48)
    puzzle = [row[:] for row in solved]
    coords = [(r, c) for r in range(9) for c in range(9)]
    rng.shuffle(coords)
    blanks = 0
    for r, c in coords:
        if blanks >= target_blanks:
            break
        if puzzle[r][c] == 0:
            continue
        saved = puzzle[r][c]
        puzzle[r][c] = 0
        # keep the blank only if the solution is still unique; otherwise put it back
        if count_solutions([row[:] for row in puzzle], limit=2) == 1:
            blanks += 1
        else:
            puzzle[r][c] = saved
    return puzzle


# ---------------- PDF rendering ----------------
def draw_sudoku(c, grid, gx, gy_top, cell, number_font, number_size,
                solution_overlay=None):
    """Render a 9x9 Sudoku grid. gy_top is the top y-coordinate.
    solution_overlay (optional): grayed-in numbers showing the answers for cells the puzzle had blank."""
    size = 9 * cell

    # white background
    c.setFillColorRGB(1, 1, 1)
    c.rect(gx, gy_top - size, size, size, stroke=0, fill=1)

    # thin gridlines (every cell)
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.65, 0.65, 0.65)
    for i in range(10):
        c.line(gx + i * cell, gy_top, gx + i * cell, gy_top - size)
        c.line(gx, gy_top - i * cell, gx + size, gy_top - i * cell)

    # heavy 3x3 box lines
    c.setLineWidth(2.4)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    for i in (0, 3, 6, 9):
        c.line(gx + i * cell, gy_top, gx + i * cell, gy_top - size)
        c.line(gx, gy_top - i * cell, gx + size, gy_top - i * cell)

    # numbers
    c.setFont(number_font, number_size)
    for r in range(9):
        for col in range(9):
            v = grid[r][col]
            if v != 0:
                c.setFillColorRGB(0, 0, 0)
                cx = gx + col * cell + cell / 2
                cy = gy_top - r * cell - cell / 2 - number_size * 0.34
                c.drawCentredString(cx, cy, str(v))

    # solution overlay (the values that were originally blank, drawn lighter)
    if solution_overlay is not None:
        c.setFillColorRGB(0.55, 0.45, 0.05)
        c.setFont(number_font, number_size)
        for r in range(9):
            for col in range(9):
                if grid[r][col] == 0 and solution_overlay[r][col] != 0:
                    cx = gx + col * cell + cell / 2
                    cy = gy_top - r * cell - cell / 2 - number_size * 0.34
                    c.drawCentredString(cx, cy, str(solution_overlay[r][col]))


def footer(c, page_no):
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.setFont("Sans", 9)
    c.drawCentredString(PAGE_W / 2, 34, str(page_no))


def front_matter(c, title, subtitle, author):
    c.setFillColorRGB(0.10, 0.10, 0.10)
    c.setFont("SansB", 32)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 280, title.upper())
    c.setFont("Sans", 14)
    for i, line in enumerate(_wrap(subtitle, 40)):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 340 - i * 22, line)
    c.setStrokeColorRGB(0.7, 0.7, 0.7); c.setLineWidth(1)
    c.line(PAGE_W / 2 - 80, PAGE_H - 410, PAGE_W / 2 + 80, PAGE_H - 410)
    c.setFont("Sans", 13)
    c.drawCentredString(PAGE_W / 2, 120, author)
    c.showPage()

    c.setFillColorRGB(0.2, 0.2, 0.2); c.setFont("Sans", 10)
    cr_lines = [
        f"Copyright © 2026 {author}. All rights reserved.",
        "",
        "No part of this publication may be reproduced, distributed, or transmitted",
        "in any form without the prior written permission of the publisher,",
        "except for brief quotations in reviews.",
        "",
        "The puzzles in this book are an original compilation.",
    ]
    for i, ln in enumerate(cr_lines):
        c.drawString(MARGIN, PAGE_H - 120 - i * 16, ln)
    c.showPage()

    c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 140, "HOW TO PLAY SUDOKU")
    c.setFont("Sans", 13)
    how = [
        "Fill the grid so every row, every column,",
        "and every 3 × 3 box contains the digits 1 through 9.",
        "",
        "No row, column, or box may repeat a digit.",
        "",
        "Use logic, never guessing — each puzzle has just one solution.",
        "",
        "Stuck? Full solutions are at the back of the book.",
        "",
        "Take your time. There is no clock. Enjoy the quiet.",
    ]
    for i, ln in enumerate(how):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 200 - i * 24, ln)
    c.showPage()


def puzzle_page(c, idx, difficulty, puzzle, page_no, running):
    c.setFillColorRGB(0.5, 0.5, 0.5); c.setFont("Sans", 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 40, running)
    c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 12)
    c.drawString(MARGIN, PAGE_H - 64, f"PUZZLE {idx}")
    c.setFont("SansB", 11)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 64, f"DIFFICULTY: {difficulty.upper()}")

    cell = 50
    grid_w = 9 * cell
    gx = (PAGE_W - grid_w) / 2
    gy_top = PAGE_H - 130
    draw_sudoku(c, puzzle, gx, gy_top, cell, "MonoB", 28)

    footer(c, page_no)
    c.showPage()


def solutions_section(c, items, page_no_start, running):
    """6 mini-grids per page (2x3 layout) — compact solutions."""
    page_no = page_no_start
    c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 30)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 10, "SOLUTIONS")
    footer(c, page_no); c.showPage(); page_no += 1

    cell = 18  # solutions: smaller cells so 3 rows (6/page) fit within the bottom margin on 8.5x11
    grid_w = 9 * cell
    cols = 2
    col_gap = 40
    row_gap = 40
    total_w = cols * grid_w + (cols - 1) * col_gap
    start_x = (PAGE_W - total_w) / 2

    per_page = 6
    for i in range(0, len(items), per_page):
        c.setFillColorRGB(0.5, 0.5, 0.5); c.setFont("Sans", 10)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 40, running)
        batch = items[i:i + per_page]
        for j, (idx, puzzle, solved) in enumerate(batch):
            row, col = divmod(j, cols)
            gx = start_x + col * (grid_w + col_gap)
            top_y = PAGE_H - 90 - row * (grid_w + row_gap + 30)
            c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 11)
            c.drawCentredString(gx + grid_w / 2, top_y + 10, f"PUZZLE {idx}")
            draw_sudoku(c, solved, gx, top_y, cell, "MonoB", 13)
        footer(c, page_no); c.showPage(); page_no += 1
    return page_no


def back_matter(c, author, also_from):
    """Same back matter pattern as wordsearch.py: review CTA + cross-sell + about."""
    import math as _m
    c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 28)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 200, "DID YOU ENJOY THIS BOOK?")
    c.setFont("Sans", 14)
    lines = [
        "",
        "Reviews are how small publishers like us reach more readers.",
        "If you enjoyed these puzzles, please leave a quick review on Amazon.",
        "",
        "Even one honest sentence makes a real difference.",
        "",
        f"Thank you, from everyone at {author}.",
    ]
    for i, ln in enumerate(lines):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 260 - i * 24, ln)
    c.setStrokeColorRGB(0.5, 0.55, 0.5); c.setLineWidth(1)
    c.line(PAGE_W / 2 - 80, PAGE_H - 470, PAGE_W / 2 + 80, PAGE_H - 470)
    # 5 yellow stars as polygons (font-free)
    c.setFillColorRGB(0.95, 0.78, 0.12); c.setStrokeColorRGB(0.7, 0.55, 0.08); c.setLineWidth(0.6)
    star_y = PAGE_H - 510
    spacing = 32
    R = 11
    start_x = PAGE_W / 2 - spacing * 4 / 2
    for i in range(5):
        cx = start_x + i * spacing
        pts = []
        for k in range(10):
            ang = -_m.pi / 2 + k * _m.pi / 5
            r = R if k % 2 == 0 else R * 0.45
            pts.append((cx + r * _m.cos(ang), star_y + r * _m.sin(ang)))
        p = c.beginPath()
        p.moveTo(*pts[0])
        for pt in pts[1:]:
            p.lineTo(*pt)
        p.close()
        c.drawPath(p, stroke=1, fill=1)
    c.showPage()

    if also_from:
        c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 26)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 180, f"ALSO FROM {author.upper()}")
        c.setStrokeColorRGB(0.5, 0.55, 0.5)
        c.line(PAGE_W / 2 - 80, PAGE_H - 200, PAGE_W / 2 + 80, PAGE_H - 200)
        c.setFont("Sans", 13)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 230,
                            "Search the titles below on Amazon to find them:")
        y = PAGE_H - 290
        for entry in also_from:
            c.setFont("SansB", 14)
            c.drawCentredString(PAGE_W / 2, y, entry.get("title", ""))
            sub = entry.get("subtitle", "")
            if sub:
                c.setFont("Sans", 11); c.setFillColorRGB(0.4, 0.4, 0.4)
                c.drawCentredString(PAGE_W / 2, y - 18, sub)
                c.setFillColorRGB(0.1, 0.1, 0.1)
            y -= 64
        c.showPage()


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines or [text]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="Large Print Sudoku")
    ap.add_argument("--subtitle", default="100 Large Print Sudoku Puzzles for Adults & Seniors with Big Easy-to-Read Numbers and Full Solutions")
    ap.add_argument("--author", default="Evergreen Puzzle Press")
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--also-from", default="")  # path to JSON list
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--profile", default="mixed", choices=["easy", "mixed", "hard"])
    a = ap.parse_args()

    rng = random.Random(a.seed)
    register_fonts()

    # Build the puzzles (difficulty mix depends on profile -> genuinely distinct books)
    ratios = {"easy": (0.70, 0.30, 0.0), "mixed": (0.40, 0.35, 0.25), "hard": (0.0, 0.40, 0.60)}[a.profile]
    ne = int(a.count * ratios[0]); nm = int(a.count * ratios[1])
    difficulties = ["easy"] * ne + ["medium"] * nm + ["hard"] * (a.count - ne - nm)
    rng.shuffle(difficulties)  # mix them through the book

    puzzles = []
    for d in difficulties:
        solved = make_solved(rng)
        puzzle = make_puzzle(solved, d, rng)
        puzzles.append((d, puzzle, solved))

    also_from = []
    if a.also_from and os.path.exists(a.also_from):
        also_from = json.load(open(a.also_from))

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    c = canvas.Canvas(a.out, pagesize=letter)
    c.setTitle(a.title); c.setAuthor(a.author)

    front_matter(c, a.title, a.subtitle, a.author)

    page_no = 1
    items_for_sol = []
    for i, (d, p, s) in enumerate(puzzles, start=1):
        puzzle_page(c, i, d, p, page_no, a.title)
        items_for_sol.append((i, p, s))
        page_no += 1

    page_no = solutions_section(c, items_for_sol, page_no, a.title)

    back_matter(c, a.author, also_from)

    c.save()

    size_kb = os.path.getsize(a.out) / 1024
    print(f"DONE -> {a.out}")
    print(f"  {a.count} Sudoku puzzles ({difficulties.count('easy')} easy / {difficulties.count('medium')} medium / {difficulties.count('hard')} hard) + solutions, {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
