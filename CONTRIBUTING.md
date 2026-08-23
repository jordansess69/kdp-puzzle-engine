# Contributing

## Setup

```
git clone https://github.com/vijaxx/kdp-puzzle-engine.git
cd kdp-puzzle-engine
pip install -r requirements-dev.txt
```

## Running tests

```
python -m pytest tests/ -v
```

CI runs this plus `python -m compileall -q .` on every push and PR. The tests cover the deterministic generation logic (grid layout, word placement, Sudoku validity) directly — no PDF rendering or file I/O involved, so they run in well under a second.

## Making a change

1. Branch off `main`.
2. If you're touching `wordsearch.py` or `sudoku.py`, add a test alongside the existing ones in `tests/` — these are pure functions and cheap to cover.
3. PDF/cover rendering (`draw_*`, `front_matter`, `back_matter`, etc.) is harder to unit test meaningfully; changes there are reviewed by generating a sample book and checking it by eye rather than by an automated check.
4. Open a PR against `main`.

Note: `pinforge` (a sibling project) imports `wordsearch.py` from this repo directly (`sys.path` trick, not a package import) — a signature change to `generate_puzzle()` or `clean_words()` will need a matching update over there.
