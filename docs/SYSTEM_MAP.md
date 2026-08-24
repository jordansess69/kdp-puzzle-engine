# SYSTEM MAP — KDP Puzzle Engine / Word Search Creator

Living map of what the application actually is today: the three production
chains, which features are authoritative vs. legacy, and where each piece of
publishing state lives. Generated during the stabilization pass; update when
major modules change.

## 1. Production chains

### Chain A — Word Search interiors (GUI-driven)
`launch_word_search_creator.py` → `word_search_creator.py` (~6.7k-line Tkinter
app: assistant home, theme builder, dialogs) → engines `wordsearch.py`
(ReportLab PDF interior), `cover.py` (300 DPI front cover), `wrap_cover.py`
(full-wrap cover + spine math) → output under `out/`.
Support: `font_utils.py`, `theme_health.py` (readiness cache), `openclipart_service.py`
(CC0 art, network, used on demand).

### Chain B — Puzzle Book Studio
`puzzle_book_studio.py`: standalone studio for Sudoku (`sudoku.py`, MRV
uniqueness solver), cryptograms, word scramble + trivia, mixed brain games.

### Chain C — Publishing pipeline (authoritative catalog)
```
themes/*.json ──sync──▶ publishing/manager.PublishingService
                          │  metadata_service.build_metadata
                          │  master_package.build_master_package
                          ▼
                    data/books.db  (THE one authoritative catalog)
                          │  readiness.marketplace_rows / database guards
                          ▼
                    publishing/ui.py  Publishing Manager Hub (Tkinter)
                          │
        ┌─────────────────┼──────────────────────┐
        ▼                 ▼                      ▼
 integrations/etsy   integrations/amazon    manual portals
 (API: draft-only    (kdp_export.py:        (Record listing /
  automation)         local handoff zip)     update status)
```

### Universal Publishing layer (`integrations/`)
Canonical, channel-neutral models consumed by Chain C:
`product.MasterProduct` (+ factory), `publication.PublicationRecord`,
`validation`, `results.PublishResult`, `exporting.FolderExportIntegration`,
`foundation.UniversalPublishingIntegration` (contract), `registry`
(explicit factories + discovery metadata), `errors` (redaction).
Adapters: `integrations/etsy/` (connection/auth/session/draft_service/drafts/mapper),
`integrations/amazon/kdp_export.py`. See
`docs/UNIVERSAL_PUBLISHING_FOUNDATION.md`.

## 2. Feature matrix

| Area | Module(s) | Status |
|---|---|---|
| Word search GUI + engines | word_search_creator.py, wordsearch.py | **ACTIVE** |
| Sudoku / studio puzzles | puzzle_book_studio.py, sudoku.py | **ACTIVE** |
| Front cover / full wrap | cover.py, wrap_cover.py | **ACTIVE** |
| Print compliance checks | preflight.py | **ACTIVE** |
| Catalog & theme validation | project_checks.py | **ACTIVE** |
| Publishing Hub + catalog | publishing/* | **ACTIVE** |
| Etsy draft automation | integrations/etsy/* | **ACTIVE** (draft-only by design) |
| Amazon KDP export handoff | integrations/amazon/kdp_export.py | **ACTIVE** (local files only) |
| Ingram/Lulu/BookVault/B&N/website channels | registry rows | **PLANNED** (manual workflows today) |
| CDP browser tools | publish_tools/* | **CONDITIONAL** — defensive, DOMs change, never auto-run |
| One-shot series builders | build_*.py (root), rebuild_*, refresh_* | **LEGACY-BATCH** — historical production scripts; kept for provenance/reproducibility, not part of daily pipeline |
| Vocabulary/data audits | audit_*, classify_*, complete_theme_library.py, sync_master_topic_links.py, set_theme_difficulty.py, verify_signature_margins.py, run_full_product_audit.py | **LEGACY-MAINTENANCE** — run manually when word banks change |
| Master word bank data | build_master_word_bank.py, build_education_word_bands.py, master_library_expansions.py, vocabulary_series_data.py, word_banks/ | **SUPPORT-DATA** |
| integrations placeholders | integrations sub-packages with only `__init__.py` | **PLACEHOLDER** |

## 3. State: single sources of truth

| State | Authoritative store | Notes |
|---|---|---|
| Book identity/metadata | `data/books.db` books.metadata_json | locked fields survive re-sync |
| Marketplace status/ASIN/link | `books.db` marketplace_status | human-owned; guarded by PROTECTED_STATUSES |
| Automation state/events | `books.db` integration_state/integration_log | machine-owned; never touches status |
| Theme readiness verdicts | `data/theme_readiness_cache.json` | content-check cache keyed by file hash |
| Export packages | `out/exports/<key>/<product-id>/` | derived artifacts, safe to delete |
| Prepared folders | `<package>/<kdp\|etsy\|...>/` | derived artifacts |
| Credentials | Windows Credential Manager (+env fallback) | NEVER in DB/files/models/logs |
| release_catalog.json | legacy sync input for Theme Builder flows | superseded as state by books.db; still read for package paths |

**Legacy-vs-authoritative analysis:** early prototypes tracked publication
progress in scattered JSON files (release_catalog.json,
production_history.json, launch_batch_tracker.json). All of that state is now
authoritative in `data/books.db`; those files persist only because older
build scripts write them. The My Books Dashboard and Publication Pipeline UIs
in `word_search_creator.py` are views over the same DB via PublishingService —
not separate stores. Do not add new JSON state files.

## 4. Invariants worth defending

1. One catalog DB; guarded transitions; Uploaded/Published immutable from below.
2. Draft-only Etsy automation; the app never activates a listing.
3. Canonical model carries no credentials; every outbound string is redacted.
4. Deterministic puzzle generation under seed; unique-solution Sudoku.
5. 8.5×11 geometry, 300 DPI, spine/barcode math untouched without spec verification.
6. Export/prepare actions only ever write local files.
