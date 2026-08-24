"""Report generation: JSON/TXT/CSV exports for the intelligence layer.

Reports land in out/word_intelligence_reports/ and never modify source
data.  Every report is plain-file based so it can be attached to a
publishing checklist or reviewed offline.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from .analysis import (
    coverage_summary,
    duplicate_topic_warnings,
    exclusive_words_preview,
    topic_health,
)
from .apply_engine import plan_apply
from .records import CLASSIFIER_VERSION

DEFAULT_REPORT_DIR = Path("out") / "word_intelligence_reports"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_report_dir(report_dir=DEFAULT_REPORT_DIR) -> Path:
    path = Path(report_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(name: str, payload: dict, report_dir=DEFAULT_REPORT_DIR) -> Path:
    path = ensure_report_dir(report_dir) / f"{name}-{_stamp()}.json"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, default=str)
    return path


def write_text(name: str, lines, report_dir=DEFAULT_REPORT_DIR) -> Path:
    path = ensure_report_dir(report_dir) / f"{name}-{_stamp()}.txt"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def write_review_queue_csv(queue, report_dir=DEFAULT_REPORT_DIR) -> Path:
    path = ensure_report_dir(report_dir) / f"review-queue-{_stamp()}.csv"
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", "word", "topic_id", "kind", "confidence",
                         "reason", "status"])
        for item in queue.open_items():
            writer.writerow([item.item_id, item.word, item.topic_id, item.kind,
                             f"{item.confidence:.0f}", item.reason, item.status])
    return path


def topic_health_lines(rows) -> list[str]:
    lines = [
        f"{'GRADE':<5} {'WORDS':>5}  {'TOPIC':<38} {'FAMILY'}",
        "-" * 90,
    ]
    for row in rows:
        lines.append(
            f"{row['grade']:<5} {row['usable_words']:>5}  "
            f"{row['display_name'][:38]:<38} {row['family']}")
    return lines


def full_intelligence_report(store, taxonomy, project_root=".",
                             report_dir=DEFAULT_REPORT_DIR) -> dict:
    """One-click snapshot of the whole subsystem; returns written paths."""
    written = {}
    coverage = coverage_summary(store)
    health = topic_health(store, taxonomy)

    written["coverage"] = write_json(
        "coverage", {"classifier_version": CLASSIFIER_VERSION,
                     "generated_at": datetime.now().isoformat(timespec="seconds"),
                     **coverage}, report_dir)
    written["topic_health"] = write_json(
        "topic-health",
        {"rows": health,
         "duplicates": duplicate_topic_warnings(taxonomy)}, report_dir)
    written["plan"] = write_json("apply-plan", plan_apply(store), report_dir)
    written["topic_health_txt"] = write_text(
        "topic-health", topic_health_lines(health), report_dir)
    return {"paths": written, "coverage": coverage, "health": health}


def unclassified_preview(store, limit: int = 200) -> list[str]:
    """Words with no confirmed association - classification targets."""
    out = []
    for norm, record in sorted(store.records.items()):
        if record.is_unclassified():
            out.append(norm)
            if len(out) >= limit:
                break
    return out


def bad_link_candidates(store, max_confidence: float = 60.0,
                        limit: int = 200) -> list[dict]:
    """Proposals below the auto-link floor - audit fodder."""
    out = []
    for norm, record in sorted(store.records.items()):
        for link in record.topics:
            if link.status == "proposed" and link.confidence < max_confidence:
                out.append({"word": norm, "topic": link.topic_id,
                            "confidence": link.confidence})
                break
        if len(out) >= limit:
            break
    return out
