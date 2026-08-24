"""Apply engine: the ONLY component that writes derived vocabulary data.

Safety model (mission §24-26):
  1. DRY RUN IS THE DEFAULT - nothing is written unless explicitly allowed.
  2. Every write is preceded by a timestamped snapshot of the target files,
     including SHA-256 checksums and a readback verification.
  3. Writes are atomic (temp file + os.replace).
  4. Rollback restores a verified snapshot in one step.

The engine emits `approved_topic_links.json` - a curated source consumed by
`build_master_word_bank.py` - so human decisions survive bank regeneration.
The master bank itself is NOT modified by this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .records import APPROVED, REJECTED, TRUSTED, EvidenceItem, SIGNAL_HUMAN_DECISION
from .store import APPROVED_LINKS_FILENAME

SNAPSHOTS_DIRNAME = "snapshots"
LINKS_SCHEMA_VERSION = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class ApplyResult:
    dry_run: bool
    output_path: str = ""
    snapshot_dir: str = ""
    link_count: int = 0
    approved_words: int = 0
    rejected_entries: int = 0
    validated: bool = False
    errors: list[str] = field(default_factory=list)
    would_write: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "output_path": self.output_path,
            "snapshot_dir": self.snapshot_dir,
            "link_count": self.link_count,
            "approved_words": self.approved_words,
            "rejected_entries": self.rejected_entries,
            "validated": self.validated,
            "errors": list(self.errors),
            "would_write": list(self.would_write),
        }


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def collect_decisions(store) -> dict[str, dict[str, dict]]:
    """Human-approved / human-rejected pairs keyed word -> topic -> info."""
    links: dict[str, dict[str, dict]] = {}
    for norm, record in sorted(store.records.items()):
        for link in record.topics:
            if link.status not in (APPROVED, REJECTED):
                continue
            human = [e for e in link.evidence if e.signal == SIGNAL_HUMAN_DECISION]
            if not human and link.status == REJECTED:
                continue  # rejections must be human-sourced to block future runs
            note = human[0].detail if human else ""
            links.setdefault(norm, {})[link.topic_id] = {
                "status": link.status,
                "confidence": round(link.confidence, 1),
                "note": note,
                "decided_at": link.updated_at,
            }
    return links


def plan_apply(store) -> dict:
    decisions = collect_decisions(store)
    return {
        "words_with_decisions": len(decisions),
        "approved_pairs": sum(
            1 for topics in decisions.values()
            for info in topics.values() if info["status"] == APPROVED),
        "rejected_pairs": sum(
            1 for topics in decisions.values()
            for info in topics.values() if info["status"] == REJECTED),
    }


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

def snapshot_files(file_paths, state_dir, label: str = "pre-apply") -> Path:
    """Copy files into snapshots/<ts>-<label>/ with a verified manifest."""
    file_paths = [Path(p) for p in file_paths if Path(p).exists()]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    snap_dir = Path(state_dir) / SNAPSHOTS_DIRNAME / f"{ts}-{label}"
    snap_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"created_at": datetime.now().isoformat(timespec="seconds"),
                "label": label, "files": {}}
    for src in file_paths:
        dest = snap_dir / src.name
        shutil.copy2(src, dest)
        if _sha256(dest) != _sha256(src):  # readback validation
            raise IOError(f"Snapshot readback mismatch for {src}")
        manifest["files"][src.name] = {
            "original_path": str(src),
            "sha256": _sha256(src),
            "size": src.stat().st_size,
        }
    manifest_path = snap_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1)
    return snap_dir


def rollback(snapshot_dir) -> list[str]:
    """Restore every file recorded in a snapshot's manifest."""
    snap_dir = Path(snapshot_dir)
    manifest_path = snap_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No snapshot manifest at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    restored = []
    for name, info in sorted(manifest["files"].items()):
        backup = snap_dir / name
        if not backup.exists() or _sha256(backup) != info["sha256"]:
            raise IOError(f"Snapshot integrity failure for {name}; aborting restore")
        target = Path(info["original_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)
        if _sha256(target) != info["sha256"]:
            raise IOError(f"Rollback readback mismatch for {target}")
        restored.append(str(target))
    return restored


def latest_snapshot(state_dir) -> Path | None:
    snaps = sorted((Path(state_dir) / SNAPSHOTS_DIRNAME).glob("*")) \
        if (Path(state_dir) / SNAPSHOTS_DIRNAME).exists() else []
    return snaps[-1] if snaps else None


# ---------------------------------------------------------------------------
# Applying curated links
# ---------------------------------------------------------------------------

def apply_approved_links(store, project_root=".", state_dir=None,
                         dry_run: bool = True, taxonomy=None) -> ApplyResult:
    """Write the curated approved-links source consumed by the bank builder.

    When a taxonomy is supplied, the payload also carries a
    ``topic_raw_names`` map (canonical id -> master-bank raw key list) so
    ``build_master_word_bank.py`` can merge decisions into its packs without
    importing this package.
    """
    root = Path(project_root)
    state_dir = Path(state_dir) if state_dir else root / "word_banks" / "word_intelligence"
    decisions = collect_decisions(store)
    result = ApplyResult(dry_run=dry_run)

    topic_raw_names: dict[str, list[str]] = {}
    if taxonomy is not None:
        wanted = {tid for topics in decisions.values() for tid in topics}
        for tid in sorted(wanted):
            topic = taxonomy.topics.get(tid)
            if topic is not None and getattr(topic, "aliases", None):
                topic_raw_names[tid] = sorted(topic.aliases)

    payload = {
        "schema_version": LINKS_SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "description": ("Human-curated topic associations. Consumed as a "
                        "source by build_master_word_bank.py; safe to regenerate."),
        "classifier_version": "n/a",
        "links": decisions,
        "topic_raw_names": topic_raw_names,
    }
    result.link_count = sum(len(t) for t in decisions.values())
    result.approved_words = sum(
        1 for topics in decisions.values()
        if any(i["status"] == APPROVED for i in topics.values()))
    result.rejected_entries = sum(
        1 for topics in decisions.values()
        for info in topics.values() if info["status"] == REJECTED)

    out_path = state_dir / APPROVED_LINKS_FILENAME
    result.output_path = str(out_path)
    if dry_run:
        result.would_write.append(str(out_path))
        return result

    # Snapshot any file we are about to touch.
    snap = snapshot_files([out_path], state_dir, label="pre-links")
    result.snapshot_dir = str(snap)

    serialized = json.dumps(payload, indent=1, ensure_ascii=False)
    fd, tmp_name = tempfile.mkstemp(dir=str(state_dir), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(serialized)
    os.replace(tmp_name, out_path)

    # Post-write validation: parse-back + count check.
    try:
        with open(out_path, encoding="utf-8-sig") as handle:
            readback = json.load(handle)
        if len(readback.get("links", {})) != len(decisions):
            raise ValueError("Link count mismatch after write")
        result.validated = True
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result.errors.append(f"Validation failed: {exc}")
        rollback(snap)
        result.errors.append("Rolled back to snapshot")
    return result


def load_approved_links(project_root="."):
    """Read the curated source (returns {} when absent - never an error)."""
    path = Path(project_root) / "word_banks" / "word_intelligence" / APPROVED_LINKS_FILENAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
