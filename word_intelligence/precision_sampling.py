"""Precision sampling harness - the quality gate for auto-linking.

Mission §44: before the apply engine may connect VERY_HIGH links
automatically, a sampled audit must show >=98% precision on that band.
This module draws deterministic samples (seeded) from a classified store
and produces the evidence report.  It NEVER modifies data.

Sample strata:
  very_high / high / medium proposals
  bad_links   (proposals below the floor)
  unclassified (words with no association)
"""

from __future__ import annotations

import random
from datetime import datetime

from .records import PROPOSED, band_of

AUTO_APPLY_PRECISION_GATE = 98.0


def _proposal_pool(store, band: str) -> list[tuple[str, str, float]]:
    pool = []
    for norm, record in sorted(store.records.items()):
        for link in record.topics:
            if link.status == PROPOSED and band_of(link.confidence) == band:
                pool.append((norm, link.topic_id, link.confidence))
    return pool


def draw_samples(store, sample_size: int = 100, seed: int = 20260823) -> dict:
    rng = random.Random(seed)
    strata: dict[str, list] = {}
    for band in ("very_high", "high", "medium"):
        pool = _proposal_pool(store, band)
        strata[band] = sorted(rng.sample(pool, min(sample_size, len(pool))))
    bad = []
    unclassified = []
    for norm, record in sorted(store.records.items()):
        if record.is_unclassified():
            unclassified.append(norm)
        for link in record.topics:
            if link.status == PROPOSED and band_of(link.confidence) == "low":
                bad.append((norm, link.topic_id, link.confidence))
                break
    strata["bad_links"] = sorted(bad)[:sample_size]
    strata["unclassified"] = sorted(unclassified)[:sample_size]
    return strata


def score_sample(stratum: list[tuple[str, str, float]],
                 judgements: dict[tuple[str, str], bool]) -> dict:
    """Score human judgements { (word, topic): correct? } for one stratum."""
    total = len(stratum)
    judged = [pair for pair in stratum if (pair[0], pair[1]) in judgements]
    correct = sum(1 for pair in judged if judgements[(pair[0], pair[1])])
    precision = (100.0 * correct / len(judged)) if judged else None
    return {
        "sample_size": total,
        "judged": len(judged),
        "correct": correct,
        "precision": round(precision, 2) if precision is not None else None,
    }


def gate_decision(scores: dict) -> dict:
    """Apply the mission's stop-rule to sampled scores."""
    vh = scores.get("very_high", {})
    precision = vh.get("precision")
    enough_data = vh.get("judged", 0) >= 30
    passed = bool(enough_data and precision is not None
                  and precision >= AUTO_APPLY_PRECISION_GATE)
    return {
        "auto_apply_allowed": passed,
        "gate": AUTO_APPLY_PRECISION_GATE,
        "very_high_precision": precision,
        "judged": vh.get("judged", 0),
        "reason": ("Precision gate met" if passed else
                   "Insufficient judgements (<30)" if not enough_data else
                   f"Precision {precision}% below {AUTO_APPLY_PRECISION_GATE}%"),
        "evaluated_at": datetime.now().isoformat(timespec="seconds"),
    }
