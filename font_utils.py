"""Shared font discovery and loading for every generator in this project.

Before this module existed, five files each carried their own copy of hard-coded
font paths (macOS absolute paths in the cover tools, ``C:/Windows`` paths in the
PDF engines, and an inline check in the Etsy bundle builder).  Those copies
drifted apart and broke whenever a preferred system font was not where the code
expected it.  This module keeps one ordered candidate list per font family and
searches the real font directories of the current platform (Windows system and
per-user folders, macOS font libraries, common Linux font locations).
"""
from __future__ import annotations

import os
from pathlib import Path

# Candidate order matters: the first file that exists wins.  Every list starts
# with the exact files this project has always used (the macOS absolute path,
# then the classic Windows file name) so rendered output stays identical on any
# machine that already produced books with the old hard-coded loaders.

_IMAGE_FAMILY_CANDIDATES: dict[str, tuple[str, ...]] = {
    # Used by Pillow (cover art, wrap art, Etsy bundle images).
    "sans": ("/System/Library/Fonts/Supplemental/Arial.ttf", "arial.ttf",
             "LiberationSans-Regular.ttf", "DejaVuSans.ttf"),
    "sans-bold": ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "arialbd.ttf",
                  "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"),
    "impact": ("/System/Library/Fonts/Supplemental/Impact.ttf", "impact.ttf",
               "arialbd.ttf", "DejaVuSans-Bold.ttf"),
    "georgia-bold": ("/System/Library/Fonts/Supplemental/Georgia Bold.ttf", "georgiab.ttf",
                     "arialbd.ttf", "DejaVuSans-Bold.ttf"),
    # Historical quirk kept on purpose: cover.py's hero grid asked for Courier
    # New Bold but its fallback chain jumped straight to Arial Bold, so Windows
    # covers have always drawn those letters in Arial Bold.  Keep the same chain
    # instead of silently changing published cover artwork.
    "display-mono": ("/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
                     "arialbd.ttf", "DejaVuSans-Bold.ttf"),
}

_PDF_FAMILY_CANDIDATES: dict[str, tuple[str, ...]] = {
    # Used by ReportLab interior pages.  The registered aliases stay exactly as
    # before (Sans/SansB/MonoB for word search and Sudoku, BookSans/BookBold/
    # BookMono for the studio).
    "sans": ("/System/Library/Fonts/Supplemental/Arial.ttf", "arial.ttf",
             "LiberationSans-Regular.ttf", "DejaVuSans.ttf"),
    "sans-bold": ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "arialbd.ttf",
                  "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"),
    "mono-bold": ("/System/Library/Fonts/Supplemental/Courier New Bold.ttf", "courbd.ttf",
                  "LiberationMono-Bold.ttf", "DejaVuSansMono-Bold.ttf"),
}


def font_search_dirs() -> list[Path]:
    """System and per-user font directories for this platform, best first."""
    dirs: list[Path] = []
    windir = os.environ.get("WINDIR") or r"C:\Windows"
    dirs.append(Path(windir) / "Fonts")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        # Per-user installed fonts (Windows 10+), e.g. fonts added without admin rights.
        dirs.append(Path(local_app_data) / "Microsoft" / "Windows" / "Fonts")
    home = Path.home()
    dirs.extend([
        Path("/System/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/Library/Fonts"),
        home / "Library" / "Fonts",
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/truetype/liberation"),
        Path("/usr/local/share/fonts"),
        home / ".fonts",
        home / ".local" / "share" / "fonts",
    ])
    unique: list[Path] = []
    seen: set[Path] = set()
    for directory in dirs:
        if directory not in seen:
            seen.add(directory)
            unique.append(directory)
    return unique


def resolve_font_file(candidates) -> Path | None:
    """Return the first existing font file from explicit paths or bare names."""
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_absolute():
            if path.is_file():
                return path
            continue
        for directory in font_search_dirs():
            hit = directory / candidate
            if hit.is_file():
                return hit
    return None


def pdf_font_candidates(family: str) -> list[str]:
    """Ordered ReportLab font candidates for a family."""
    return list(_PDF_FAMILY_CANDIDATES[family])


def image_font_candidates(family: str) -> list[str]:
    """Ordered Pillow font candidates for a family."""
    return list(_IMAGE_FAMILY_CANDIDATES[family])


def register_pdf_font(alias: str, candidates) -> bool:
    """Register a ReportLab TTFont under ``alias``, trying candidates in order.

    Skips aliases that are already registered (the puzzle studio relied on that
    behaviour).  Returns True when ``alias`` is usable afterwards.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if alias in pdfmetrics.getRegisteredFontNames():
        return True
    resolved = resolve_font_file(candidates)
    if resolved is None:
        return False
    pdfmetrics.registerFont(TTFont(alias, str(resolved)))
    return True


def load_image_font(candidates, size: int):
    """Load a Pillow font from the first loadable candidate, in order.

    Bare file names are also looked up in the platform font directories, then
    still handed to Pillow itself so its own bundled-font search keeps working.
    Falls back to the bitmap default font, matching the old cover behaviour.
    """
    from PIL import ImageFont

    for candidate in candidates:
        if not candidate:
            continue
        resolved = resolve_font_file([candidate])
        path = str(resolved) if resolved else candidate
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()
