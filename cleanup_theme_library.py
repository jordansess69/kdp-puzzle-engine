"""Theme library cleanup driver.

Production-quality enforcement over the whole theme library using the Word
Intelligence layer. Safety model mirrors the apply engine: inventory and
plans never modify anything; application snapshots every target file first
(sha256 manifest), writes atomically, validates the result by parse-back,
and restores the snapshot automatically if anything fails.

Subcommands:
  inventory    Canonical failure inventory for every theme (JSON report).
  plan         Dry-run repair plans for repair / repair_partial themes.
               Unresolved words are routed to the human review queue.
  apply        Dry-run report by default: shows tier counts and exactly
                which plans would run. --write performs the application.
                ONLY auto-tier plans (small share, very-high confidence,
                zero conflicts) run without approval; review and
                approval_required tiers require --approve-plan NAME per
                plan; blocked plans never apply. Every applied file is
                snapshotted first with rollback on any failure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from project_checks import run_project_check  # noqa: E402
from word_intelligence.apply_engine import rollback, snapshot_files  # noqa: E402
from word_intelligence.pipeline import load_taxonomy, load_or_build_store  # noqa: E402
from word_intelligence.repair import (  # noqa: E402
    build_inventory,
    plan_theme_repairs,
)
from word_intelligence.reports import DEFAULT_REPORT_DIR  # noqa: E402

STATE_DIR = ROOT / "word_banks" / "word_intelligence"
PLANS_DIR = STATE_DIR / "repair_plans"
REPORT_DIR = ROOT / DEFAULT_REPORT_DIR


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _load_intelligence():
    taxonomy = load_taxonomy(ROOT)
    store, _ = load_or_build_store(taxonomy, project_root=ROOT)
    return store, taxonomy


def _plan_file_name(theme_rel_path: str) -> str:
    """Collision-proof plan name: stems can repeat across subfolders
    (e.g. two different Arizona_100_... files), so encode the whole
    relative path instead of just the stem."""
    return Path(theme_rel_path).with_suffix(".plan.json").as_posix().replace(
        "/", "__")


def write_json_atomic(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(serialized)
    os.replace(tmp_name, path)


def cmd_inventory(_args) -> None:
    store, taxonomy = _load_intelligence()
    print("Auditing the full library…")
    inventory = build_inventory(ROOT / "themes", store, taxonomy)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORT_DIR / f"theme_failure_inventory-{_stamp()}.json"
    write_json_atomic(target, inventory)
    counts = inventory["verdict_counts"]
    print(f"Wrote {target}")
    print(f"Verdicts: {counts}")
    print(f"Cause totals: {inventory['finding_cause_totals']}")
    dispositions = {}
    for entry in inventory["themes"]:
        dispositions[entry["disposition"]] = \
            dispositions.get(entry["disposition"], 0) + 1
    print(f"Dispositions: {dict(sorted(dispositions.items()))}")


def _latest_inventory() -> Path:
    files = sorted(REPORT_DIR.glob("theme_failure_inventory-*.json"))
    if not files:
        raise SystemExit("No inventory found - run `inventory` first.")
    return files[-1]


def cmd_plan(args) -> None:
    store, taxonomy = _load_intelligence()
    inventory = json.loads(_latest_inventory().read_text(encoding="utf-8-sig"))

    wanted = {d.strip() for d in args.disposition.split(",") if d.strip()}
    member_index = None
    planned = skipped = 0
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    # Plans are fully reproducible from the current inventory + library:
    # clear the directory so stale plans (old names, removed themes) can
    # never be picked up by apply.
    for old in PLANS_DIR.glob("*.plan.json"):
        old.unlink()

    from word_intelligence.repair import build_topic_member_index
    from word_intelligence.review import seed_review_queue
    queue = seed_review_queue(store)
    gap_total = 0

    for entry in inventory["themes"]:
        if entry["disposition"] not in wanted:
            continue
        if not entry.get("targets"):
            skipped += 1
            continue
        path = ROOT / "themes" / entry["file"]
        if not path.exists():
            skipped += 1
            continue
        if member_index is None:
            print("Building candidate index (one-time scan)…")
            member_index = build_topic_member_index(store, taxonomy)
        theme_data = json.loads(path.read_text(encoding="utf-8-sig"))
        plan = plan_theme_repairs(theme_data, path, store, taxonomy,
                                  member_index=member_index)
        plan_dict = plan.to_dict()
        # Store the library-relative path so apply can resolve the target
        # without guessing folders.
        plan_dict["theme_file"] = entry["file"]
        plan_dict["disposition"] = entry["disposition"]
        plan_dict["generated_at"] = _stamp()
        write_json_atomic(PLANS_DIR / _plan_file_name(entry["file"]),
                          plan_dict)
        planned += 1
        # Candidate gaps stay inside their plan JSON ("unresolved") - the
        # shared review queue is for human link decisions, not a dump of
        # thousands of "no candidate available" rows.
        gap_total += len(plan.unresolved)

    queue.save(STATE_DIR)
    print(f"Plans written: {planned} (skipped {skipped}) -> {PLANS_DIR}")
    print(f"Candidate gaps recorded inside plans (unresolved): {gap_total}")


def cmd_apply(args) -> None:
    """Apply repair plans. Dry-run report by default; --write mutates."""
    approved = {a.strip() for a in (args.approve_plan or "").split(",")
                if a.strip()}
    plan_files = sorted(PLANS_DIR.glob("*.plan.json"))
    tier_counts: dict[str, int] = {}
    selected: list[tuple[Path, dict]] = []
    pending_approval = blocked = 0

    # Pass 1 - classify and select without touching anything.
    for plan_path in plan_files:
        plan_dict = json.loads(plan_path.read_text(encoding="utf-8-sig"))
        tier = plan_dict.get("tier") or (
            "auto" if plan_dict.get("auto_applicable") else "review")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        # Only auto-tier plans may run without being named explicitly.
        # Review and approval_required tiers require their exact plan stem
        # in --approve-plan; blocked plans never apply.
        if tier == "blocked":
            blocked += 1
            continue
        if tier != "auto" and plan_path.stem not in approved:
            pending_approval += 1
            continue
        if not (ROOT / "themes" / plan_dict["theme_file"]).exists():
            blocked += 1
            continue
        selected.append((plan_path, plan_dict))

    print(f"Tiers: {dict(sorted(tier_counts.items()))}")
    if not args.write:
        print(f"DRY-RUN: {len(selected)} plan(s) would be applied "
              f"({pending_approval} awaiting explicit --approve-plan, "
              f"{blocked} blocked). Nothing has been modified.")
        for plan_path, plan_dict in selected[:15]:
            print(f"   would apply {plan_path.name} "
                  f"(tier={plan_dict.get('tier')}, "
                  f"{len(plan_dict['replacements'])} changes, share="
                  f"{plan_dict.get('replacement_share', 0):.1%})")
        if len(selected) > 15:
            print(f"   … and {len(selected) - 15} more")
        return

    # Pass 2 - actual application: snapshot -> atomic write -> parse-back
    # -> rollback on any failure.
    applied = 0
    changelog_all = []
    for plan_path, plan_dict in selected:
        if plan_dict.get("tier") not in ("auto", None):
            print(f"APPROVED-APPLY {plan_path.stem} "
                  f"(tier={plan_dict.get('tier')}, share="
                  f"{plan_dict.get('replacement_share', 0):.0%})")
        theme_path = ROOT / "themes" / plan_dict["theme_file"]
        original_raw = theme_path.read_text(encoding="utf-8-sig")
        theme_data = json.loads(original_raw)

        from word_intelligence.repair import (  # noqa: E402
            ThemeRepairPlan,
            WordReplacement,
            apply_plan,
        )
        replacements = [WordReplacement(**{
            **rep, "alternates": list(rep.get("alternates", []))})
            for rep in plan_dict["replacements"]]
        plan = ThemeRepairPlan(
            theme_file=plan_dict["theme_file"],
            title=plan_dict.get("title", ""),
            replacements=replacements)
        try:
            new_data, changelog = apply_plan(theme_data, plan)
        except ValueError as exc:
            print(f"REFUSED {theme_path.name}: {exc}")
            blocked += 1
            continue
        if not changelog:
            continue

        snap = snapshot_files([theme_path], STATE_DIR, label="pre-repair")
        try:
            write_json_atomic(theme_path, new_data)
            json.loads(theme_path.read_text(encoding="utf-8-sig"))  # parse-back
        except Exception as exc:
            rollback(snap)
            print(f"FAILED {theme_path.name}: {exc} - restored backup.")
            blocked += 1
            continue
        applied += 1
        changelog_all.append({"theme": theme_path.name,
                              "snapshot": str(snap),
                              "changes": changelog})
        print(f"Applied {len(changelog)} change(s) to {theme_path.name}")

    stamp = _stamp()
    if changelog_all:
        write_json_atomic(REPORT_DIR / f"repair_changelog-{stamp}.json",
                          {"applied_themes": applied, "blocked": blocked,
                           "tier_counts": tier_counts,
                           "batches": changelog_all})
    print(f"Batches applied: {applied}; blocked: {blocked}; "
          f"awaiting explicit approval: {pending_approval}")


def cmd_status(_args) -> None:
    problems, notes = run_project_check(ROOT / "themes")
    print(f"project_check problems: {len(problems)}")
    for note in notes[:6]:
        print(f"  {note}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inventory")
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--disposition", default="repair,repair_partial")
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument(
        "--approve-plan", default="",
        help="Comma-separated plan stems the human explicitly approves to "
             "apply. Required for any non-auto tier; blocked plans never "
             "apply.")
    apply_parser.add_argument(
        "--write", action="store_true",
        help="Actually modify theme files. Without this flag the command "
             "only reports what it would do (dry-run is the default).")
    sub.add_parser("status")
    args = parser.parse_args()
    {"inventory": cmd_inventory, "plan": cmd_plan,
     "apply": cmd_apply, "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    main()
