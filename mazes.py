#!/usr/bin/env python3
"""
mazes.py — code-generated, print-ready LARGE PRINT Maze book for KDP.

Perfect mazes via recursive-backtracker (every maze has exactly one solution path).
Each maze on its own page in large print; full solutions at the back.

USAGE (run with /usr/bin/python3 for reportlab):
    /usr/bin/python3 mazes.py --out out/mazes_v1.pdf --title "Large Print Mazes" \
        --author "Evergreen Puzzle Press" --count 80
"""
import argparse, json, os, random
from collections import deque
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

PAGE_W, PAGE_H = letter
MARGIN = 54
FONTS = {
    "Sans":  "/System/Library/Fonts/Supplemental/Arial.ttf",
    "SansB": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
}
OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}
DC = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}  # r grows downward


def register_fonts():
    for name, path in FONTS.items():
        pdfmetrics.registerFont(TTFont(name, path))


def gen_maze(cols, rows, rng):
    """Recursive-backtracker perfect maze. Returns walls[(c,r)] = set of present walls."""
    walls = {(c, r): {"N", "E", "S", "W"} for c in range(cols) for r in range(rows)}
    visited = set()
    stack = [(0, 0)]
    visited.add((0, 0))
    while stack:
        c, r = stack[-1]
        nbrs = []
        for d, (dc, dr) in DC.items():
            nc, nr = c + dc, r + dr
            if 0 <= nc < cols and 0 <= nr < rows and (nc, nr) not in visited:
                nbrs.append((d, nc, nr))
        if nbrs:
            d, nc, nr = rng.choice(nbrs)
            walls[(c, r)].discard(d)
            walls[(nc, nr)].discard(OPP[d])
            visited.add((nc, nr))
            stack.append((nc, nr))
        else:
            stack.pop()
    return walls


def solve(walls, cols, rows):
    """BFS the unique path from (0,0) to (cols-1,rows-1)."""
    start, end = (0, 0), (cols - 1, rows - 1)
    prev = {start: None}
    q = deque([start])
    while q:
        c, r = q.popleft()
        if (c, r) == end:
            break
        for d, (dc, dr) in DC.items():
            if d in walls[(c, r)]:
                continue
            nc, nr = c + dc, r + dr
            if 0 <= nc < cols and 0 <= nr < rows and (nc, nr) not in prev:
                prev[(nc, nr)] = (c, r)
                q.append((nc, nr))
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    return path[::-1]


def draw_maze(c, walls, cols, rows, gx, gy_top, cell, line_w, path=None):
    # entrance (top-left, open North) + exit (bottom-right, open South)
    w = {k: set(v) for k, v in walls.items()}
    w[(0, 0)].discard("N")
    w[(cols - 1, rows - 1)].discard("S")

    c.setLineWidth(line_w)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    c.setLineCap(1)
    for (cc, rr), ws in w.items():
        x0 = gx + cc * cell
        yt = gy_top - rr * cell
        if "N" in ws: c.line(x0, yt, x0 + cell, yt)
        if "S" in ws: c.line(x0, yt - cell, x0 + cell, yt - cell)
        if "W" in ws: c.line(x0, yt, x0, yt - cell)
        if "E" in ws: c.line(x0 + cell, yt, x0 + cell, yt - cell)

    if path:
        c.setStrokeColorRGB(0.85, 0.45, 0.1)
        c.setLineWidth(max(1.5, cell * 0.16))
        c.setLineCap(1)
        pts = [(gx + cc * cell + cell / 2, gy_top - rr * cell - cell / 2) for (cc, rr) in path]
        for i in range(len(pts) - 1):
            c.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])


def footer(c, n):
    c.setFillColorRGB(0.45, 0.45, 0.45); c.setFont("Sans", 9)
    c.drawCentredString(PAGE_W / 2, 34, str(n))


def front_matter(c, title, subtitle, author):
    c.setFillColorRGB(0.10, 0.10, 0.10); c.setFont("SansB", 32)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 280, title.upper())
    c.setFont("Sans", 14)
    for i, line in enumerate(_wrap(subtitle, 40)):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 340 - i * 22, line)
    c.setStrokeColorRGB(0.7, 0.7, 0.7); c.setLineWidth(1)
    c.line(PAGE_W / 2 - 80, PAGE_H - 410, PAGE_W / 2 + 80, PAGE_H - 410)
    c.setFont("Sans", 13); c.drawCentredString(PAGE_W / 2, 120, author)
    c.showPage()

    c.setFillColorRGB(0.2, 0.2, 0.2); c.setFont("Sans", 10)
    for i, ln in enumerate([
            f"Copyright © 2026 {author}. All rights reserved.", "",
            "No part of this publication may be reproduced, distributed, or transmitted",
            "in any form without the prior written permission of the publisher,",
            "except for brief quotations in reviews.", "",
            "The puzzles in this book are an original compilation."]):
        c.drawString(MARGIN, PAGE_H - 120 - i * 16, ln)
    c.showPage()

    c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 140, "HOW TO SOLVE")
    c.setFont("Sans", 13)
    for i, ln in enumerate([
            "Start at the opening at the TOP-LEFT of each maze.",
            "Find a continuous path to the opening at the BOTTOM-RIGHT.",
            "", "You may not cross any walls.",
            "There is exactly one path through — take your time.",
            "", "Stuck? Full solutions are at the back of the book."]):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 200 - i * 26, ln)
    c.showPage()


def maze_page(c, idx, walls, cols, rows, page_no, running, difficulty):
    c.setFillColorRGB(0.5, 0.5, 0.5); c.setFont("Sans", 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 40, running)
    c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 12)
    c.drawString(MARGIN, PAGE_H - 64, f"MAZE {idx}")
    c.setFont("SansB", 11); c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 64, f"DIFFICULTY: {difficulty.upper()}")

    avail = min(PAGE_W - 2 * MARGIN, PAGE_H - 200)
    cell = avail / max(cols, rows)
    grid_w = cell * cols
    grid_h = cell * rows
    gx = (PAGE_W - grid_w) / 2
    gy_top = PAGE_H - 110
    draw_maze(c, walls, cols, rows, gx, gy_top, cell, line_w=2.4)
    footer(c, page_no); c.showPage()


def solutions_section(c, items, page_no, running):
    c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 30)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 10, "SOLUTIONS")
    footer(c, page_no); c.showPage(); page_no += 1

    cols_n, rows_n = 2, 3
    per_page = cols_n * rows_n
    gap_y = 30
    top = PAGE_H - 90            # below the running header
    bottom = MARGIN + 30         # leave room for the page-number footer
    box_w = (PAGE_W - 2 * MARGIN) / cols_n
    box_h = (top - bottom - (rows_n - 1) * gap_y) / rows_n
    box = min(box_w, box_h)      # square cell-box that fits both axes
    for i in range(0, len(items), per_page):
        c.setFillColorRGB(0.5, 0.5, 0.5); c.setFont("Sans", 10)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 40, running)
        batch = items[i:i + per_page]
        for j, (idx, walls, cols, rows, path) in enumerate(batch):
            row, col = divmod(j, cols_n)
            cell = (box - 18) / max(cols, rows)
            gw = cell * cols
            gx = MARGIN + col * box_w + (box_w - gw) / 2
            gy_top = top - row * (box_h + gap_y)
            c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 10)
            c.drawCentredString(gx + gw / 2, gy_top + 12, f"MAZE {idx}")
            draw_maze(c, walls, cols, rows, gx, gy_top, cell, line_w=1.0, path=path)
        footer(c, page_no); c.showPage(); page_no += 1
    return page_no


def back_matter(c, author, also_from):
    import math as _m
    c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 28)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 200, "DID YOU ENJOY THIS BOOK?")
    c.setFont("Sans", 14)
    for i, ln in enumerate(["", "Reviews help small publishers like us reach more readers.",
                            "If you enjoyed these mazes, please leave a quick review on Amazon.",
                            "", "Even one honest sentence makes a real difference.",
                            "", f"Thank you, from everyone at {author}."]):
        c.drawCentredString(PAGE_W / 2, PAGE_H - 260 - i * 24, ln)
    c.setFillColorRGB(0.95, 0.78, 0.12); c.setStrokeColorRGB(0.7, 0.55, 0.08); c.setLineWidth(0.6)
    sy = PAGE_H - 470; sp = 32; R = 11; sx = PAGE_W / 2 - sp * 4 / 2
    for i in range(5):
        cx = sx + i * sp; pts = []
        for k in range(10):
            ang = -_m.pi / 2 + k * _m.pi / 5
            r = R if k % 2 == 0 else R * 0.45
            pts.append((cx + r * _m.cos(ang), sy + r * _m.sin(ang)))
        p = c.beginPath(); p.moveTo(*pts[0])
        for pt in pts[1:]: p.lineTo(*pt)
        p.close(); c.drawPath(p, stroke=1, fill=1)
    c.showPage()
    if also_from:
        c.setFillColorRGB(0.1, 0.1, 0.1); c.setFont("SansB", 26)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 180, f"ALSO FROM {author.upper()}")
        c.setFont("Sans", 13)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 230, "Search the titles below on Amazon to find them:")
        y = PAGE_H - 290
        for e in also_from:
            c.setFont("SansB", 14); c.drawCentredString(PAGE_W / 2, y, e.get("title", ""))
            y -= 50
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
    ap.add_argument("--title", default="Large Print Mazes")
    ap.add_argument("--subtitle", default="80 Relaxing Large Print Maze Puzzles for Adults & Seniors with Full Solutions")
    ap.add_argument("--author", default="Evergreen Puzzle Press")
    ap.add_argument("--count", type=int, default=80)
    ap.add_argument("--also-from", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--profile", default="mixed", choices=["easy", "mixed", "hard"])
    a = ap.parse_args()

    rng = random.Random(a.seed)
    register_fonts()
    sizes = {"easy": 11, "medium": 15, "hard": 19}
    ratios = {"easy": (0.70, 0.30, 0.0), "mixed": (0.40, 0.35, 0.25), "hard": (0.0, 0.40, 0.60)}[a.profile]
    ne = int(a.count * ratios[0]); nm = int(a.count * ratios[1])
    diffs = ["easy"] * ne + ["medium"] * nm + ["hard"] * (a.count - ne - nm)
    rng.shuffle(diffs)

    items = []
    for i, d in enumerate(diffs, start=1):
        n = sizes[d]
        walls = gen_maze(n, n, rng)
        path = solve(walls, n, n)
        items.append((i, d, n, walls, path))

    also = json.load(open(a.also_from)) if a.also_from and os.path.exists(a.also_from) else []
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    c = canvas.Canvas(a.out, pagesize=letter)
    c.setTitle(a.title); c.setAuthor(a.author)
    front_matter(c, a.title, a.subtitle, a.author)
    page_no = 1
    sol_items = []
    for (idx, d, n, walls, path) in items:
        maze_page(c, idx, walls, n, n, page_no, a.title, d)
        sol_items.append((idx, walls, n, n, path)); page_no += 1
    page_no = solutions_section(c, sol_items, page_no, a.title)
    back_matter(c, a.author, also)
    c.save()
    print(f"DONE -> {a.out}")
    print(f"  {a.count} mazes ({diffs.count('easy')} easy / {diffs.count('medium')} medium / {diffs.count('hard')} hard) + solutions")


if __name__ == "__main__":
    main()
