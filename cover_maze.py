#!/usr/bin/env python3
"""Front cover for the maze book -- same layout as cover_sudoku.py, but the
hero is a real generated maze. 2550x3300 at 300 DPI."""
import argparse, os, random
from PIL import Image, ImageDraw, ImageFont
from mazes import gen_maze

W, H = 2550, 3300
PALETTE = {"bg": (238, 244, 236), "accent": (74, 122, 86), "deep": (26, 58, 40),
           "mute": (110, 130, 116), "hi": (245, 188, 74), "cell": (252, 253, 251)}

ARIALB = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
GEORGIA = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"


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


def hero_maze(d, cx, cy, n, cell):
    P = PALETTE
    rng = random.Random(7)
    walls = gen_maze(n, n, rng)
    w = {k: set(v) for k, v in walls.items()}
    w[(0, 0)].discard("N")
    w[(n - 1, n - 1)].discard("S")
    size = n * cell
    x0, y0 = cx - size // 2, cy - size // 2
    d.rectangle([x0, y0, x0 + size, y0 + size], fill=P["cell"])
    lw = max(6, cell // 7)
    for (cc, rr), ws in w.items():
        ax = x0 + cc * cell
        ay = y0 + rr * cell
        if "N" in ws: d.line([(ax, ay), (ax + cell, ay)], fill=P["deep"], width=lw)
        if "S" in ws: d.line([(ax, ay + cell), (ax + cell, ay + cell)], fill=P["deep"], width=lw)
        if "W" in ws: d.line([(ax, ay), (ax, ay + cell)], fill=P["deep"], width=lw)
        if "E" in ws: d.line([(ax + cell, ay), (ax + cell, ay + cell)], fill=P["deep"], width=lw)
    d.rectangle([x0, y0, x0 + size, y0 + size], outline=P["deep"], width=lw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="Large Print Mazes")
    ap.add_argument("--subtitle", default="80 Relaxing Puzzles for Adults & Seniors, with Full Solutions")
    ap.add_argument("--author", default="Evergreen Puzzle Press")
    ap.add_argument("--badge", default="80 LARGE PRINT MAZES")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    P = PALETTE
    img = Image.new("RGB", (W, H), P["bg"])
    d = ImageDraw.Draw(img)
    m = 120
    d.rectangle([m, m, W - m, H - m], outline=P["accent"], width=8)
    d.rectangle([m + 32, m + 32, W - m - 32, H - m - 32], outline=P["accent"], width=3)

    lpf = f(IMPACT, 138); lp = "LARGE PRINT"
    lpw = d.textlength(lp, font=lpf)
    bx0, by0 = (W - lpw) / 2 - 60, 380 - 28
    bx1, by1 = (W + lpw) / 2 + 60, 380 + 138 + 28
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=22, fill=P["deep"])
    d.text(((W - lpw) / 2, 380 - 6), lp, font=lpf, fill=P["hi"])

    title_rest = a.title.upper()
    if title_rest.startswith("LARGE PRINT "):
        title_rest = title_rest[len("LARGE PRINT "):]
    tf = f(GEORGIA, 230)
    y = by1 + 70
    for ln in wrap(d, title_rest, tf, W - 2 * (m + 90)):
        tw = d.textlength(ln, font=tf)
        d.text(((W - tw) / 2, y), ln, font=tf, fill=P["deep"]); y += 250
    y += 6
    d.line([(W // 2 - 240, y), (W // 2 + 240, y)], fill=P["accent"], width=4); y += 56
    sf = f(ARIAL, 62)
    for ln in wrap(d, a.subtitle, sf, W - 2 * (m + 170)):
        tw = d.textlength(ln, font=sf)
        d.text(((W - tw) / 2, y), ln, font=sf, fill=P["mute"]); y += 86

    hero_maze(d, W // 2, 2010, n=11, cell=124)

    grid_bottom = 2010 + (11 * 124) // 2
    if a.badge:
        vf = f(IMPACT, 104); vw = d.textlength(a.badge, font=vf)
        by = grid_bottom + 120; bx = (W - vw) / 2; pad = 64
        d.rounded_rectangle([bx - pad, by - 26, bx + vw + pad, by + 124], radius=30,
                            fill=P["hi"], outline=P["deep"], width=5)
        d.text((bx, by - 8), a.badge, font=vf, fill=P["deep"])
    if a.author:
        af = f(ARIALB, 70); aw = d.textlength(a.author, font=af)
        d.text(((W - aw) / 2, H - 290), a.author, font=af, fill=P["deep"])

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    img.save(a.out, "PNG")
    print(f"DONE -> {a.out}  ({W}x{H})")


if __name__ == "__main__":
    main()
