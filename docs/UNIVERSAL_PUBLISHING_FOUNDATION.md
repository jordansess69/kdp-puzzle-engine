# Universal Publishing Foundation

One publishing system. The SQLite catalog (`publishing/database.py`) stays the
single authoritative store. This foundation adds a marketplace-neutral
*domain layer* on top of it so every future channel plugs into the same shape
instead of growing its own workflow.

```
Puzzle Project / Catalog Record        (authoritative: books.db + metadata JSON)
        |  MasterProductFactory.from_book_record()      integrations/factory.py
        v
MasterProduct                          integrations/product.py   (in-memory only)
        |
ProductArtifact collection             (generic files: interior, cover, digital PDF,
        |                               thumbnails, previews - no marketplace names)
        v
Marketplace Adapter / Mapper           integrations/foundation.py contract
        |                              integrations/etsy/mapper.py  (Etsy reference)
        v
Remote Listing  OR  Export Package     API mode          exports/<key>/<product-id>/
        |
        v
PublicationRecord / existing status    integrations/publication.py - a VIEW over
                                       marketplace_status (+ integration columns)
```

## What each module owns

| Module | Responsibility |
|---|---|
| `integrations/product.py` | `MasterProduct`, `ProductArtifact`, `ArtifactPurpose`, canonical validation. Neutral field names only (`tags`, `keywords`, `price`). Incomplete products are valid. |
| `integrations/validation.py` | `ValidationSeverity` / `ValidationIssue` / `ValidationResult`. Valid = zero ERRORs; warnings/info never block. |
| `integrations/results.py` | `PublishResult` for every operation answer. Messages pre-redacted via `redact_text`; repr never includes `recovery`. |
| `integrations/foundation.py` | `UniversalPublishingIntegration`: opt-in full contract. Unsupported operations raise `UnsupportedCapabilityError` - never silent no-ops. |
| `integrations/exporting.py` | Export-only support: structured `exports/<key>/<id>/` bundles with `LISTING_KIT.txt` + `manifest.json` + copied files, plus the reference `FolderExportIntegration` (no network, no credentials). |
| `integrations/factory.py` | Pure translation from catalog book records to `MasterProduct`. Never regenerates PDFs/covers/puzzles. Marketplace-named source fields (`etsy_tags`) appear ONLY here and in mappers. |
| `integrations/publication.py` | `PublicationRecord` view over existing rows. No new tables, no migration, no dual writes. `published_at` exists only when a human confirmed "Published" - "Uploaded" never counts. |
| `integrations/registry.py` | Explicit `_FACTORIES` registration + discovery metadata (`integration_metadata()`) covering channels that have no adapter yet ("planned"/export-only). No dynamic imports. |

## Phase A / Etsy compatibility guarantees

- `PublishingIntegration` and `EtsyIntegration` keep their exact public shape.
  Security tests still assert they expose **no** write-style method names.
- `CapabilityFlags` grew additively: all original fields, order and defaults
  unchanged; new flags default False; `has_any_write_capability` now covers
  the new remote-write flags too.
- `registry.available_keys()` is still exactly `("etsy",)` and
  `get_integration("amazon")` is still None.
- The Etsy mapper reuses `sanitize_title`/`sanitize_tags` from
  `draft_service` and tests prove byte-identical `createDraftListing`
  payloads versus `build_draft_fields`.
- Etsy remains the only active API integration. Draft-only semantics
  (never activate/publish/delete) are unchanged.

## HOW TO ADD A NEW INTEGRATION

Example: a future Gumroad adapter at `integrations/gumroad/`.

1. **Contract**: subclass `UniversalPublishingIntegration`
   (`integrations.foundation`) - not `PublishingIntegration`, which stays the
   minimal Phase A surface. Implement `is_configured()` and
   `test_connection()`; override only the operations you truly support
   (`create_draft`, `publish`, `update`, `get_status`,
   `validate_product`, `export_package`).
2. **Capabilities**: advertise truthfully with `CapabilityFlags(...)` -
   flags are authoritative; anything not advertised must raise
   `UnsupportedCapabilityError` (the base defaults already do).
3. **Mapping**: put ALL platform rules in your package's mapper
   (e.g. `integrations/gumroad/mapper.py`): title length, tag count, category
   ids, allowed MIME types, image limits, pricing format, required fields.
   Consume `MasterProduct`; produce your platform request object. Never push
   platform names back into the canonical model.
4. **Validation**: channel rules = `ValidationIssue`s from your mapper's
   `validate_product`. Canonical checks come free via
   `integrations.product.validate_canonical`; aggregate both with
   `ValidationResult.aggregate` when reporting.
5. **Results**: return `PublishResult.ok(...)` / `PublishResult.failure(...)`
   with plain-English messages (they are auto-redacted). Put non-secret
   recovery hints only (ids, folder paths) in `recovery`.
6. **Registry**: one explicit entry -
   `registry.register_integration("gumroad", create_gumroad_integration)` -
   inside your package's registration helper called from
   `registry._register_builtin_integrations()`. Plus one discovery row in
   `_INTEGRATION_INFO`. Nothing else in the app changes.
7. **Export-only platforms** (KDP/IngramSpark today): skip auth entirely;
   subclass or reuse `FolderExportIntegration`, override
   `validate_product`, and let `write_export_bundle` produce
   `exports/<key>/<product-id>/`. `is_configured()` returns True and
   `test_connection()` explains the offline mode.
8. **Secrets**: credentials never touch MasterProduct, results, logs or the
   catalog DB. Store them like Etsy does (Windows Credential Manager via
   `integrations.wincred`, env-var priority), inject them through a provider
   protocol, and route every HTTP call through `integrations.http.HttpClient`
   (HTTPS-only, explicit timeouts, bounded retries, redacted errors).
9. **Publication state**: after any real change, persist through the EXISTING
   guarded methods (`transition_status`, `set_integration_state`,
   `record_integration_event`) and read back through `PublicationRecord`.
   Never write a second store; never move a human-confirmed
   Uploaded/Published record backwards.

## Testing rules

Everything above is covered by offline tests:
`tests/test_universal_publishing_foundation.py` and
`tests/test_universal_factory_and_mapper.py`. New adapters must ship the same
style: fake transports, tmp_path fixtures, no network, no real credentials.
