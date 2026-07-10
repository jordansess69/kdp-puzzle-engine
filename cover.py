#!/usr/bin/env python3
"""Print-ready front cover for the large-print word-search books.

The hero is a real solved grid with the theme words highlighted, so the
cover shows what's actually inside rather than generic clip art. Theme
silhouettes per niche."""
import argparse, os, random
from PIL import Image, ImageDraw, ImageFont

W, H = 2550, 3300

PALETTES = {
    "nature":    {"bg": (244, 239, 226), "accent": (107, 142, 107), "deep": (32, 58, 38),  "mute": (120, 134, 116), "hi": (255, 211, 84)},
    "food":      {"bg": (250, 243, 229), "accent": (193, 84, 58),   "deep": (84, 28, 22),  "mute": (150, 108, 92),  "hi": (255, 200, 80)},
    "animals":   {"bg": (240, 238, 230), "accent": (58, 128, 124),  "deep": (18, 56, 54),  "mute": (108, 128, 124), "hi": (255, 211, 84)},
    "bible":     {"bg": (250, 244, 230), "accent": (176, 141, 60),  "deep": (96, 42, 48),  "mute": (130, 104, 76),  "hi": (255, 211, 84)},
    "usa":       {"bg": (245, 243, 236), "accent": (38, 58, 98),    "deep": (150, 44, 52), "mute": (92, 102, 120),  "hi": (255, 211, 84)},
    "kids":      {"bg": (255, 251, 243), "accent": (240, 112, 92),  "deep": (40, 62, 92),  "mute": (90, 120, 140),  "hi": (255, 211, 84)},
    "nostalgia": {"bg": (238, 228, 208), "accent": (150, 112, 70),  "deep": (72, 52, 36),  "mute": (140, 118, 94),  "hi": (255, 211, 84)},
    "beach-vacation": {"bg": (250, 243, 228), "accent": (40, 138, 158), "deep": (16, 54, 78), "mute": (104, 128, 142), "hi": (255, 205, 70)},
    "summer-vacation": {"bg": (252, 246, 230), "accent": (242, 158, 58), "deep": (40, 78, 120), "mute": (120, 120, 108), "hi": (255, 208, 70)},
    "birds":     {"bg": (243, 244, 236), "accent": (86, 140, 170), "deep": (30, 54, 74), "mute": (110, 124, 132), "hi": (255, 205, 80)},
    "gardening": {"bg": (244, 242, 228), "accent": (120, 150, 90), "deep": (44, 66, 40), "mute": (120, 130, 108), "hi": (255, 205, 80)},
    "sports":    {"bg": (245, 244, 238), "accent": (44, 92, 162), "deep": (20, 40, 74), "mute": (98, 110, 132), "hi": (255, 196, 60)},
    "ocean-life": {"bg": (236, 244, 247), "accent": (30, 112, 144), "deep": (12, 44, 68), "mute": (94, 120, 134), "hi": (255, 205, 80)},
    "retro-travel-and-landmarks": {"bg": (240, 230, 210), "accent": (176, 116, 62), "deep": (74, 52, 34), "mute": (140, 116, 90), "hi": (255, 200, 74)},
}

ARIALB = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
GEORGIA = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"
MONO = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"


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
    if cur: lines.append(cur)
    return lines


# ---------- theme silhouettes (drawn in accent color) ----------
def pine_tree(d, cx, cy, scale, color):
    """Stacked triangles + trunk."""
    h = int(220 * scale); w = int(130 * scale)
    for i, frac in enumerate([0.55, 0.78, 1.0]):
        tw = int(w * frac); tier_h = int(h * 0.42)
        ty = cy - int(h * (0.9 - i * 0.3))
        d.polygon([(cx - tw // 2, ty + tier_h), (cx + tw // 2, ty + tier_h), (cx, ty)], fill=color)
    tw = max(10, int(20 * scale)); th = int(35 * scale)
    d.rectangle([cx - tw // 2, cy + 6, cx + tw // 2, cy + th], fill=color)


def leaf(d, cx, cy, scale, color):
    """Real leaf shape: pointed ellipse with a stem and center vein."""
    w = int(120 * scale); h = int(54 * scale)
    layer = Image.new("RGBA", (w * 2 + 40, h * 2 + 40), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    # Build a leaf via two arcs meeting at points (vesica piscis):
    # draw two filled ellipses whose intersection forms the leaf, masked together
    # Simpler approach: polygon with many curve points
    pts = []
    n = 24
    import math
    for i in range(n + 1):           # upper arc, left point -> right point
        t = i / n
        x = -w + (2 * w) * t
        y = -h * (1 - (2 * t - 1) ** 2) ** 0.5
        pts.append((x + w + 20, y + h + 20))
    for i in range(n + 1):           # lower arc, right point -> left point
        t = i / n
        x = w - (2 * w) * t
        y = h * (1 - (2 * t - 1) ** 2) ** 0.5 * 0.55  # less rounded bottom = leaf-y
        pts.append((x + w + 20, y + h + 20))
    ld.polygon(pts, fill=color + (255,))
    # center vein
    ld.line([(20, h + 20), (2 * w + 20, h + 20)], fill=(255, 255, 255, 120), width=max(2, int(3 * scale)))
    # stem
    sx0, sy0 = 2 * w + 20, h + 20
    sx1, sy1 = sx0 + int(34 * scale), sy0 + int(14 * scale)
    layer_with_stem = layer
    rotated = layer_with_stem.rotate(-28, resample=Image.BICUBIC, expand=True)
    d._image.paste(rotated, (cx - rotated.width // 2, cy - rotated.height // 2), rotated)
    # short stem in main image (so rotation doesn't bend it weirdly)
    d.line([(cx + int(w * 0.7 * scale), cy + int(h * 0.5 * scale)),
            (cx + int(w * 1.1 * scale), cy + int(h * 0.85 * scale))],
           fill=color, width=max(3, int(6 * scale)))


def fork(d, cx, cy, scale, color):
    """Simple fork silhouette."""
    w = max(4, int(8 * scale)); h = int(180 * scale)
    # handle
    d.rectangle([cx - w, cy, cx + w, cy + int(h * 0.6)], fill=color)
    # tines
    tw, th = max(3, int(5 * scale)), int(h * 0.5)
    for ox in (-w * 3, -w, w, w * 3):
        d.rectangle([cx + ox - tw // 2, cy - th, cx + ox + tw // 2, cy], fill=color)
    d.rectangle([cx - w * 4, cy, cx + w * 4, cy + int(h * 0.08)], fill=color)


def spoon(d, cx, cy, scale, color):
    """Simple spoon silhouette."""
    w = max(4, int(8 * scale)); h = int(180 * scale)
    d.rectangle([cx - w, cy, cx + w, cy + int(h * 0.6)], fill=color)
    bw, bh = int(38 * scale), int(50 * scale)
    d.ellipse([cx - bw, cy - bh, cx + bw, cy + int(bh * 0.2)], fill=color)


def paw(d, cx, cy, scale, color):
    """Paw print: 4 toes + pad."""
    s = scale
    # pad
    d.ellipse([cx - int(45 * s), cy - int(10 * s), cx + int(45 * s), cy + int(60 * s)], fill=color)
    # 4 toes
    for ox, oy, rx, ry in [(-50, -45, 18, 22), (-20, -65, 18, 22), (20, -65, 18, 22), (50, -45, 18, 22)]:
        d.ellipse([cx + int(ox * s) - int(rx * s), cy + int(oy * s) - int(ry * s),
                   cx + int(ox * s) + int(rx * s), cy + int(oy * s) + int(ry * s)], fill=color)


def star(d, cx, cy, scale, color):
    """5-point star silhouette."""
    import math as _m
    R = int(70 * scale)
    pts = []
    for k in range(10):
        ang = -_m.pi / 2 + k * _m.pi / 5
        r = R if k % 2 == 0 else R * 0.45
        pts.append((cx + r * _m.cos(ang), cy + r * _m.sin(ang)))
    d.polygon(pts, fill=color)


def holly(d, cx, cy, scale, color):
    """Holly leaf cluster with two berries — Christmas decoration."""
    # two leaves crossed
    for ang_deg in (-25, 25):
        layer = Image.new("RGBA", (int(200 * scale), int(120 * scale)), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        w = int(80 * scale); h = int(36 * scale)
        # use a simple ellipse approximation
        ld.ellipse([int(10 * scale), (layer.height - 2 * h) // 2,
                    int(10 * scale) + 2 * w, (layer.height + 2 * h) // 2], fill=color + (255,))
        rotated = layer.rotate(ang_deg, resample=Image.BICUBIC, expand=True)
        d._image.paste(rotated, (cx - rotated.width // 2, cy - rotated.height // 2), rotated)
    # red berries
    br = int(14 * scale)
    d.ellipse([cx - br - 4, cy - br, cx + br - 4, cy + br], fill=(180, 30, 30))
    d.ellipse([cx - br + 22, cy - br + 6, cx + br + 22, cy + br + 6], fill=(180, 30, 30))


def sun(d, cx, cy, scale, color):
    """Sun: center disc with straight rays — beach/summer motif."""
    import math as _m
    R = int(40 * scale)
    inner = R + int(10 * scale)
    outer = R + int(46 * scale)
    for k in range(12):
        ang = k * _m.pi / 6
        x0, y0 = cx + inner * _m.cos(ang), cy + inner * _m.sin(ang)
        x1, y1 = cx + outer * _m.cos(ang), cy + outer * _m.sin(ang)
        d.line([(x0, y0), (x1, y1)], fill=color, width=max(3, int(7 * scale)))
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=color)


def palmtree(d, cx, cy, scale, color):
    """Palm tree: leaning trunk + radiating fronds — tropical/beach motif."""
    import math as _m
    th = int(150 * scale)
    tw = max(5, int(13 * scale))
    top_x, top_y = cx - int(20 * scale), cy - th
    d.line([(cx, cy), (top_x, top_y)], fill=color, width=tw)        # trunk (leaning)
    for ang_deg in (-165, -125, -90, -55, -15):                    # fronds fan upward
        ang = _m.radians(ang_deg)
        fx = top_x + int(108 * scale * _m.cos(ang))
        fy = top_y + int(108 * scale * _m.sin(ang))
        d.line([(top_x, top_y), (fx, fy)], fill=color, width=max(3, int(9 * scale)))


def wave(d, cx, cy, scale, color):
    """Three stacked rolling waves — ocean motif."""
    import math as _m
    span = int(150 * scale)
    amp = int(16 * scale)
    for row in range(3):
        oy = cy + row * int(30 * scale)
        pts = []
        for i in range(0, span + 1, 6):
            x = cx - span // 2 + i
            y = oy + amp * _m.sin(i / span * 2 * _m.pi * 2)
            pts.append((x, y))
        d.line(pts, fill=color, width=max(3, int(8 * scale)), joint="curve")


THEME_DECOR = {
    "nature":    [(pine_tree, 0.10, 0.16, 1.1), (leaf, 0.86, 0.14, 1.0),
                  (pine_tree, 0.91, 0.92, 0.95), (leaf, 0.09, 0.92, 0.95)],
    "food":      [(fork, 0.10, 0.13, 1.0), (spoon, 0.90, 0.13, 1.0),
                  (fork, 0.10, 0.88, 0.9), (spoon, 0.90, 0.88, 0.9)],
    "animals":   [(paw, 0.12, 0.16, 1.1), (paw, 0.88, 0.16, 1.1),
                  (paw, 0.12, 0.93, 1.0), (paw, 0.88, 0.93, 1.0)],
    "bible":     [(leaf, 0.10, 0.14, 1.0), (leaf, 0.90, 0.14, 1.0),
                  (leaf, 0.10, 0.92, 0.9), (leaf, 0.90, 0.92, 0.9)],
    "usa":       [(star, 0.10, 0.14, 1.0), (star, 0.90, 0.14, 1.0),
                  (star, 0.10, 0.93, 0.9), (star, 0.90, 0.93, 0.9)],
    "kids":      [(star, 0.10, 0.14, 1.1), (star, 0.90, 0.14, 1.1),
                  (star, 0.10, 0.93, 1.0), (star, 0.90, 0.93, 1.0)],
    "christmas": [(pine_tree, 0.10, 0.16, 1.0), (holly, 0.88, 0.14, 0.95),
                  (holly, 0.10, 0.93, 0.95), (pine_tree, 0.91, 0.92, 0.9)],
    "nostalgia": [],
    "beach-vacation": [(sun, 0.12, 0.15, 1.05), (palmtree, 0.88, 0.17, 1.0),
                       (wave, 0.12, 0.90, 1.0), (palmtree, 0.90, 0.90, 0.95)],
    "summer-vacation": [(sun, 0.12, 0.15, 1.15), (palmtree, 0.88, 0.16, 1.0),
                        (wave, 0.10, 0.90, 1.0), (sun, 0.90, 0.90, 0.8)],
    "birds":     [(leaf, 0.10, 0.15, 1.0), (sun, 0.88, 0.16, 0.9),
                  (leaf, 0.10, 0.90, 0.95), (leaf, 0.90, 0.90, 0.95)],
    "gardening": [(pine_tree, 0.10, 0.15, 1.0), (leaf, 0.88, 0.16, 1.0),
                  (leaf, 0.10, 0.90, 0.95), (pine_tree, 0.90, 0.90, 0.9)],
    "sports":    [(star, 0.10, 0.14, 1.1), (star, 0.90, 0.14, 1.1),
                  (star, 0.10, 0.93, 1.0), (star, 0.90, 0.93, 1.0)],
    "ocean-life": [(wave, 0.12, 0.14, 1.0), (wave, 0.88, 0.14, 1.0),
                   (wave, 0.12, 0.90, 1.0), (wave, 0.88, 0.90, 1.0)],
    "retro-travel-and-landmarks": [(sun, 0.12, 0.15, 1.05), (palmtree, 0.88, 0.17, 1.0),
                                   (star, 0.10, 0.92, 0.9), (palmtree, 0.90, 0.90, 0.95)],
}


# ---------- hero puzzle grid (the centerpiece — looks like a real solved word search) ----------
THEME_WORDS = {
    "nature":    ["NATURE", "TREE", "BIRD", "LEAF"],
    "food":      ["TASTY", "BAKE", "MINT", "PIE"],
    "animals":   ["ANIMAL", "CAT", "PAW", "WILD"],
    "bible":     ["FAITH", "HOPE", "LOVE", "PRAY"],
    "usa":       ["USA", "FREE", "FLAG", "WEST"],
    "kids":      ["FUN", "PLAY", "KIDS", "STAR"],
    "christmas": ["JOY", "NOEL", "SANTA", "STAR"],
    "nostalgia": ["RETRO", "DINER", "DISCO", "RADIO"],
    "beach-vacation": ["BEACH", "OCEAN", "WAVES", "SANDY"],
    "summer-vacation": ["SUMMER", "SUNNY", "TRAVEL", "RELAX"],
    "birds":     ["ROBIN", "FINCH", "CANARY", "FLOCK"],
    "gardening": ["GARDEN", "SEEDS", "FLOWER", "TROWEL"],
    "sports":    ["SOCCER", "TENNIS", "MEDAL", "HOCKEY"],
    "ocean-life": ["WHALE", "DOLPHIN", "SHARK", "CORAL"],
    "retro-travel-and-landmarks": ["TRAVEL", "VOYAGE", "RETRO", "CRUISE"],
}
# 4 fallback words so a theme not in THEME_WORDS never crashes the hero grid.
DEFAULT_HERO_WORDS = ["WORD", "SEARCH", "PUZZLE", "SOLVE"]


def hero_grid(d, cx, cy, cell, theme, accent, deep, hi):
    """A solved-looking word search: 9x9 grid, some words highlighted with yellow sweeps."""
    n = 9
    size = n * cell
    x0, y0 = cx - size // 2, cy - size // 2

    rng = random.Random(42)
    grid = [[rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(n)] for _ in range(n)]

    # placements: (word, (r,c), (dr,dc)). Pad to 4 words so an unregistered
    # theme falls back gracefully instead of an IndexError.
    words = list(THEME_WORDS.get(theme, [])) or list(DEFAULT_HERO_WORDS)
    while len(words) < 4:
        words.append(DEFAULT_HERO_WORDS[len(words)])
    # Four pairwise-DISJOINT placements (top row / right col / center diagonal /
    # left col) so no two highlighted words share a cell — otherwise the later
    # word overwrites the crossing letter and the sweep reads as a garbled word.
    plans = [
        (words[0], (1, 1), (0, 1)),     # horizontal, top      (row 1, cols 1+)
        (words[1], (2, 7), (1, 0)),     # vertical, right edge (col 7, rows 2+)
        (words[2], (3, 1), (1, 1)),     # diagonal, center     ((3,1) down-right)
        (words[3], (2, 0), (1, 0)),     # vertical, left edge  (col 0, rows 2+)
    ]
    highlights = []
    for word, (r0, c0), (dr, dc) in plans:
        cells = []
        valid = True
        for i, ch in enumerate(word):
            r, c = r0 + dr * i, c0 + dc * i
            if not (0 <= r < n and 0 <= c < n):
                valid = False; break
            cells.append((r, c, ch))
        if valid:
            for r, c, ch in cells:
                grid[r][c] = ch
            highlights.append([(r, c) for r, c, _ in cells])

    # 1) Yellow highlight sweeps UNDER letters
    for cells in highlights:
        (r0, c0), (r1, c1) = cells[0], cells[-1]
        p0 = (x0 + c0 * cell + cell // 2, y0 + r0 * cell + cell // 2)
        p1 = (x0 + c1 * cell + cell // 2, y0 + r1 * cell + cell // 2)
        d.line([p0, p1], fill=hi, width=int(cell * 0.78))

    # 2) Grid lines
    for i in range(n + 1):
        d.line([(x0 + i * cell, y0), (x0 + i * cell, y0 + size)], fill=accent, width=2)
        d.line([(x0, y0 + i * cell), (x0 + size, y0 + i * cell)], fill=accent, width=2)

    # 3) Heavy outer border
    d.rectangle([x0, y0, x0 + size, y0 + size], outline=deep, width=6)

    # 4) Letters
    lf = ImageFont.truetype(MONO, int(cell * 0.56))
    for r in range(n):
        for c in range(n):
            ch = grid[r][c]
            tw = d.textlength(ch, font=lf)
            d.text((x0 + c * cell + (cell - tw) / 2, y0 + r * cell + cell * 0.17),
                   ch, font=lf, fill=deep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--badge", default="")
    ap.add_argument("--palette", default="nature")
    ap.add_argument("--theme", default=None, help="silhouette theme; defaults to --palette")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    random.seed(11)
    theme = a.theme or a.palette
    P = PALETTES.get(a.palette, PALETTES["nature"])
    bg, accent, deep, mute, hi = P["bg"], P["accent"], P["deep"], P["mute"], P["hi"]

    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)

    # double frame
    m = 120
    d.rectangle([m, m, W - m, H - m], outline=accent, width=8)
    d.rectangle([m + 32, m + 32, W - m - 32, H - m - 32], outline=accent, width=3)

    # theme silhouettes (4 corners-ish)
    for fn, fx, fy, scale in THEME_DECOR.get(theme, []):
        fn(d, int(W * fx), int(H * fy), scale, accent)

    # ---- TITLE block ----
    # "LARGE PRINT" stand-alone bar (high contrast attention grab at thumbnail size)
    lpf = f(IMPACT, 138)
    lp = "LARGE PRINT"
    lpw = d.textlength(lp, font=lpf)
    bar_pad_x, bar_pad_y = 60, 28
    bx0, by0 = (W - lpw) / 2 - bar_pad_x, 380 - bar_pad_y
    bx1, by1 = (W + lpw) / 2 + bar_pad_x, 380 + 138 + bar_pad_y
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=22, fill=deep)
    d.text(((W - lpw) / 2, 380 - 6), lp, font=lpf, fill=hi)

    # niche line ("NATURE WORD SEARCH" / "FOOD & KITCHEN WORD SEARCH" / etc.)
    # extract everything AFTER "LARGE PRINT " from the title
    title_rest = a.title.upper()
    if title_rest.startswith("LARGE PRINT "):
        title_rest = title_rest[len("LARGE PRINT "):]
    # Auto-fit the niche title to at most 2 lines so a long title (e.g.
    # "RETRO TRAVEL AND LANDMARKS WORD SEARCH") can't wrap to 3 lines and push
    # the subtitle down into the hero grid — that overlap is a defective cover.
    maxw = W - 2 * (m + 90)
    tsize = 96
    for cand in (174, 156, 138, 122, 108, 96):
        if len(wrap(d, title_rest, f(GEORGIA, cand), maxw)) <= 2:
            tsize = cand
            break
    tf = f(GEORGIA, tsize)
    lh = int(tsize * 1.13)
    y = by1 + 60
    for ln in wrap(d, title_rest, tf, maxw):
        tw = d.textlength(ln, font=tf)
        d.text(((W - tw) / 2, y), ln, font=tf, fill=deep)
        y += lh

    # divider
    y += 14
    d.line([(W // 2 - 240, y), (W // 2 + 240, y)], fill=accent, width=4)
    y += 56

    # subtitle
    sf = f(ARIAL, 60)
    for ln in wrap(d, a.subtitle, sf, W - 2 * (m + 200)):
        tw = d.textlength(ln, font=sf)
        d.text(((W - tw) / 2, y), ln, font=sf, fill=mute)
        y += 84

    # ---- HERO puzzle grid (the proof) — sized so badge sits cleanly BELOW it ----
    grid_cell = 128
    grid_cy = 1980
    hero_grid(d, W // 2, grid_cy, cell=grid_cell, theme=theme, accent=accent, deep=deep, hi=hi)

    # ---- BADGE (placed below grid with clear gap) ----
    grid_bottom = grid_cy + (9 * grid_cell) // 2
    if a.badge:
        vf = f(IMPACT, 110)
        vw = d.textlength(a.badge, font=vf)
        by = grid_bottom + 140
        bx = (W - vw) / 2
        pad = 64
        d.rounded_rectangle([bx - pad, by - 26, bx + vw + pad, by + 128], radius=30,
                            fill=hi, outline=deep, width=5)
        d.text((bx, by - 6), a.badge, font=vf, fill=deep)

    # ---- author ----
    if a.author:
        af = f(ARIALB, 68)
        aw = d.textlength(a.author, font=af)
        d.text(((W - aw) / 2, H - 280), a.author, font=af, fill=deep)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    img.save(a.out, "PNG")
    print(f"DONE -> {a.out}  ({W}x{H}, palette={a.palette}, theme={theme})")


if __name__ == "__main__":
    main()
