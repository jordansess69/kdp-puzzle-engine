# KDP Puzzle Engine

Generates print-ready, large-print puzzle books — word search, Sudoku, and mazes — as camera-ready PDFs for Amazon KDP. Swap in a themed word list and it produces a complete new book: interior PDF, cover, and back-cover wrap, laid out to KDP's print specs.

The premise: most puzzle-book sellers on KDP build books by hand, one at a time. This generates them, so a new niche is a new JSON file away from a new title rather than a new manual layout job.

## Generators

- **`wordsearch.py`** — takes a theme JSON (a name + word list), lays out a large-print grid guaranteed to place every word, and renders front matter, puzzles, and a full solutions section to an 8.5x11 interior PDF.
- **`sudoku.py`** — standard 9x9 puzzles. Generates valid solved grids via symmetry-preserving transformations of a base grid, then removes cells to hit a target difficulty.
- **`mazes.py`** — perfect mazes (exactly one solution path) via recursive backtracking, one per page, solutions at the back.
- **`cover.py`** / **`cover_sudoku.py`** / **`cover_maze.py`** / **`wrap_cover.py`** — cover and full-wrap (front + spine + back) generation at 300 DPI, palette-matched per theme.

## Automation layer

- **`build_theme_book.py`** — the end-to-end path for a themed word-search book: theme JSON in, complete `{interior.pdf, cover.png, wrap.pdf}` folder out.
- **`auto_factory.py`** — an unattended factory mode that rotates across a fixed set of recipes (Sudoku/Mazes at a few difficulty tiers) so scheduled runs produce genuinely different books back-to-back rather than near-duplicates (which KDP penalizes), tracking its own position in the rotation between runs.
- **`gen_themes.py`** — drafts a theme's word list via a local LLM (Ollama) as a starting point — output is intentionally treated as a first draft, not a final list.
- **`preflight.py`** — a compliance check that runs on a built book folder before it's ever uploaded: page-size/count sanity, and the specific formatting issues that have triggered Amazon KDP review flags in practice (e.g. author-field/imprint conflicts, spine text sitting too close to the trim edge on thin books).
- **`publish_tools/`** — small scripts that drive already-published KDP listings: updating a book's search keywords, attaching a book to a series, and the underlying CDP session handling they share.

## Themes

`themes/*.json` are the word lists that drive `wordsearch.py` — one file per niche (animals, nature, travel, holidays, and so on). `specs/*.json` are lighter skeleton specs (just sub-theme names) used as input to `gen_themes.py` when drafting a new one.

## Stack

Python, reportlab (PDF generation), Pillow (cover rendering), a local Ollama model for word-list drafting, Chrome DevTools Protocol for the KDP listing-management tools.

## Running it

```
python3 wordsearch.py --themes themes/nature.json --out out/nature.pdf
python3 build_theme_book.py themes/beach-vacation.json      # full book folder: interior + cover + wrap
python3 auto_factory.py                                     # one factory-mode book, next recipe in rotation
python3 preflight.py out/beach-vacation/                    # compliance check before upload
```
