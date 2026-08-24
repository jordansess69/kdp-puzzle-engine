"""Deterministic word-pool builder for puzzle generation.

Implements the mission's selection gate (§55-58): eligible words must be
topic-eligible AND quality-screened; each puzzle gets an anchor/support/
specialty mix; repetition policy is honoured exactly or raises - words are
never silently reused or dropped.

The builder NEVER invents vocabulary: if the pool cannot satisfy the
request it returns the shortfall with actionable detail.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .analysis import words_for_topic, estimate_capacity
from .quality import PuzzleWorthiness, assess_quality, familiarity_tier


DIFFICULTY_MIN_ZIPF = {
    "easy": 3.2,       # very familiar words only
    "medium": 2.6,     # standard screen (matches existing audit rules)
    "hard": 2.2,       # enthusiasts' vocabulary allowed
}
DEFAULT_DIFFICULTY = "medium"

MAX_SPECIALTY_SHARE = 0.2   # specialty words per puzzle
MIN_ANCHORS_PER_PUZZLE = 1
MAX_ANCHOR_TARGET = 4


@dataclass
class PoolRequest:
    topic_id: str
    puzzle_count: int
    words_per_puzzle: int
    difficulty: str = DEFAULT_DIFFICULTY
    subtopics: list[str] | None = None      # canonical subtopic ids to balance
    series_context: list[str] | None = None # words already used by sibling books
    seed: int | None = None


@dataclass
class PoolResult:
    puzzles: list[list[str]] = field(default_factory=list)
    unused_pool: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    shortfall: int = 0
    capacity: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "puzzles": [list(p) for p in self.puzzles],
            "unused_pool": list(self.unused_pool),
            "warnings": list(self.warnings),
            "shortfall": self.shortfall,
            "capacity": dict(self.capacity),
        }


def _difficulty_ok(record, difficulty: str) -> tuple[bool, str]:
    min_zipf = DIFFICULTY_MIN_ZIPF.get(difficulty, DIFFICULTY_MIN_ZIPF["medium"])
    if record.safety_review:
        return False, "safety"
    quality = assess_quality(record)
    if quality.worthiness in (PuzzleWorthiness.EXCLUDE,):
        return False, "quality exclude"
    freq = record.frequency
    if freq is not None and freq < min_zipf:
        return False, f"zipf {freq:.1f} below {difficulty} floor {min_zipf}"
    if quality.worthiness == PuzzleWorthiness.REVIEW:
        return False, "needs review"
    if quality.worthiness == PuzzleWorthiness.SPECIALIZED and difficulty == "easy":
        return False, "specialized word in easy book"
    return True, ""


def collect_eligible_words(store, taxonomy, request: PoolRequest,
                           min_band: str = "medium") -> dict[str, list[str]]:
    """Eligible pool keyed by role: anchor / support / specialty."""
    from .quality import role_for
    from .records import APPROVED, PROPOSED, TRUSTED, band_of

    roles: dict[str, list[str]] = {"anchor": [], "support": [], "specialty": []}
    used_elsewhere = set(request.series_context or [])
    for norm in words_for_topic(store, request.topic_id, min_band=min_band):
        record = store.get(norm)
        ok, _reason = _difficulty_ok(record, request.difficulty)
        if not ok:
            continue
        link = record.link_for(request.topic_id)
        is_trusted = bool(link and link.status in (TRUSTED, APPROVED))
        role = role_for(assess_quality(record).worthiness,
                        link.confidence if link else 0.0, is_trusted)
        roles[role].append(norm)
    return roles


def build_word_pool(store, taxonomy, request: PoolRequest,
                    min_band: str = "medium") -> PoolResult:
    rng = random.Random(request.seed)
    needed = request.puzzle_count * request.words_per_puzzle
    result = PoolResult()

    roles = collect_eligible_words(store, taxonomy, request, min_band)
    all_eligible = sorted(set().union(*roles.values()))
    result.capacity = estimate_capacity(len(all_eligible), request.words_per_puzzle)

    for role in ("anchor", "support", "specialty"):
        roles[role] = sorted(set(roles[role]) - set(request.series_context or []))
        rng.shuffle(roles[role])

    total_available = sum(len(v) for v in roles.values())
    if total_available < needed:
        result.shortfall = needed - total_available
        result.warnings.append(
            f"Pool short by {result.shortfall} eligible words "
            f"(have {total_available}, need {needed}); "
            f"classify more vocabulary or relax filters")
        return result

    anchors = roles["anchor"]
    supports = roles["support"]
    specialties = roles["specialty"]

    max_specialty_per_puzzle = int(request.words_per_puzzle * MAX_SPECIALTY_SHARE)
    consumed: set[str] = set()

    for index in range(request.puzzle_count):
        puzzle: list[str] = []

        def take(pool: list[str], count: int) -> None:
            taken = 0
            while taken < count and pool:
                candidate = pool.pop()
                if candidate in consumed:
                    continue
                puzzle.append(candidate)
                consumed.add(candidate)
                taken += 1

        # Anchor presence first, then support fill, then a specialty garnish.
        anchor_target = min(MAX_ANCHOR_TARGET,
                            max(MIN_ANCHORS_PER_PUZZLE,
                                request.words_per_puzzle // 6))
        take(anchors, anchor_target)
        specialty_target = min(max_specialty_per_puzzle, len(specialties))
        take(specialties, specialty_target)
        remaining = request.words_per_puzzle - len(puzzle)
        take(supports, remaining)
        # Top up from any pool if support ran dry.
        if len(puzzle) < request.words_per_puzzle:
            for backup in (supports, anchors, specialties):
                before = len(puzzle)
                take(backup, request.words_per_puzzle - len(puzzle))
                if len(puzzle) >= request.words_per_puzzle:
                    break
        if len(puzzle) < request.words_per_puzzle:
            break  # exhausted mid-run; report shortfall below
        result.puzzles.append(sorted(puzzle))

    placed = sum(len(p) for p in result.puzzles)
    expected = min(needed, total_available)
    if placed < needed:
        result.shortfall = needed - placed
        result.warnings.append(
            f"Built {len(result.puzzles)} of {request.puzzle_count} puzzles "
            f"before exhausting the pool")

    leftovers: set[str] = set()
    for role in ("anchor", "support", "specialty"):
        leftovers |= set(roles[role])
    leftovers -= consumed
    result.unused_pool = sorted(leftovers)
    return result
