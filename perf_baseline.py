"""Read-only performance baseline for the Word Base phase.

Measures the operations PRODUCT_DIRECTION.md names as the baseline set:
taxonomy load, word-store load, single-record lookups, candidate index
build, one mid-size theme audit, and a full-library inventory. Writes a
JSON record under out/word_intelligence_reports/. Modifies nothing else.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cleanup_theme_library import REPORT_DIR, write_json_atomic
from word_intelligence.pipeline import load_taxonomy, load_or_build_store
from word_intelligence.repair import build_inventory, build_topic_member_index


def timed(label, fn, repeat=1):
    best = None
    result = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        result = fn()
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
    return {"label": label, "seconds": round(best, 3)}, result


def main() -> None:
    rows = []

    row, taxonomy = timed("load_taxonomy", lambda: load_taxonomy(ROOT))
    rows.append(row)

    def _store():
        return load_or_build_store(taxonomy, project_root=ROOT)[0]
    row, store = timed("load_or_build_store (cached)", _store)
    rows.append(row)

    # Single-record lookup: the hot path for every audit/classifier call.
    probe = next(iter(store.records)) if store.records else "TROWEL"
    n = 20_000
    t0 = time.perf_counter()
    for _ in range(n):
        store.get(probe)
    per_lookup_ms = (time.perf_counter() - t0) / n * 1000
    rows.append({"label": f"store.get x{n}", "seconds":
                 round(time.perf_counter() - t0, 3),
                 "per_call_ms": round(per_lookup_ms, 5)})

    row, _index = timed("build_topic_member_index", 
                        lambda: build_topic_member_index(store, taxonomy))
    rows.append(row)

    zion = ROOT / "themes" / "national_parks_02_zion.json"
    if not zion.exists():
        zion = next(ROOT.glob("themes/*.json"))
    row, _ = timed(f"audit_theme_file ({zion.name})",
                   lambda: __import__(
                       "word_intelligence.theme_audit",
                       fromlist=["audit_theme_file"]).audit_theme_file(
                           zion, store, taxonomy))
    rows.append(row)

    row, inventory = timed("build_inventory (full library)",
                           lambda: build_inventory(
                               ROOT / "themes", store, taxonomy))
    rows.append(row)
    verdicts = inventory["verdict_counts"]

    total = round(sum(r["seconds"] for r in rows), 3)
    payload = {
        "generated_at": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "python": sys.version.split()[0],
        "measurements": rows,
        "total_seconds": total,
        "inventory_verdict_counts": verdicts,
        "notes": [
            "Best-of-N wall times where repeat > 1; cold caches otherwise.",
            f"Library: {len(inventory['themes'])} themes.",
            "Read-only except this report file.",
        ],
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORT_DIR / f"perf_baseline-{payload['generated_at']}.json"
    write_json_atomic(target, payload)
    print(f"Wrote {target}")
    for r in rows:
        extra = f"  ({r['per_call_ms']} ms/call)" if "per_call_ms" in r else ""
        print(f"  {r['label']:<42} {r['seconds']:>8.3f}s{extra}")
    print(f"  {'TOTAL':<42} {total:>8.3f}s")


if __name__ == "__main__":
    main()
