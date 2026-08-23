"""Measure all interior text against KDP's minimum 0.5-inch safe bounds."""
from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber


def main(root_text: str) -> None:
    root = Path(root_text)
    pdf_paths = [root / "interior.pdf"] if (root / "interior.pdf").is_file() else sorted(root.glob("*/interior.pdf"))
    for pdf_path in pdf_paths:
        with pdfplumber.open(pdf_path) as document:
            all_chars = [char for page in document.pages for char in page.chars]
            outside = [
                page_number
                for page_number, page in enumerate(document.pages, 1)
                if page.chars and (min(char["x0"] for char in page.chars) < 36 or max(char["x1"] for char in page.chars) > 576)
            ]
            print(
                f"{pdf_path.parent.name}: pages={len(document.pages)}, "
                f"min_x={min(char['x0'] for char in all_chars):.1f}, "
                f"max_x={max(char['x1'] for char in all_chars):.1f}, "
                f"outside_KDP_minimum={outside}"
            )


if __name__ == "__main__":
    main(sys.argv[1])
