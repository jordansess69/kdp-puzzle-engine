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
- Gumroad / Shopify / full KDP workflow / IngramSpark / secondary channels:
  NOT started — future phases in the sequence above.
