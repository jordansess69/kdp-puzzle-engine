"""Theme library cleanup: canonical inventory, dry-run repair plans, safe apply.

Design principles (mission + user direction):
  * Good existing content is preserved. Only words with a concrete failure
    cause (off-topic evidence, trademark/safety flags, duplicates beyond the
    first use, weak puzzle-worthiness) are candidates for replacement.
    Words we simply cannot judge (unverified) are kept, never blindly swapped.
  * Replacement candidates must be production-eligible: strong topic
    confidence to the theme's own anchors, clean safety/trademark record,
    no ambiguity conflict, sane length, and not already used in the book.
  * Dry-run plans come first. A plan is auto-applicable only when EVERY
    chosen replacement carries very-high-confidence or trusted/approved
    evidence and zero ambiguity conflicts; anything less routes to the
    human review queue.
  * Application never writes a file directly. The caller snapshots the
    target, applies in memory, validates JSON, then writes atomically.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .analysis import STANDARD_BOOK_WORDS
from .normalization import _VARIANT_LOOKUP, clean_surface
from .quality import PuzzleWorthiness, assess_quality
from .records import APPROVED, PROPOSED, TRUSTED, band_of
from .theme_audit import (
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_PASS_WITH_NOTES,
    WordFinding,
    audit_all_themes,
    audit_theme,
)

AUTO_APPLY_MAX_OFF_TOPIC_RATIO = 0.20   # legacy single threshold (superseded by tiers)
MAX_CANDIDATES_PER_WORD = 10

# Repair-scale tiers. Thresholds come from the measured 2026-08-24 plan
# distribution: proposed replacement shares span 17.7%-49.5% across all 93
# plans with NONE below 10%. There is therefore no real "small repair"
# population today - an honest auto tier is expected to be empty or nearly
# empty until audit precision improves. Curated books whose audit disagrees
# with a fifth-to-half of their vocabulary need human curation, never batch
# rewriting.
TIER_AUTO = "auto"                   # <= AUTO_TIER_MAX_SHARE, all swaps >= AUTO_TIER_MIN_CONFIDENCE
TIER_REVIEW = "review"               # moderate changes: explicit per-plan approval to apply
TIER_APPROVAL = "approval_required"  # large-scale rewrite territory
TIER_BLOCKED = "blocked"             # unresolved words / missing anchors: never applies

AUTO_TIER_MAX_SHARE = 0.10           # >1 in 10 words changed is not a touch-up
REVIEW_TIER_MAX_SHARE = 0.35         # beyond a third of the book is rewrite territory
AUTO_TIER_MIN_CONFIDENCE = 95.0      # very-high band only
MIN_WORDS_PER_PUZZLE_AFTER_REPAIR = 8

CAUSE_OFF_TOPIC = "off_topic"
CAUSE_TRADEMARK = "trademark_contamination"
CAUSE_SAFETY = "safety_flag"
CAUSE_DUPLICATE = "duplicate_beyond_first_use"
CAUSE_WEAK = "low_puzzle_worthiness"

_REPAIRABLE_CAUSES = {CAUSE_OFF_TOPIC, CAUSE_TRADEMARK, CAUSE_SAFETY,
                      CAUSE_DUPLICATE, CAUSE_WEAK}


def cause_for(finding: WordFinding) -> str | None:
    """Map an audit finding to the cleanup taxonomy's cause buckets."""
    if finding.status == "off_topic":
        return CAUSE_OFF_TOPIC
    if finding.status == "flagged":
        if finding.detail.startswith("Trademark"):
            return CAUSE_TRADEMARK
        if finding.detail.startswith("Exclusion"):
            return CAUSE_SAFETY
    if finding.status == "duplicate":
        # The audit marks every repeat; repairs keep the first occurrence.
        return CAUSE_DUPLICATE
    if finding.status == "weak":
        return CAUSE_WEAK
    return None


# ---------------------------------------------------------------------------
# Canonical failure inventory
# ---------------------------------------------------------------------------

def content_signature(theme_data: dict) -> str:
    """Hash of the vocabulary + first puzzle names, for duplicate detection."""
    puzzles = theme_data.get("puzzles") or []
    words = sorted(str(w) for pz in puzzles for w in (pz.get("words") or []))
    names = tuple(str(pz.get("name")) for pz in puzzles[:5])
    blob = json.dumps([words, names], ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def _is_signature_stem(file_name: str) -> bool:
    return "signature" in Path(file_name).stem.lower()


def _accidental_duplicate_groups(signatures: dict[str, list[str]]) -> list[dict]:
    """True duplicate groups: identical content AND same product kind.

    A Standard Edition and its Signature Edition intentionally share
    vocabulary - they are two products of one series, never merged. Only
    same-kind copies (timestamped rebuilds, re-saves) are accidental.
    Within an accidental group the NEWEST copy (highest name sort) is kept;
    earlier copies become archival.
    """
    groups = []
    for sig, files in signatures.items():
        if len(files) < 2:
            continue
        buckets: dict[bool, list[str]] = {True: [], False: []}
        for name in files:
            buckets[_is_signature_stem(name)].append(name)
        for same_kind in buckets.values():
            if len(same_kind) < 2:
                continue
            ordered = sorted(same_kind)   # timestamped names sort chronologically
            groups.append({
                "signature": sig,
                "files": ordered,
                "keep": ordered[-1],
                "archive": ordered[:-1],
            })
    return sorted(groups, key=lambda g: -len(g["files"]))


def build_inventory(themes_dir, store, taxonomy) -> dict:
    """Canonical failure inventory for the whole library.

    Every failing word is recorded under its cause bucket; duplicate content
    groups and per-theme dispositions (repair / partial / archive / retain)
    make this the single source of truth for the cleanup batches.
    """
    audit = audit_all_themes(str(themes_dir), store, taxonomy)
    signatures: dict[str, list[str]] = {}
    themes: list[dict] = []

    for report in audit["reports"]:
        causes: dict[str, list[dict]] = {}
        for finding in report.findings:
            cause = cause_for(finding)
            if cause is None:
                continue
            causes.setdefault(cause, []).append({
                "word": finding.display,
                "normalized": finding.normalized,
                "puzzle_index": finding.puzzle_index,
                "detail": finding.detail,
            })
        counts = report.to_dict()["counts"]
        total_bad = sum(len(v) for v in causes.values())
        # Keep the library-relative path (incl. subfolders) so downstream
        # plan/apply steps can find every file and same-stem files in
        # different folders never collide.
        try:
            entry_file = Path(report.theme_file).relative_to(
                themes_dir).as_posix()
        except ValueError:
            entry_file = Path(report.theme_file).name
        entry = {
            "file": entry_file,
            "title": report.title,
            "verdict": report.verdict,
            "word_count": report.word_count,
            "targets": report.target_topics,
            "counts": counts,
            "causes": {k: v for k, v in sorted(causes.items())},
            "bad_words_total": total_bad,
        }
        sig = content_signature(report.theme_data) \
            if report.theme_data is not None \
            else content_signature_from_report(report.theme_file)
        if sig:
            signatures.setdefault(sig, []).append(entry["file"])
        themes.append(entry)

    duplicate_groups = _accidental_duplicate_groups(signatures)
    archive_members = {f for group in duplicate_groups for f in group["archive"]}

    for entry in themes:
        entry["disposition"] = recommend_disposition(entry, archive_members)

    inventory = {
        "themes_scanned": audit["themes_scanned"],
        "audited": audit["audited"],
        "skipped_unreadable": audit["skipped_unreadable"],
        "verdict_counts": audit["verdicts"],
        "finding_cause_totals": {
            cause: sum(len(e["causes"].get(cause, [])) for e in themes)
            for cause in sorted(_REPAIRABLE_CAUSES)
        },
        "duplicate_content_groups": duplicate_groups,
        "themes": themes,
    }
    return inventory


def content_signature_from_report(theme_file) -> str:
    try:
        data = json.loads(Path(theme_file).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ""
    return content_signature(data)


def recommend_disposition(entry: dict, dup_members: set[str]) -> str:
    """repair | repair_partial | archive_candidate | merge_duplicate | retain."""
    if entry["file"] in dup_members:
        # Newest timestamped copy stays; earlier copies become archival.
        return "merge_duplicate"
    if entry["verdict"] in (VERDICT_PASS, VERDICT_PASS_WITH_NOTES):
        return "retain"
    bad = entry["bad_words_total"]
    total = max(entry["word_count"], 1)
    ratio = bad / total
    if total >= 500 and not entry["targets"]:
        return "archive_candidate"      # legacy freeform bank beyond targeted repair
    if ratio > 0.5:
        return "archive_candidate"      # majority-contaminated book: rewriting it
                                        # would be exactly the blind rewrite we avoid
    if bad > 150 or ratio > 0.15:
        return "repair_partial"         # structural: targeted swaps + pool curation
    return "repair"


# ---------------------------------------------------------------------------
# Repair planning
# ---------------------------------------------------------------------------

@dataclass
class WordReplacement:
    puzzle_index: int
    old_word: str
    normalized: str
    cause: str
    reason: str
    chosen: str
    alternates: list[str] = field(default_factory=list)
    confidence: float = 0.0
    topic_id: str = ""

    def to_dict(self) -> dict:
        return {
            "puzzle_index": self.puzzle_index, "old_word": self.old_word,
            "normalized": self.normalized, "cause": self.cause,
            "reason": self.reason, "chosen": self.chosen,
            "alternates": list(self.alternates),
            "confidence": self.confidence, "topic_id": self.topic_id,
        }


@dataclass
class ThemeRepairPlan:
    theme_file: str
    title: str
    replacements: list[WordReplacement] = field(default_factory=list)
    unresolved: list[dict] = field(default_factory=list)
    tier: str = TIER_BLOCKED
    blockers: list[str] = field(default_factory=list)
    word_count: int = 0
    puzzles_affected: int = 0

    @property
    def replacement_count(self) -> int:
        return len(self.replacements)

    @property
    def auto_applicable(self) -> bool:
        """Back-compat gate: only the auto tier may ever apply silently."""
        return self.tier == TIER_AUTO

    @property
    def replacement_share(self) -> float:
        return len(self.replacements) / max(self.word_count, 1)

    def to_dict(self) -> dict:
        return {
            "theme_file": self.theme_file,
            "title": self.title,
            "tier": self.tier,
            "auto_applicable": self.auto_applicable,
            "blockers": list(self.blockers),
            "replacement_count": len(self.replacements),
            "replacement_share": round(self.replacement_share, 4),
            "word_count": self.word_count,
            "puzzles_affected": self.puzzles_affected,
            "unresolved_count": len(self.unresolved),
            "replacements": [r.to_dict() for r in self.replacements],
            "unresolved": list(self.unresolved),
        }


def classify_repair_tier(share: float, unresolved_count: int,
                         min_confidence: float | None,
                         causes: set[str]) -> str:
    """Assign the safety tier for a repair plan.

    Rules (most restrictive wins):
      * any unresolved word  -> blocked (plan incomplete)
      * share > REVIEW_TIER_MAX_SHARE -> approval_required (rewrite scale)
      * share > AUTO_TIER_MAX_SHARE   -> review
      * any swap below very-high confidence -> review
      * trademark/safety causes always get human eyes, even when tiny
      * otherwise -> auto
    """
    if unresolved_count:
        return TIER_BLOCKED
    if share > REVIEW_TIER_MAX_SHARE:
        return TIER_APPROVAL
    if share > AUTO_TIER_MAX_SHARE:
        return TIER_REVIEW
    if min_confidence is not None and min_confidence < AUTO_TIER_MIN_CONFIDENCE:
        return TIER_REVIEW
    if causes & {CAUSE_TRADEMARK, CAUSE_SAFETY}:
        return TIER_REVIEW
    return TIER_AUTO


def build_topic_member_index(store, taxonomy) -> dict[str, dict[str, float]]:
    """One-time scan mapping canonical topic -> eligible member -> confidence.

    Membership mirrors the classifier's own evidence rules: trusted/approved
    links count fully, proposals only when they reach high band. This index
    is reused across every theme plan in a batch so the O(records) walk
    happens once.
    """
    index: dict[str, dict[str, float]] = {}
    for norm, record in store.records.items():
        if record.safety_review or record.trademark_review:
            continue
        quality = assess_quality(record)
        if quality.worthiness in (PuzzleWorthiness.REVIEW, PuzzleWorthiness.EXCLUDE):
            continue
        if not (3 <= len(norm) <= 15):
            continue
        for link in record.topics:
            if link.status in (TRUSTED, APPROVED):
                score = link.confidence
            elif link.status == PROPOSED and \
                    band_of(link.confidence) in ("high", "very_high"):
                score = link.confidence
            else:
                continue
            members = index.setdefault(link.topic_id, {})
            if score > members.get(norm, 0.0):
                members[norm] = score
    # Taxonomy-trusted vocabulary (master bank) may exceed store links when
    # the store was built read-only without ingestion; union both views.
    for cid, words in getattr(taxonomy, "trusted_words", {}).items():
        members = index.setdefault(cid, {})
        for norm in words:
            record = store.get(norm)
            if record is None or record.safety_review or record.trademark_review:
                continue
            if norm not in members:
                members[norm] = 100.0
    return index


def candidate_pool(targets, related_ids, member_index) -> dict[str, float]:
    """Production-eligible words for the anchor topics, with best confidence."""
    pool: dict[str, float] = {}
    allowed_topics = set(targets) | set(related_ids)
    for cid in sorted(allowed_topics):
        for norm, score in member_index.get(cid, {}).items():
            pool[norm] = max(pool.get(norm, 0.0), score)
    return pool


def _rank_candidates(candidates: dict[str, float], old_norm: str) -> list[str]:
    """Deterministic preference order: strongest evidence first, name as tiebreak."""
    old_key = _VARIANT_LOOKUP.get(old_norm, old_norm)
    scored = [
        (confidence, norm)
        for norm, confidence in candidates.items()
        if norm != old_norm and _VARIANT_LOOKUP.get(norm, norm) != old_key
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [norm for _, norm in scored]


def plan_theme_repairs(theme_data: dict, theme_file: str, store, taxonomy,
                       member_index: dict | None = None) -> ThemeRepairPlan:
    """Build the dry-run repair plan for one theme.

    Only findings with a repairable cause produce replacements; unverified
    words are deliberately left alone. When the eligible candidate pool runs
    dry, the word is listed as unresolved with its reason instead of forcing
    a poor swap.
    """
    if member_index is None:
        member_index = build_topic_member_index(store, taxonomy)
    report = audit_theme(theme_data, str(theme_file), store, taxonomy)
    targets = report.target_topics
    related: set[str] = set()
    for cid in targets:
        related |= taxonomy.related_closure(cid, hops=1)
    pool = candidate_pool(targets, related, member_index) if targets else {}

    used_in_book: set[str] = set()
    for puzzle in theme_data.get("puzzles") or []:
        for word in puzzle.get("words") or []:
            used_in_book.add(clean_surface(word))

    plan = ThemeRepairPlan(theme_file=str(theme_file),
                           title=str(theme_data.get("title") or ""))
    seen_norm_puzzle: set[tuple[str, int]] = set()

    for finding in report.findings:
        cause = cause_for(finding)
        if cause is None:
            continue
        key = (finding.normalized, finding.puzzle_index)
        if key in seen_norm_puzzle:
            continue
        seen_norm_puzzle.add(key)

        # Duplicates: later occurrences are removed outright when the word is
        # otherwise fine; the first occurrence always stays.
        if cause == CAUSE_DUPLICATE:
            plan.replacements.append(WordReplacement(
                puzzle_index=finding.puzzle_index,
                old_word=finding.display,
                normalized=finding.normalized,
                cause=cause,
                reason=finding.detail or "Repeated within the same book",
                chosen="-REMOVE-",
            ))
            continue

        options = _rank_candidates(pool, finding.normalized)
        fresh = [c for c in options if c not in used_in_book][:MAX_CANDIDATES_PER_WORD]
        if not fresh:
            plan.unresolved.append({
                "word": finding.display,
                "cause": cause,
                "reason": finding.detail,
                "why": ("No production-eligible candidate available in the "
                        "anchor pools; needs vocabulary curation"),
            })
            if "No production-eligible candidate available" not in plan.blockers:
                plan.blockers.append("No production-eligible candidate available")
            continue

        chosen = fresh[0]
        confidence = pool[chosen]
        # Diversity: a chosen replacement becomes "used" immediately so the
        # next replacement in the SAME plan cannot repeat it. Otherwise a
        # strong pool word (e.g. ABOLITION) would be stamped into every
        # puzzle, manufacturing the very repetition the cleanup forbids.
        used_in_book.add(chosen)
        if band_of(confidence) != "very_high" and confidence < AUTO_TIER_MIN_CONFIDENCE:
            if "Some replacements below very-high confidence" not in plan.blockers:
                plan.blockers.append("Some replacements below very-high confidence")
        plan.replacements.append(WordReplacement(
            puzzle_index=finding.puzzle_index,
            old_word=finding.display,
            normalized=finding.normalized,
            cause=cause,
            reason=finding.detail,
            chosen=chosen,
            alternates=fresh[1:],
            confidence=confidence,
            topic_id=targets[0] if targets else "",
        ))

    # SCALE GUARDRAIL (tiered): a repair that would swap a large share of a
    # book is not a repair - it is a rewrite, and rewrites need human
    # curation. Plans carry an explicit tier; only the auto tier may ever
    # apply without per-plan human approval, and blocked plans never apply.
    plan.word_count = max(report.word_count, len(plan.replacements), 1)
    plan.puzzles_affected = len({r.puzzle_index for r in plan.replacements})
    causes = {r.cause for r in plan.replacements}
    min_conf = min((r.confidence for r in plan.replacements
                    if r.chosen != "-REMOVE-"), default=None)
    share = len(plan.replacements) / plan.word_count
    plan.tier = classify_repair_tier(share, len(plan.unresolved),
                                     min_conf, causes)
    if plan.tier != TIER_AUTO and \
            f"Tier '{plan.tier}'" not in "".join(plan.blockers):
        plan.blockers.insert(0, f"Tier '{plan.tier}': "
                             f"repair affects {share:.0%} of the book - "
                             f"requires explicit human approval to apply")
    return plan


# ---------------------------------------------------------------------------
# Applying plans (in-memory only; caller snapshots + writes atomically)
# ---------------------------------------------------------------------------

def apply_plan(theme_data: dict, plan: ThemeRepairPlan) -> tuple[dict, list[dict]]:
    """Return (new_theme_data, changelog) with replacements applied.

    Duplicate entries marked ``-REMOVE-`` drop every occurrence AFTER the
    first within that puzzle. Word lists stay uppercase letter-only.
    """
    import copy

    new_data = copy.deepcopy(theme_data)
    changelog: list[dict] = []
    puzzles = new_data.get("puzzles") or []

    for rep in plan.replacements:
        idx = rep.puzzle_index
        if not (0 <= idx < len(puzzles)):
            continue
        words = puzzles[idx].get("words")
        if not isinstance(words, list):
            continue
        if rep.chosen == "-REMOVE-":
            cleaned = clean_surface(rep.old_word)
            for pos, word in enumerate(words):
                if clean_surface(word) != cleaned:
                    continue
                # Keep-first: drop this occurrence only if an earlier one exists.
                if any(clean_surface(w) == cleaned for w in words[:pos]):
                    del words[pos]
                    changelog.append({"action": "remove_duplicate",
                                      "puzzle_index": idx,
                                      "word": rep.old_word})
            continue
        target_clean = clean_surface(rep.old_word)
        for pos, word in enumerate(words):
            if clean_surface(word) == target_clean:
                words[pos] = rep.chosen
                changelog.append({
                    "action": "replace",
                    "puzzle_index": idx,
                    "old": rep.old_word,
                    "new": rep.chosen,
                    "cause": rep.cause,
                    "confidence": rep.confidence,
                })
                break

    # Puzzle-capacity floor: repairs may never starve a real puzzle below
    # the engine's usable minimum. Swaps preserve counts, so this only
    # bites duplicate-removal plans - exactly where silent thinning could
    # happen. Puzzles already below the minimum are left alone rather than
    # made unrepairable (their fix is curation, not blocked dedup).
    for idx, puzzle in enumerate(puzzles):
        words = puzzle.get("words")
        if not isinstance(words, list):
            continue
        touched = any(c.get("action") == "remove_duplicate"
                      and c["puzzle_index"] == idx for c in changelog)
        if touched and len(words) < MIN_WORDS_PER_PUZZLE_AFTER_REPAIR \
                and len(words) + sum(
                    1 for c in changelog
                    if c.get("action") == "remove_duplicate"
                    and c["puzzle_index"] == idx) \
                >= MIN_WORDS_PER_PUZZLE_AFTER_REPAIR:
            raise ValueError(
                f"Puzzle {idx} would fall below "
                f"{MIN_WORDS_PER_PUZZLE_AFTER_REPAIR} words after repair")
    return new_data, changelog


# ---------------------------------------------------------------------------
# Production-readiness gate (direction item B)
# ---------------------------------------------------------------------------

def production_readiness(theme_data: dict, theme_file: str, store, taxonomy) -> dict:
    """Hard gate a theme must pass before it may be treated as production-ready.

    Checks mirror the audit's FAIL rules plus worthiness and anchor-mix floors;
    thresholds are intentionally NOT loosened to turn fails green.
    """
    report = audit_theme(theme_data, str(theme_file), store, taxonomy)
    counts = report.to_dict()["counts"]
    total_words = max(report.word_count, 1)

    judged = 0
    worthiness_ok = 0
    for puzzle in theme_data.get("puzzles") or []:
        for word in puzzle.get("words") or []:
            record = store.get(clean_surface(word))
            if record is None:
                continue  # unknown to the store yet: future curation, not a fault
            judged += 1
            score = assess_quality(record)
            if score.worthiness in (PuzzleWorthiness.PREFERRED,
                                    PuzzleWorthiness.ACCEPTABLE,
                                    PuzzleWorthiness.SPECIALIZED):
                worthiness_ok += 1
    worthy_share = (worthiness_ok / judged) if judged else 1.0

    on_topicish = counts.get("on_topic", 0) + counts.get("related", 0) \
        + counts.get("likely_ok", 0)
    checks = {
        "verdict_pass_or_notes": report.verdict in (VERDICT_PASS, VERDICT_PASS_WITH_NOTES),
        "no_trademark_flags": counts.get("flagged", 0) == 0,
        "off_topic_within_tolerance": counts.get("off_topic", 0) <= max(2, total_words // 20),
        "worthiness_share": round(worthy_share, 4),
        "worthiness_at_least_90pct": worthy_share >= 0.90,
        "anchor_depth": on_topicish,
        "anchor_depth_sufficient": on_topicish >= min(STANDARD_BOOK_WORDS, total_words // 2),
        "no_malformed_entries": all(
            isinstance(pz, dict) and pz.get("name") and pz.get("words")
            for pz in (theme_data.get("puzzles") or [])),
        "duplicates_within_limits": len(report.duplicate_pairs) <= 2,
    }
    ready = all(v for k, v in checks.items() if isinstance(v, bool)) and \
        checks["worthiness_at_least_90pct"]
    return {"ready": ready, "verdict": report.verdict, "checks": checks}


__all__ = [
    "AUTO_APPLY_MAX_OFF_TOPIC_RATIO",
    "CAUSE_DUPLICATE", "CAUSE_OFF_TOPIC", "CAUSE_SAFETY", "CAUSE_TRADEMARK",
    "CAUSE_WEAK", "ThemeRepairPlan", "WordReplacement", "apply_plan",
    "build_inventory", "candidate_pool", "cause_for", "content_signature",
    "plan_theme_repairs", "production_readiness", "recommend_disposition",
]
