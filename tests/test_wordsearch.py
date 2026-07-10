import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wordsearch as ws


def test_clean_words_uppercases_and_strips_non_alpha():
    assert ws.clean_words(["cat", "Dog-2", "  fish "]) == ["CAT", "DOG", "FISH"]


def test_clean_words_drops_words_longer_than_grid():
    too_long = "X" * (ws.GRID_N + 1)
    assert too_long not in ws.clean_words([too_long, "OK"])


def test_clean_words_drops_empty_results():
    assert ws.clean_words(["123", "-- ", "cat"]) == ["CAT"]


def test_generate_puzzle_grid_is_square_and_fully_filled():
    random.seed(1)
    grid, placements, placed = ws.generate_puzzle(["CAT", "DOG", "BIRD", "FISH"])
    assert len(grid) == ws.GRID_N
    assert all(len(row) == ws.GRID_N for row in grid)
    assert all(cell != "" for row in grid for cell in row)


def test_generate_puzzle_placed_words_actually_read_off_the_grid():
    random.seed(1)
    grid, placements, placed = ws.generate_puzzle(["CAT", "DOG", "BIRD", "FISH"])
    assert placed, "expected at least one word to be placed in a 15x15 grid"
    for word, cells in zip(placed, placements):
        read_back = "".join(grid[r][c] for r, c in cells)
        assert read_back == word


def test_generate_puzzle_only_reports_words_it_was_given():
    random.seed(2)
    words = ["CAT", "DOG"]
    _, _, placed = ws.generate_puzzle(words)
    assert set(placed) <= set(words)
