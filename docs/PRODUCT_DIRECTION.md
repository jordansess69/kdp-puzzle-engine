# Product Direction — Create Once → Package Once → Publish Everywhere

> Authoritative long-term direction adopted 2026-08-23. Supersedes any older
> assumptions about scope. The **word database is the current phase** and must
> not be compromised or rushed for publishing work.

## Vision

The application evolves beyond a Word Search Creator into a puzzle product
studio with a multi-channel publishing layer:

```
WORD DATABASE → TOPIC/NICHE → PUZZLE PROJECT → PUZZLE GENERATION
→ BOOK/PRODUCT GENERATION → MASTER PRODUCT → PRODUCT ASSETS
→ MARKETPLACE-SPECIFIC LISTINGS → PUBLISH/EXPORT → TRACK STATUS
```

The core remains: **high-quality puzzle products from a large, curated,
topic-aware word database.** Publishing is an additive layer on top.

## Domain Separation (non-negotiable)

```
WORD DATABASE → PUZZLE DOMAIN → PRODUCT DOMAIN → PUBLISHING DOMAIN
→ INTEGRATIONS → EXTERNAL SERVICES
```

- Puzzle generator never knows how Etsy works.
- Word database never knows how Shopify works.
- `MasterProduct` never knows Lulu API details.
- GUI never contains marketplace HTTP requests.
- Marketplace rules (title limits, tags, categories) live ONLY in that
  marketplace's adapter/mapper, never in shared models.

## Canonical Concepts

| Concept | Meaning |
| --- | --- |
| MasterProduct | WHAT we sell (marketplace-neutral). Existing `integrations/product.py` model; extend, never duplicate. Neutral fields only (`keywords`, never `etsy_tags`). |
| Edition | WHICH version we sell (digital PDF / paperback / hardcover / classroom pack / bundle). Lightweight variant of one conceptual product. |
| ProductArtifact | Generated files (PRINT_INTERIOR, PRINT_COVER, DIGITAL_PDF, EPUB, THUMBNAIL, LISTING_IMAGE, MOCKUP, PREVIEW, SOURCE_ARCHIVE, METADATA_EXPORT) with path/purpose/MIME/checksum/dimensions/order. Existing artifact architecture; extend. |
| SalesChannel (integration role) | WHERE we sell: MARKETPLACE, STOREFRONT, FULFILLMENT_PROVIDER, DISTRIBUTOR, EXPORT_TARGET. An integration may hold several roles. |
| FulfillmentRoute | WHO manufactures/ships a physical edition (e.g., Shopify → Lulu Direct). Separate from MasterProduct. |
| PublicationRecord | WHERE a specific product/edition has been published + remote IDs/status/timestamps. Existing persistence (`data/books.db`) only. |
| ValidationResult / ValidationIssue | Generic pre-publish validation (ERROR/WARNING/INFO). Canonical validation in domain layer; platform-specific inside integrations. |
| PublishResult | Standardized operation result (success, remote ID/URL, warnings, errors, timestamp). Never expose secrets. |
| CapabilityFlags | "What can this integration actually do?" (CONNECTION_TEST, CREATE_DRAFT/LISTING, UPDATE/DELETE, UPLOAD_IMAGES/DIGITAL_FILE, PUBLISH/UNPUBLISH, SYNC_STATUS/ORDERS/SALES, EXPORT_PACKAGE, FULFILL_PHYSICAL, CALCULATE_PRINT_COST). Existing flags; extend, don't replace. |

## Integration Roles

- **Etsy** — MARKETPLACE (official API; preserve existing working code).
- **Gumroad** — MARKETPLACE (next major integration after Etsy; official API; NO browser automation).
- **Shopify** — STOREFRONT (own direct channel; digital + physical).
- **Amazon KDP** — MARKETPLACE/EXPORT_TARGET. No unofficial browser automation. Generate maximally complete KDP upload packages (interior, cover, metadata, keywords, categories, pricing, trim/bleed, page count, ISBN, AI-content disclosure).
- **Lulu Direct** — FULFILLMENT_PROVIDER via its NATIVE Shopify/WooCommerce/Wix connectors. **Do NOT build our own order→print→ship pipeline** while Lulu's native integrations solve it.
- **IngramSpark** — future DISTRIBUTOR/EXPORT_TARGET (distribution package), not immediate API work.
- Secondary/future (do NOT implement now): WooCommerce, Wix, eBay, Payhip, TpT, Creative Fabrica, Creative Market, Sellfy, Ko-fi, Apple Books, Google Play Books, B&N Press, Bookvault, Gelato, Printful.

### Anti-duplication principle

Before ANY external-service feature: check whether an existing platform or
native integration already solves it; prefer official APIs; prefer export
packages over fragile automation. Build integrations for business value,
not because APIs exist. **No unofficial browser automation** for marketplaces.

## Sales Lanes

- DIGITAL: printable PDFs via Etsy, Gumroad, Shopify (+future digital markets). Never route digital fulfillment through Lulu.
- PHYSICAL: paperback/hardcover via Amazon KDP, or Shopify fulfilled by Lulu Direct.

One source project may generate many commercial products/editions
(Amazon paperback, Etsy printable pack, Gumroad mega pack, TpT activity pack…).
Architecture must allow these transformations without contaminating the core
engine; do not build all transformations now.

## Security Rules (all integrations)

Never log/store tokens or secrets; credentials never in `repr` or in
MasterProduct; auth lives inside integrations; redaction everywhere;
explicit HTTP timeouts; bounded retries; never retry permanent failures;
no unnecessary dependencies.

## Development Sequence

1. **CURRENT PHASE: finish and stabilize the WORD DATABASE** (curated,
   categorized, topic/subtopic-aware; supports intelligent selection so
   puzzles stay tightly related to their topic).
2. Audit Universal Publishing foundation for marketplace neutrality; fix minimally.
3. Finish/stabilize Etsy (first publisher).
4. Gumroad.
5. Shopify (digital; physical via native Lulu Direct connector).
6. Amazon KDP export workflow.
7. STOP AND EVALUATE before adding more platforms.

Every phase ships tests (mocks/fakes only — never real external API calls in
unit tests); existing tests must keep passing. Maintain this document plus
`docs/SYSTEM_MAP.md` as architecture evolves; a future developer should be
able to add `integrations/gumroad/` without touching puzzle logic.

Target end-state UX: pick a niche → app generates puzzles/solutions/interiors/
editions/cover/previews/listing metadata from the curated word database → user
reviews everything → Master Product created → PUBLISH screen shows each
channel with edition, price, readiness, capabilities → user selects
destinations → app performs supported API publishing and generates
upload-ready packages where official APIs are unavailable.

## Status Snapshot (2026-08-23)

- Universal Publishing foundation: implemented (models, artifacts, registry,
  capability metadata, HTTP layer with redaction/timeouts, publication
  records, KDP export adapter, hub UI actions) — see `docs/SYSTEM_MAP.md`.
- Etsy draft pipeline: existing, working; adoption of shared mappers complete.
- Word Intelligence system: under active development (`word_intelligence/`),
  see mission spec §1–66; this is the CURRENT PHASE.
- Theme cleanup safety model (2026-08-24): dry-run repair plans carry tiers
  (`auto` ≤10% share & very-high confidence; `review` 10–35%;
  `approval_required` >35%; `blocked` when unresolved gaps exist). Only auto
  may ever apply, `cleanup_theme_library.py apply` is dry-run by default,
  and any non-auto tier requires per-plan `--approve-plan`. Measured plan
  distribution: shares span ~5–50%, so almost everything correctly lands in
  review/approval — curated books need curation, not batch rewriting.
  Standard↔Signature edition pairs are intentional products and are never
  treated as duplicates. Read-only perf baseline:
  `out/word_intelligence_reports/perf_baseline-20260824-084709.json`
  (full 236-theme inventory ≈37 s; single-theme audit ≈73 ms; store lookups
  ≈0.14 µs; cached store load ≈1.7 s).
- Gumroad / Shopify / full KDP workflow / IngramSpark / secondary channels:
  NOT started — future phases in the sequence above.

## Performance & Resource Baseline (project-wide architectural rule)

Adopted 2026-08-24. Philosophy: **feature-rich, modular, responsive, and
lightweight when idle.** Performance is architecture, not a later cleanup.

### The Idle Rule
> If the user is not actively using a feature, that feature consumes
> approximately zero CPU/network and as little extra memory as practical.

No marketplace polling, AI-provider initialization, or intelligence analysis
may run merely because the app is open. Heavy systems follow
**Load → Perform Task → Release**, never Load Everything and stay resident.

### Standing engineering rules
- **Lazy by default.** Startup initializes GUI shell + core state only.
  Word store, integrations, AI providers, publication history load on demand.
- **Word Base scalability.** Indexed/targeted lookups over full scans; no
  duplicate full-library copies in RAM; incremental updates; cached stable
  results; pagination/result limits in GUI surfaces; heavy work stays off the
  Tk main thread (daemon thread + `after(0, ...)` marshalling).
- **Classification coverage ≠ puzzle eligibility.** Dictionary inclusion
  never auto-admits a word into puzzles; production pools require trusted/
  approved or very-high-band evidence plus quality/safety gates (enforced in
  `word_intelligence/repair.py` candidate pools and pool_builder).
- **Background jobs.** Long operations run as controlled background work with
  progress; a future JobQueue (queued/running/completed/failed/cancelled) is
  deferred until bulk workflows justify it.
- **Controlled concurrency.** More parallelism is not better; sequential or
  small-batch execution for heavy jobs until proven otherwise.
- **Memory discipline.** File-backed/streaming processing for PDFs and
  high-resolution images; release large assets when the job finishes;
  thumbnails instead of full-resolution images in GUI memory.
- **Optional features stay optional.** Core puzzle/book generation must work
  with no AI image provider and no marketplace configured. Local AI models,
  if ever supported, are explicit user-initiated downloads with sizes shown —
  never bundled, never initialized at startup; hardware-capability detection
  is deferred to that future phase.
- **Marketplace isolation & lightweight clients.** Integrations initialize on
  demand, never poll by default, fail independently; Lulu Direct remains
  print-fulfillment via its native store connectors (no redundant order
  monitoring built here).
- **Incremental builds (direction).** Changing one artifact (e.g. description)
  must not regenerate upstream artifacts (words/puzzles/PDF); track enough
  dependency info to skip unchanged work once product pipelines exist.

### Baseline & budgets
A read-only performance baseline of current operations is recorded during the
Word Base phase (startup, store load, lookups, classifier run, theme audit,
representative generation). Broad regression budgets — same performance class,
interactive lookups, zero idle CPU, background-safe long jobs — guide future
work; no brittle timing assertions. Local diagnostics only; no telemetry.

### Feature checklist (every major feature)
Startup needed? Resident? Lazy-loadable? Cacheable? Incremental? Background-
safe? Duplicating an existing service? Laptop-friendly? Failure isolated?
Full-database scan avoidable? Large files held in RAM? Idle CPU/network cost?
Simpler implementation possible? Correctness always outranks micro-speed.
