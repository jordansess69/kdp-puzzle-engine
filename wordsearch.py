#!/usr/bin/env python3
"""Print-ready large-print word-search book for Amazon KDP. Swap the themes
JSON and it's a new book in a new niche -- that's the whole premise: code
generates books at a volume a hand-maker can't match, not a one-off script
for a single title.

Outputs an 8.5x11 interior PDF with front matter, puzzles, and full
solutions. KDP needs a separate cover, either from their free Cover Creator
or generated separately here."""
from __future__ import annotations
import argparse, json, math, os, random, string
from reportlab.pdfgen import canvas
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

PAGE_W, PAGE_H = letter            # 612 x 792 pt  (8.5 x 11 in)
MARGIN = 54                        # 0.75in uniform — safe KDP gutter (<150pg) + roomy large print
GRID_N = 15
DIRS = [(0, 1), (1, 0), (1, 1), (1, -1), (0, -1), (-1, 0), (-1, -1), (-1, 1)]

Cell = tuple[int, int]
Grid = list[list[str]]

FONTS = {
    "Sans":  "/System/Library/Fonts/Supplemental/Arial.ttf",
    "SansB": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "MonoB": "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
}


def register_fonts() -> None:
    for name, path in FONTS.items():
        pdfmetrics.registerFont(TTFont(name, path))


# ---------------- puzzle generation ----------------
def _try_place(grid: Grid, word: str, N: int) -> list[Cell] | None:
    dr, dc = random.choice(DIRS)
    r, c = random.randint(0, N - 1), random.randint(0, N - 1)
    cells: list[Cell] = []
    for k, ch in enumerate(word):
        rr, cc = r + dr * k, c + dc * k
        if not (0 <= rr < N and 0 <= cc < N):
            return None
        cur = grid[rr][cc]
        if cur and cur != ch:
            return None
        cells.append((rr, cc))
    for (rr, cc), ch in zip(cells, word):
        grid[rr][cc] = ch
    return cells


def generate_puzzle(words: list[str], N: int = GRID_N) -> tuple[Grid, list[list[Cell]], list[str]]:
    grid: Grid = [["" for _ in range(N)] for _ in range(N)]
    placements: list[list[Cell]] = []
    placed: list[str] = []
    for w in sorted(words, key=len, reverse=True):
        cells = None
        for _ in range(500):
            cells = _try_place(grid, w, N)
            if cells:
                break
        if cells:
            placements.append(cells)
            placed.append(w)
    for r in range(N):
        for c in range(N):
            if not grid[r][c]:
                grid[r][c] = random.choice(string.ascii_uppercase)
    return grid, placements, placed


# ---------------- drawing helpers ----------------
def draw_grid(c: Canvas, grid: Grid, gx: float, gy_top: float, cell: float,
              font_size: float, highlights: list[list[Cell]] | None = None) -> None:
    N = len(grid)
    h = N * cell
    # faint internal gridlines
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.86, 0.86, 0.86)
    for i in range(N + 1):
        c.line(gx + i * cell, gy_top, gx + i * cell, gy_top - h)
        c.line(gx, gy_top - i * cell, gx + N * cell, gy_top - i * cell)
    # solution highlighters (drawn UNDER the letters)
    if highlights:
        c.setLineCap(1)
        c.setStrokeColorRGB(1.0, 0.78, 0.20)
        c.setStrokeAlpha(0.5)
        c.setLineWidth(cell * 0.72)
        for cells in highlights:
            (r0, c0), (r1, c1) = cells[0], cells[-1]
            x0, y0 = gx + c0 * cell + cell / 2, gy_top - r0 * cell - cell / 2
            x1, y1 = gx + c1 * cell + cell / 2, gy_top - r1 * cell - cell / 2
            c.line(x0, y0, x1, y1)
        c.setStrokeAlpha(1.0)
        c.setLineCap(0)
    # outer border
    c.setStrokeColorRGB(0.25, 0.25, 0.25)
    c.setLineWidth(1.3)
    c.rect(gx, gy_top - h, N * cell, h)
    # letters
    c.setFillColorRGB(0, 0, 0)
    c.setFont("MonoB", font_size)
    for r in range(N):
        for col in range(N):
            cx = gx + col * cell + cell / 2
            cy = gy_top - r * cell - cell / 2 - font_size * 0.34
            c.drawCentredString(cx, cy, grid[r][col])


def draw_word_list(c: Canvas, words: list[str], gx: float, top_y: float,
                    grid_w: float, cols: int = 3) -> None:
    c.setFillColorRGB(0, 0, 0)
    c.setFont("SansB", 12)
    c.drawCentredString(PAGE_W / 2, top_y, "FIND THESE WORDS")
    words = sorted(words)
    rows = math.ceil(len(words) / cols)
    col_w = grid_w / cols
    c.setFont("Sans", 13)
    start_y = top_y - 22
    for i, w in enumerate(words):
        col, row = i // rows, i % rows
        x = gx + col * col_w + 8
        y = start_y - row * 20
        c.drawString(x, y, w)


def footer(c: Canvas, page_no: int) -> None:
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.setFont("Sans", 9)
    c.drawCentredString(PAGE_W / 2, 34, str(page_no))


# ---------------- pages ----------------
def front_matter(c: Canvas, title: str, subtitle: str, author: str) -> None:
    # title page
    c.setFillColorRGB(0.10, 0.10, 0.10)
    c.setFont("SansB", 30)
    for i, line in enumerate(_wrap(title.upper(), 16)):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 250 - i * 38, line)
    c.setFont("Sans", 15)
    for i, line in enumerate(_wrap(subtitle, 40)):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 360 - i * 22, line)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(1)
    c.line(PAGE_W / 2 - 80, PAGE_H - 410, PAGE_W / 2 + 80, PAGE_H - 410)
    c.setFont("Sans", 13)
    c.drawCentredString(PAGE_W / 2, 120, author)
    c.showPage()

    # copyright page
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Sans", 10)
    lines = [
        f"Copyright © 2026 {author}.",
        "All rights reserved.",
        "",
        "No part of this publication may be reproduced, distributed, or",
        "transmitted in any form without the prior written permission of",
        "the publisher, except for brief quotations in reviews.",
        "",
        "The puzzles in this book are an original compilation.",
        "Printed editions produced via Amazon KDP.",
    ]
    for i, ln in enumerate(lines):
        c.drawString(MARGIN, PAGE_H - 120 - i * 16, ln)
    c.showPage()

    # how to play
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("SansB", 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 140, "HOW TO PLAY")
    c.setFont("Sans", 13)
    how = [
        "Each puzzle hides a list of words in a grid of letters.",
        "",
        "Words run in straight lines — across, down, diagonally,",
        "and sometimes backwards.",
        "",
        "Find every word in the list and circle it in the grid.",
        "",
        "Stuck? Full solutions are at the back of the book.",
        "",
        "Take your time. There is no clock. Enjoy the quiet.",
    ]
    for i, ln in enumerate(how):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 200 - i * 22, ln)
    c.showPage()


def puzzle_page(c: Canvas, idx: int, name: str, grid: Grid, words: list[str],
                 page_no: int, running_title: str) -> None:
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.setFont("Sans", 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 40, running_title)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("SansB", 12)
    c.drawString(MARGIN, PAGE_H - 64, f"PUZZLE {idx}")
    c.setFont("SansB", 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 96, name.upper())

    cell = 30
    N = len(grid)
    grid_w = N * cell
    gx = (PAGE_W - grid_w) / 2
    gy_top = PAGE_H - 122          # grid bottom = 670 - 450 = 220
    draw_grid(c, grid, gx, gy_top, cell, 18)

    draw_word_list(c, words, gx, gy_top - N * cell - 26, grid_w, cols=3)
    footer(c, page_no)
    c.showPage()


def solutions_pages(c: Canvas, solutions: list[tuple[int, str, Grid, list[list[Cell]]]],
                     page_no_start: int, running_title: str) -> int:
    page_no = page_no_start
    # section divider
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("SansB", 30)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 10, "SOLUTIONS")
    footer(c, page_no)
    c.showPage()
    page_no += 1

    cell = 17
    N = GRID_N
    grid_w = N * cell
    gx = (PAGE_W - grid_w) / 2
    slots_top = [PAGE_H - 96, PAGE_H - 96 - 320]   # two solutions per page
    for i in range(0, len(solutions), 2):
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.setFont("Sans", 10)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 40, running_title)
        for slot, sol in zip(slots_top, solutions[i:i + 2]):
            idx, name, grid, placements = sol
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("SansB", 13)
            c.drawCentredString(PAGE_W / 2, slot, f"PUZZLE {idx}  —  {name.upper()}")
            draw_grid(c, grid, gx, slot - 16, cell, 10, highlights=placements)
        footer(c, page_no)
        c.showPage()
        page_no += 1
    return page_no


def back_matter(c: Canvas, author: str, also_from: list[dict]) -> None:
    """Back-matter pages — the highest-leverage thing for a new KDP book:
      1. Review request (lifts review count = lifts ranking).
      2. 'Also from [author]' cross-sell (when one book sells, the others get free shelf space).
      3. Short 'About' note.
    """
    # --- review request ---
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("SansB", 28)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 200, "DID YOU ENJOY THIS BOOK?")
    c.setFont("Sans", 14)
    lines = [
        "",
        "Reviews are how small publishers like us reach more readers.",
        "If you enjoyed these puzzles, please leave a quick review on Amazon.",
        "",
        "Even one honest sentence makes a real difference.",
        "",
        "Thank you, from everyone at " + (author or "our small press") + ".",
    ]
    for i, ln in enumerate(lines):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 260 - i * 24, ln)
    # decorative rule
    c.setStrokeColorRGB(0.5, 0.55, 0.5)
    c.setLineWidth(1)
    c.line(PAGE_W / 2 - 80, PAGE_H - 470, PAGE_W / 2 + 80, PAGE_H - 470)
    # five star icons drawn as polygons (no font glyph dependency)
    c.setFillColorRGB(0.95, 0.78, 0.12)
    c.setStrokeColorRGB(0.7, 0.55, 0.08)
    c.setLineWidth(0.6)
    import math as _m
    star_y = PAGE_H - 510
    spacing = 32
    total_w = spacing * 4
    start_x = PAGE_W / 2 - total_w / 2
    R = 11
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

    # --- also from <author> (series cross-sell) ---
    if also_from:
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("SansB", 26)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 180, "ALSO FROM " + (author or "OUR PRESS").upper())
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
                c.setFont("Sans", 11)
                c.setFillColorRGB(0.4, 0.4, 0.4)
                c.drawCentredString(PAGE_W / 2, y - 18, sub)
                c.setFillColorRGB(0.1, 0.1, 0.1)
            y -= 64
        c.showPage()

    # --- about the press ---
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("SansB", 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 180, "ABOUT " + (author or "OUR PRESS").upper())
    c.setFont("Sans", 13)
    about_lines = [
        "",
        f"{author} publishes calm, beautifully made puzzle books in",
        "large print, made to be easy on the eyes and a pleasure to solve.",
        "",
        "We believe a puzzle book should slow time down, not race it.",
        "We make every book by hand and care a great deal about quality.",
        "",
        "Thank you for spending your time with one of our books.",
    ]
    for i, ln in enumerate(about_lines):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 240 - i * 22, ln)
    c.showPage()


# ---------------- utils ----------------
def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]


def clean_words(words: list[str]) -> list[str]:
    out: list[str] = []
    for w in words:
        w = "".join(ch for ch in w.upper() if ch.isalpha())
        if w and len(w) <= GRID_N:
            out.append(w)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--themes", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--author")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    random.seed(a.seed)
    data = json.load(open(a.themes))
    title = a.title or data.get("title", "Word Search")
    subtitle = a.subtitle or data.get("subtitle", "")
    author = a.author or data.get("author", "")
    running = title

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    register_fonts()
    c = canvas.Canvas(a.out, pagesize=letter)
    c.setTitle(title)
    c.setAuthor(author)

    front_matter(c, title, subtitle, author)

    solutions = []
    page_no = 1
    for i, p in enumerate(data["puzzles"], start=1):
        words = clean_words(p["words"])
        grid, placements, placed = generate_puzzle(words)
        puzzle_page(c, i, p["name"], grid, placed, page_no, running)
        solutions.append((i, p["name"], grid, placements))
        if len(placed) < len(words):
            print(f"  note: puzzle {i} '{p['name']}' placed {len(placed)}/{len(words)} words")
        page_no += 1

    solutions_pages(c, solutions, page_no, running)

    # Back-matter: review request + cross-sell + about
    also_from = data.get("also_from", [])
    back_matter(c, author, also_from)

    c.save()

    n_puzzles = len(data["puzzles"])
    size_kb = os.path.getsize(a.out) / 1024
    print(f"DONE -> {a.out}")
    print(f"  {n_puzzles} puzzles + solutions, {size_kb:.0f} KB, 8.5x11 print-ready")


if __name__ == "__main__":
    main()
