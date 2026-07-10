import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sudoku as sd


def _is_valid_solved_grid(g):
    full = set(range(1, 10))
    for row in g:
        if set(row) != full:
            return False
    for c in range(9):
        if {g[r][c] for r in range(9)} != full:
            return False
    for br in range(3):
        for bc in range(3):
            box = {g[br * 3 + i][bc * 3 + j] for i in range(3) for j in range(3)}
            if box != full:
                return False
    return True


def test_make_solved_produces_a_valid_grid_across_several_seeds():
    for seed in range(10):
        rng = random.Random(seed)
        grid = sd.make_solved(rng)
        assert len(grid) == 9 and all(len(row) == 9 for row in grid)
        assert _is_valid_solved_grid(grid), f"invalid grid for seed {seed}"


def test_make_solved_seeds_produce_different_grids():
    a = sd.make_solved(random.Random(1))
    b = sd.make_solved(random.Random(2))
    assert a != b


def test_count_solutions_on_a_full_grid_is_exactly_one():
    grid = sd.make_solved(random.Random(3))
    assert sd.count_solutions(grid, limit=2) == 1


def test_count_solutions_stops_at_the_limit():
    empty = [[0] * 9 for _ in range(9)]
    # a blank grid has vastly more than 2 solutions; count_solutions must not
    # exhaustively search them all -- it should stop right at the cap.
    assert sd.count_solutions(empty, limit=2) == 2


def test_make_puzzle_carved_from_solved_grid_has_a_unique_solution():
    rng = random.Random(4)
    solved = sd.make_solved(rng)
    puzzle = sd.make_puzzle(solved, "easy", rng)
    assert sd.count_solutions([row[:] for row in puzzle], limit=2) == 1
