# Word Search Creator — Version History

## 3.37.0 — 2026-08-23

- Strengthened word-search generation with whole-grid retries. If a greedy placement pass falls short, the engine now retries the grid before accepting a reduced puzzle, preventing a prechecked full book from failing during actual package creation.
- Verified the complete Book Studio package path with three Word Search release candidates and added final-package coverage across Sudoku, Cryptograms, Word Scramble + Trivia, and Mixed Brain Games.
- Confirmed automated author consistency, KDP preflight, production proof, cover-wrap creation, and Publishing Manager registration for each newly generated package.
- Publishing Manager now collapses duplicate, untracked non-word package titles to the newest package while preserving any title with marketplace preparation, upload, or publication history.

## 3.36.0 — 2026-08-23

- Added one shared, revision-aware production-readiness record for each theme. Manual checks and package creation write it; the Theme Dashboard and Publishing Manager read it.
- A word-bank edit invalidates its prior pass automatically. Unchecked and blocked themes can no longer be promoted as recommended production books merely because their format or page estimate looks complete.
- Publishing Manager now shows the saved content-check result in Book Details and recommends only themes that have passed the exact current-revision production check, while completed packages remain available as completed work.
- Added integration tests covering pass-record invalidation and the Publishing Manager recommendation gate.

## 3.35.1 — 2026-08-23

- Corrected the readiness connection: a complete puzzle count is now shown as a format check, not as a promise that the word bank is safe to publish. The Theme Safety view now applies the same topic-fit and protected-name review used before package creation.
- Strengthened the PDF engine to use print-safe ASCII separators in visible headings and guide pages, preventing unsupported decorative characters from appearing in generated interiors.
- Added regression coverage for protected-word readiness and PDF heading character safety, alongside the full production sample test.

## 3.35.0 — 2026-08-23

- Added Upload Status to Publishing Manager. It scans the local marketplace folders, records only seller-confirmed upload/published progress, and saves the exact ASIN, listing/product ID, and live URL for every marketplace.
- The local scan marks only untracked prepared folders as Ready. It never overwrites an existing Uploaded or Published record, so your confirmed live information stays intact.
- Replaced the old vague “Mark marketplace published” prompt with a clear per-book status screen that can reopen the saved live listing.

## 3.34.1 — 2026-08-23

- Set SladePuzzleCo as the default Etsy storefront identity for new Etsy bundle listing kits and bundle titles. Jordan M. Slade remains the contributor name; existing print-package brand settings are unchanged.

## 3.34.0 — 2026-08-23

- Added a first-class Etsy Bundle Builder to Publishing Manager. Select two or more completed books and it creates Etsy-sized buyer-download ZIP file(s), a bundle cover image, a complete listing kit, and a saved bundle record—without changing any original book package.
- Refined Publishing Manager actions into a clearer production workflow with direct access to the bundle builder alongside package creation, master handoffs, and marketplace preparation.

## 3.33.1 — 2026-08-23

- Updated Publishing Manager's visible workflow around the new master handoff system: a direct “Open Master Release Folder” action is available from the catalog and Book Details, and the dashboard explains what that folder contains.
- Restyled Book Details and ISBN Manager to match the modern dark Publishing Manager instead of reverting to older Windows-style dialogs.

## 3.33.0 — 2026-08-23

- Added an automatic `MASTER_RELEASE_PACKAGE` to every completed book type. It contains KDP, Etsy Digital, Direct Website, IngramSpark, Lulu, Bookvault, and Barnes & Noble handoff folders with visible instructions for exactly which files can be reused.
- Strengthened marketplace preparation rules: Etsy checks buyer-download size, IngramSpark requires an ISBN and an Ingram-specific cover template, and Lulu/Bookvault no longer treat a KDP-sized wrap as ready for their printers.
- Every new Word Search and Puzzle Book Studio package now registers itself with Publishing Manager automatically. Syncing the catalog also brings older packages into the same master-folder system.

## 3.32.0 — 2026-08-23

- Made Publishing Manager the production hub: it can start a new guided book, open a saved catalog title, or create a complete Word Search package directly from a selected theme.
- Direct package creation uses the same title-uniqueness check, automatic cover settings, no-repeat and preflight gates, and dated output folder as the regular Book Studio workflow.
- Completed packages now automatically register with Publishing Manager as soon as the final package is created, eliminating the manual catalog-sync step before KDP preparation.

## 3.31.2 — 2026-08-23

- Rebuilt Publishing Manager's appearance to match the modern Studio Dark workspace: calm dark panels, clearer hierarchy, modern controls, and improved catalog readability.
- Replaced the vague “Needs Review” outcome with a plain-English KDP readiness explanation. The new “Why not KDP ready?” button tells you exactly whether a title needs a complete package, author detail, or another basic fix.
- Strengthened marketplace validation so it verifies that the referenced interior and cover PDF files actually exist before calling a book ready.

## 3.31.1 — 2026-08-23

- Added a Recommended Next Books panel to Publishing Manager. It ranks titles from your own checked library by broad, series-friendly appeal, usable puzzle count, and whether the book still needs to be created.
- A selected new-book recommendation now opens directly in Word Search tools with its saved recommendations intact. Completed packages are marked as ready to prepare instead.

## 3.31.0 — 2026-08-23

- Completed a product-wide compatibility audit: restored three legacy cover palette aliases, removed the last duplicate high-school vocabulary terms, and confirmed every saved theme has a usable palette, layout, author, and linked cover-background record.
- Modernized the Book Studio home screen with a clearer creation-first layout, a concise quick-start panel, visible entry points for Cryptograms and Scramble + Trivia, stronger chat contrast, and clearer first-run guidance.
- Hardened the standalone package-audit builder so it never treats the Slade Puzzles brand as an author and always puts the real contributor on the full KDP wrap.

## 3.30.1 — 2026-08-23

- Cleaned the Publishing Manager catalog by consolidating timestamped duplicate theme copies into one buyer-facing book record while preserving every original theme and package file.
- Publishing Manager now calculates estimated page counts for saved Word Search themes and reads exact page counts from completed interiors, eliminating zero-page catalog entries.
- Imported existing finished Sudoku, Cryptogram, and Scramble + Trivia packages into the catalog, and created a ready Mixed Brain Games package so every supported puzzle type has a product record.

## 3.30.0 — 2026-08-23

- Added Phase 1 of the modular Publishing Manager: a local SQLite master catalog, reusable metadata engine, marketplace statuses, metadata locking, ISBN duplicate protection, and an ISBN Manager.
- Added safe preparation packages for Amazon KDP, Etsy, IngramSpark, Direct Website sales, Lulu Direct, BookVault, and Barnes & Noble Press. KDP is preparation-only; no browser automation is used.
- Added a Publishing Manager entry to the modern main navigation. It syncs existing themes and completed packages while preserving the original theme files and existing package folders.
- Verified the first real KDP handoff package for America’s National Parks Word Search, including print files, metadata, description, seven keywords, categories, price, and upload checklist.

## 3.29.0 — 2026-08-23

- Added a package-level Author & Metadata Consistency check that blocks publishing-brand names in the contributor field and verifies the selected contributor against the interior PDF and listing kit.
- Every new package now includes a source record, cover-art rights ledger, thumbnail review note, published-catalog duplicate guard, final KDP upload steps, and a plain-English `FIX_THIS_FIRST.txt` report.
- Updated the My Books Dashboard with clearer “Open for Revision” wording and a one-click Release Audit report for current packages.
- Applied the same contributor protection and package records to Sudoku, Cryptogram, Scramble + Trivia, and Mixed Brain Games packages.

## 3.28.1 — 2026-08-23

- Set Jordan M. Slade as the default Author for new Word Search and non-word-search packages.
- Separated the Slade Puzzles publishing brand from the KDP contributor name and made full-wrap author text follow the Author field.
- Updated the three KDP-flagged production themes and rebuilt their matching KDP replacement packages.

## 3.28.0 — 2026-08-23

- Added three commercial-ready starter directions to the Book Assistant: 100-puzzle Number, Letter & Shape Sudoku, Space & Astronomy Cryptograms, and General Knowledge Scramble + Trivia.
- Expanded the verified non-word-search library to support 100-puzzle Signature Editions with a 60% safety buffer: Space Cryptograms now have 180 checked prompts and General Knowledge Scramble + Trivia has 160 checked entries.
- Added matching automatic cover art, palettes, title ideas, listing copy, and search phrases for the Space and General Knowledge directions.
- Strengthened the Production Proof Gate: it now verifies print-sized cover resolution and requires checked-library proof for content-driven books.
- Added an Automatic Book Plan to every completed package so the studio's selected theme, art, palette, format, and safety checks are visible in one plain-English file.
- Replaced the inherited generic word-search back-cover heading with puzzle-specific copy for Sudoku, Cryptograms, Scramble + Trivia, and Mixed Brain Games packages.

## 3.27.1 — 2026-08-22

- Corrected the final full-height layout issue: the hidden Word Search workspace was still reserving an empty row beneath the chat view.
- Chat mode now uses the entire area below the top bar; the detailed workspace receives that area only when it is opened.
- Live measurement confirmed the chat panel fills from y=47 through y=697 in the maximized window, and all 13 automated tests still pass.

## 3.27.0 — 2026-08-22

- Made the app open maximized and made the Book Assistant stretch to the entire available workspace rather than stopping at its natural content height.
- Added responsive content sizing: chat mode fills the screen cleanly, while the detailed Word Search workspace returns to its natural scrollable behavior when opened.
- Verified live at 1366×697 available workspace: the chat surface fills the full height, workspace scrolling restores correctly, and all 13 automated tests pass.

## 3.26.0 — 2026-08-22

- Rebuilt the visible Book Assistant in a cleaner modern-chat style: a quiet dark navigation rail, low-profile top bar, centered conversation surface, subtle prompt chips, and a compact message composer.
- Removed the prominent framed panels, blue banner, permanent status strip, and visible chat scroll chrome that made the home view feel like a traditional form-based desktop app.
- The status strip and scroll controls now appear only inside the detailed Word Search workspace, where they are useful.
- Confirmed the revised home view fits within the app window, routes to saved themes, returns cleanly to chat, and passes all 13 automated tests.

## 3.25.0 — 2026-08-22

- Modernized the Book Assistant into a chat-first workspace: differentiated assistant and user message styling, a streamlined suggestion row, compact navigation, and a single send-arrow composer.
- Replaced the duplicate pop-out Book Assistant with a focused Cover Direction picker, so the app has one clear conversation experience and one purpose-built place for visual cover selection.
- Kept Word Search, Sudoku, Cryptogram, Scramble + Trivia, and Mixed Brain Games routes intact while removing obsolete duplicate assistant routing.
- Stress-checked assistant sizing, scroll behavior, message styling, saved-theme routing, and Mixed Brain Games launch flow; all 13 automated tests pass.

## 3.24.0 — 2026-08-22

- Made the Book Assistant home fit compact laptop screens without requiring a page scroll to reach the message box or Send button.
- The app now adapts its launch size to the available screen height, uses a tighter assistant layout, and hides the main scroll bar on the home screen.
- The full Word Search workspace still restores its scroll bar automatically when its larger detailed controls are opened.
- Verified live at a 648-pixel app height: the assistant content is 542 pixels tall, fully visible, and the automated test suite passes.

## 3.23.0 — 2026-08-22

- Made the Book Assistant the actual home screen rather than a button that opens a separate starting view.
- Replaced the old dashboard with a cleaner conversation layout: simple suggested prompts at the left, the assistant conversation in the center, and one message box at the bottom.
- Kept the detailed Word Search workspace intact but moved it behind one clear button; a Word Search request automatically selects the matching saved theme and opens that workspace only when it is useful.
- Confirmed live routing for both Mixed Brain Games and a saved Space Word Search theme, then passed the automated suite again.

## 3.22.0 — 2026-08-22

- Added Mixed Brain Games: one book can now combine Sudoku, Cryptograms, and Word Scramble + Trivia, each separated by its own illustrated black-and-white section title page and followed by its own answer section.
- Added Mixed Brain Games to the Book Assistant and the main quick-start choices. The studio keeps its capacity safety check before it creates a package.
- Reworked the main screen into an assistant-first dashboard. The detailed Word Search workspace remains available in one click instead of competing with the first choice.
- Corrected a dark photo-cover contrast issue found during a real mixed-book test so titles and the Slade Puzzles imprint remain readable on dark artwork.
- Created and inspected a disposable mixed package: 40 even interior pages, all three section dividers, all answer sections, KDP wrap, listing kit, preflight, and Production Proof Gate; the sample package was removed after testing.

## 3.21.0 — 2026-08-22

- Upgraded the Book Assistant into a visual chooser: it renders three real cover directions from the selected theme, lets the publisher choose one, understands simple refinement requests, and can start a three-puzzle reader preview or final package review.
- Added four built-in app appearances: Studio Dark, Paper Light, Neon Code Rain, and Midnight Indigo. The Book Assistant adds a dedicated neon code-console treatment in Neon Code Rain mode.
- Tested the complete assistant preview path with a saved theme, including visual cover choices and the three-puzzle reader preview; disposable test files were removed afterward.

## 3.20.0 — 2026-08-22

- Added the no-cost local Book Assistant: a chat-style guide that understands plain-English requests, routes to Word Search, Sudoku, Cryptogram, or Scramble + Trivia creation, and finds matching saved Word Search themes.
- Added direct Book Assistant access to the main studio header, preserving all manual choices as optional overrides rather than first-step requirements.
- Confirmed live startup for the Book Assistant and passed the full test suite after the interface addition.

## 3.19.0 — 2026-08-22

- Promoted Word Search, Sudoku, Cryptograms, and Scramble + Trivia to the main screen with clear, direct launch cards; none are hidden in a menu.
- Reworked the Other Puzzle Book Studio into a fuller, focused workspace with its puzzle-type choices first, followed by book settings and proofing.
- Expanded Travel & Adventure Cryptograms to the same 130-entry checked capacity as the other ready Cryptogram packs, using related approved travel, road-trip, outdoor, and national-park vocabulary.
- Removed six disconnected legacy maze/factory utilities and refreshed project documentation to reflect the current app.
- Confirmed live startup for the main studio plus all three new-puzzle launch cards, and passed the full existing test suite.

## 3.18.0 — 2026-08-22

- Raised the release-ready floor for Cryptogram and Word Scramble + Trivia libraries to 130 checked, unique entries. Signature Editions continue to require 160 entries.
- Expanded the General Cryptogram library to 134 prompts and the General Word Scramble + Trivia library to 130 distinct answer/question pairs.
- Connected Space & Astronomy and Garden & Growing Cryptograms to the existing approved Master Word Bank, giving each 130 unique, on-topic prompts without mixing niches.
- Added a content-library verification report to every applicable package, covering exact capacity, malformed entries, and duplicate prompts or answers.
- Upgraded automatic cover selection so Space, Garden, and Travel books select subject-matched local artwork and a valid matching palette.
- Rebuilt the Other Puzzle Book Studio title generator around stronger, puzzle-type and theme-aware titles and subtitles.

## 3.17.1 — 2026-08-22

- Added Standard, Large Print, Kids, and Signature Edition presets to the Other Puzzle Book Studio.
- Enforced the content-buffer rule: standard releases require at least 130 unique entries, while a 100-puzzle Signature Edition requires 160 before creation is allowed.

## 3.17.0 — 2026-08-22

- Added the first supervised-ready themed content library for Cryptograms and Scramble + Trivia: Space & Astronomy, Garden & Growing, and Travel & Adventure.
- Added theme selection to the studio and automatic capacity guards, so a themed book cannot be created with more puzzles than the library can support without repeats.

## 3.16.0 — 2026-08-22

- Added the Production Proof Gate to every new non-word-search package. It blocks a finished package when required PDFs, listing facts, trim size, page count, or Sudoku special-game promises do not match.
- Revamped the Other Puzzle Book Studio around a simple create-and-proof flow, including direct access to the latest package and proof report.
- Strengthened the review summary so every new package states its exact promises before creation.

## 3.15.0 — 2026-08-22

- Made special Sudoku games standard in every new Sudoku book: a balanced mix of classic number, letter, and font-free shape Sudoku using the same verified one-solution logic.
- Added the special-game promise to Sudoku covers, instructions, KDP listing kits, and descriptions.

## 3.14.2 — 2026-08-22

- Added a one-click title and subtitle idea generator to the Other Puzzle Book Studio.
- Expanded Scramble + Trivia to 60 unique starter games and added hard no-repeat limits for its starter content and Cryptograms.

## 3.14.1 — 2026-08-22

- Upgraded all future KDP descriptions with more vivid, shopper-friendly copy while keeping every promise grounded in the actual interior.
- Added type-specific description voices for Sudoku, Cryptograms, and Word Scramble + Trivia packages.

## 3.14.0 — 2026-08-22

- Added a separate Other Puzzle Book Studio for Sudoku, Cryptograms, and Word Scramble + Trivia, keeping word-search creation isolated and unchanged.
- Each new puzzle type now creates a complete KDP package: interior, full-wrap cover, listing kit, compliance report, scorecard, and plain-English upload guide.
- Added automatic, matching local cover artwork for all three new puzzle types.
- Corrected the standalone Sudoku generator’s Windows font paths and strengthened thin Sudoku grid lines for print reliability.

## 3.13.5 — 2026-08-22

- Added a KDP Compliance & Discoverability review to every future package, including metadata blockers, supported-HTML description checks, keyword checks, and upload guidance.
- Reworked copy-ready descriptions into simple, scannable KDP-compatible HTML with accurate puzzle details rather than keyword stuffing.
- Strengthened print preflight with KDP's 24-page minimum, 8.5 x 11 page-range guidance, even-page verification, and the current 79-page spine-text threshold.
- Made the interior engine add a final blank page when needed, keeping the PDF page count and cover-spine calculation aligned.
- Corrected all Signature Edition builders so their actual interiors include the promised Signature pages, rather than only their listings and covers doing so.
- Clarified the AI disclosure reminder to follow KDP's distinction between AI-generated and AI-assisted content.

## 3.13.4 — 2026-08-22

- Rebuilt both Vocabulary Ladder Signature Edition packages with the KDP-safe heading system enabled.
- Added a separate non-destructive replacement-package builder, so approved originals are always retained.
- Put the upgraded premium Grade 5 and Grade 8 listing descriptions directly into each replacement package.
- Corrected the Garden/Homestead Signature builder to validate against the Master Library's direct topic names.
- Made source-linked books use the Master Library's exact topic-fit check instead of a narrower keyword-only heuristic.

## 3.13.3 — 2026-08-22

- Fixed long puzzle headings in interiors: headings now automatically scale to remain inside the KDP print-safe page area instead of extending into the trim or gutter region.
- Rebuilt the National Parks interior in a separate KDP-fixed package so the original package remains preserved.

## 3.13.2 — 2026-08-22

- Added the market-led Top 5 production builder with direct-topic word pools, placement validation, repeat-free checks, KDP listing materials, and complete individual package folders.
- Kept incomplete production themes safely marked as drafts so they cannot interfere with the originality checks for completed books.
- Refined source-topic validation so intentional multi-topic seasonal books are evaluated against their actual approved source groups.
- Corrected the KDP wrap barcode treatment to reserve one clean required barcode area instead of displaying an unnecessary second white rectangle on the back cover.

## 3.13.1 — 2026-08-22

- Connected the three-level library reports to the in-app Library & Quality Center, including plain-English readiness, dictionary-screen, and review information.
- Added one safe “Refresh Library Intelligence” action that rebuilds the Master Library, candidate map, readiness map, and audits without modifying any saved theme or creating a book.
- Improved the main-screen library summary so it shows what is ready now and what is intentionally being expanded.
- Added a `START_HERE.txt` handoff file to every complete package folder, explaining exactly which interior and wrap files upload to KDP and which proof files to review first.

## 3.13.0 — 2026-08-22

- Added a three-level dictionary library: Proven words can generate books; Suggested words are high-confidence topic candidates awaiting review; Unassigned words remain searchable but cannot contaminate a niche automatically.
- Added 10,800 frequency-screened, direct Grade 5–12 vocabulary assignments from the local dictionary. Each grade now has enough mapped words for a repeat-free 48-puzzle standard book and a true 100-puzzle Signature Edition.
- Rebuilt the Grade 5–12 source themes from their own direct pools rather than remixing three short lists. Standard and Signature source themes now pass the strict quality gate with no repeats or catalog-overlap warnings.
- Strengthened the production stop: strong book similarity, weak clean-library fit, and weak independent topic fit now block package creation instead of appearing as warnings that can be overlooked.

## 3.12.1 — 2026-08-22

- Deepened the clean, direct-source word bank for Bible & Faith, Gardening & Homesteading, National Parks, and Pets. These focused packs now have honest repeat-free capacity records for full 48-puzzle books.
- Added capacity records for the Guided Builder's combined topic packs, so a friendly multi-topic choice can be evaluated using the actual words available to it.
- Strengthened meaningful discovery links for faith and nostalgia terms while keeping generation strict: related words are easier to find, but unrelated vocabulary is never silently placed into a niche book.
- Corrected compound pet and breed entries so phrase fragments cannot be mistaken for standalone puzzle words.

## 3.9.2 — 2026-08-22

- Expanded the Master Library with researched space/astronomy, weather/climate, and forest/wildlife/outdoor vocabulary. Added dedicated Weather & Climate and Forest, Wildlife & Outdoors topic choices and ready-made Builder packs.
- Updated the related-topic rules so outdoor, weather, nature, park, science, and travel terms remain discoverable across every relevant group without being added as unrelated direct puzzle words.

## 3.9.1 — 2026-08-22

- Rebuilt the Master Library’s word profiles to distinguish strict source-topic membership from helpful related-topic discovery links. A word can now be found through every relevant group without weakening the topic-purity checks used for a finished book.
- Added repeat-free 48-puzzle and 100-puzzle capacity flags to every topic, so the Guided Builder and launch ranking can identify thin word banks before a book is planned.
- Restored package creation for legacy themes: clean-library and topic-fit signals are now review notes rather than accidental hard stops. Photo Hero now chooses a matching local background automatically or safely falls back to an illustrated layout.

## 3.9.0 — 2026-08-22

- Rebuilt the Guided Builder Master Library from curated, topic-specific source groups only. It no longer learns vocabulary from active theme files, preventing an old mixed book from contaminating a new niche.
- Added 65 clean topic choices, cross-linked words wherever they genuinely fit more than one subject, topic-family organization, no-repeat capacity counts, and an honest local dictionary/spelling reference policy.
- Added a ranked “Make Next” score in the Library & Readiness Dashboard. It favors complete, repeat-free, topic-matched themes with enough clean source capacity and flags themes that need a word-bank rebuild before production.
- Made 100 puzzles the required size for every new Signature Edition. The Blueprint Wizard, edition settings, final package screen, quality checks, page estimate, listing kit, and price estimate now agree on that standard.
- Recalibrated suggested US pricing for the larger Signature format. A typical 100-puzzle Signature interior now suggests $13.99; KDP’s own print-cost calculator remains the final authority.

## 3.8.0 — 2026-08-22

- Reorganized the main Book Studio into a clearer four-step workflow: Choose a Book, Name Your Book, Cover Plan, then Review, Create & Proof.
- Removed duplicate tool paths from the daily screen and renamed grouped menus in plain English: Library & Planning, Picture Choices, Cover Workshop, Extra Outputs, and More Studio Tools.
- Moved Signature Edition and “move to Used Themes” choices into Final Book Review, where they affect the package and are no longer visual clutter during normal book setup.
- Added a one-click main-screen Cover Preview and kept advanced cover, library, research, publishing, safety, and app settings grouped in their appropriate workspaces.
- Added three purpose-built learning cover backgrounds for elementary, middle-school, and high-school vocabulary books. Grade 5–12 books now automatically choose their correct education-level artwork and matched palette instead of a generic reading or living-room scene.

## 3.7.1 — 2026-08-22

- Fixed a hidden edition-settings leak found during the finished-book audit: standard packages now include Signature Edition pages only when the app’s Signature Edition checkbox is selected. Clearly named Signature Edition themes still select that option automatically.
- Synced the Final Book Review, price estimate, page estimate, KDP listing kit, back-cover wording, and the interior engine to the same explicit edition choice.
- Added automated regression coverage for standard-versus-Signature behavior and completed a corrected Grade 5 end-to-end test package. Its 81-page interior, cover, full wrap, listing kit, and print preflight passed.

## 3.7.0 — 2026-08-22

- Added an independent, source-safe topic-fit check for focused Zion, Space, and Christmas books. It prevents a package from being created when the word bank does not support the cover promise.
- Upgraded possible protected brand, franchise, and celebrity names from a review note to an automatic package stop.
- Corrected the dashboard wording so old Master Library history is presented as a cross-reference, never as proof that a word bank is genuinely on topic.
- Completed a full visual product audit of National Parks, Space, and Christmas test packages. Layout, grids, solutions, wraps, and KDP files passed; the source word banks were correctly identified as not publishable until their topic vocabulary is rebuilt.

## 3.6.0 — 2026-08-22

- Connected every reusable photo family to a deliberately matched palette, including all National Park subcategories. Automatic photo selection and the visual photo picker now apply the matching colors with the Photo Hero layout.
- Added the polished Retro Travel & Landmarks palette to the Book Studio color picker, so travel recommendations are visible and fully editable.
- Validated all 29 photo families, all 20 National Park scenery matches, and representative canyon, space, and winter cover previews for contrast and readability.

## 3.5.0 — 2026-08-22

- Improved the last approval step into a clearer Final Book Review: title, subtitle, difficulty, puzzle count, total word count, estimated pages, price estimate, selected picture, cover direction, and package folder are shown beside the cover preview.
- Added a visual Cover Background Picker under Cover Picture Tools. It shows up to three best topic-matched background choices before package creation; National Parks retain their exact landscape match.
- Added a Series Factory visual lock. Leave it on for a recognizable collection family with identical colors and layout, or turn it off for coordinated variation. The chosen family style is remembered whenever a series theme is loaded.

## 3.4.0 — 2026-08-22

- Expanded the reusable cover-background library to 53 locally stored images: three rotating choices for every core topic plus a dedicated National Parks collection for forest, alpine, canyon, geyser, desert, waterfalls, coast, rainforest, mountain lakes, rivers, dunes, thermal springs, hoodoos, volcanoes, arches, and caves.
- Photo recommendations now choose a stable variation per title, so rebuilding the same book keeps its visual identity while different books in a topic avoid always receiving the same image.
- National Parks titles now always favor their exact scenery type over a generic outdoors image.
- Added a repeatable Grade 5-12 package builder and created a final corrected photo-cover package set. Each book accurately states 48 puzzles and includes an interior, front cover, KDP full wrap and preview, listing kit, upload checklist, scorecard, and preflight record. Earlier classic and photo-cover drafts remain preserved separately.

## 3.3.0 — 2026-08-22

- Added a 13-image reusable photo-background library covering current core collections: outdoors, gardening, pets, ocean, vehicles, space, books, winter holidays, autumn/Halloween, food, travel/history, sports, and 90s nostalgia.
- Book Studio now automatically suggests a matching Photo Hero background for a theme that does not already have its own saved cover picture. A new Cover Picture Tools action lets you reapply the suggestion at any time.
- Updated Photo Hero covers with a quiet faded word-search grid across the photo background, so every image-led cover still visibly reads as a puzzle book.
- The background library does not overwrite a saved cover choice. Each generated background carries a local note to review final rights and KDP AI-content disclosure before commercial upload.

## 3.2.0 — 2026-08-22

- Connected all production routes to one package handoff: the final title, subtitle, author, cover callout, palette, layout, and Signature Edition choice now carry through to KDP listing files, price guidance, scorecards, and back-cover wording.
- Rebuilt the old preflight checker around the actual Book Studio package files. Every new complete package now receives `PUBLISHER_PREFLIGHT.txt` that checks its interior page count, trim, wrap dimensions, spine rule, and author metadata.
- Updated the Production Queue to create the same complete paperwork as Book Studio, including a full-wrap preview, KDP listing kit, upload checklist, preflight report, and package scorecard.
- Finished packages now automatically appear as Ready in My Books Dashboard and retain the exact created package folder even if the title was customized during production.
- Added two verified photo-cover sample packages for local review: National Parks and Gardening. Their cover-art notes clearly remind you to confirm rights and KDP AI-content disclosure before commercial upload.

## 3.1.0 — 2026-08-22

- Added Publisher Safety Check: plain-English topic-fit, cover-promise, and protected-name review signals now join the full Book Quality Check. It preserves existing word banks and never claims to provide legal clearance.
- Upgraded Theme Dashboard into a Production Dashboard with topic-fit, package, readiness, and rights-review status in one view.
- Added Edition Designer for saving a coordinated palette, cover layout, front-cover callout, and Signature Edition setting without changing a book's words or pages.
- Added Market Pulse Tracker: it opens live Google Trends/Amazon research and saves your dated observations locally, without presenting changing web data as a fake sales score.
- Kept the main Book Studio uncluttered: the new tools live under Production Tools → Production Management and Safety & Settings.

## 3.0.0 — 2026-08-22

- Strengthened cross-book similarity protection: every active theme is compared, very close non-Signature matches block package creation, and medium/strong matches provide plain-English review notes.
- Added Series Differentiation: it identifies the closest related books, suggests a distinct next angle, and opens Series Expansion with the selected book already loaded.
- Added automatic final package files in both production routes: `KDP_LISTING_KIT.txt`, `KDP_UPLOAD_CHECKLIST.txt`, and `PACKAGE_SCORECARD.txt` now travel with the interior, cover, and KDP wrap.
- Reorganized the Master Library into 8 topic families and 9 pack families. Guided Book Builder now presents focused packs with their family label instead of one long ungrouped list.
- Expanded the Master Library to 8,063 unique words across 67 topics and 68 ready-made packs, including arts, music, farm life, coastal/lake/river life, U.S. landmarks, community careers, and word skills.

## 2.9.0 — 2026-08-22

- Added automatic Collection Guide and My Puzzle Notes pages to every new interior (themes can opt out only when needed); Signature Editions retain their existing special pages.
- Added the simple Book Quality Score with a buyer-facing strength score and plain-English next steps.
- Added the required Review Before Creating screen: it shows title, subtitle, topic, difficulty, puzzle count, page estimate, price guidance, cover direction, output location, score, and a live cover preview before complete-package creation.
- Streamlined the Create area: quality score, one More Create Options menu, and one clear Review Before Creating path.
- Expanded the Guided Builder Master Library to 8,002 unique words across 60 topic groups and 61 reusable packs, including Outdoor Adventure, Home & Household, Wellness, Science & Discovery, Pets & Animal Care, and Travel/Road Trips. Every shared word is re-linked to every applicable topic and pack during rebuild.

## 2.5.0 — 2026-08-22

- Added an integrated OpenClipart picker backed by the CC0 OpenClipart dataset, with automatic keyword suggestions, review-risk filtering, thumbnail selection, download-on-choice, cached assets, and a persistent license/source record.
- Added automatic Photo Hero crop-focus suggestions from image shape, applied to previews, front covers, and complete packages. Packages using selected OpenClipart art now include a cover-art license record.
- Made the main Book Studio vertically scrollable so all Create controls remain reachable on shorter laptop screens.
- Replaced several technical labels with plain English and added hover explanations for puzzle pattern, output file, cover callout, back-cover name, colors, layout, and cover picture.

## 2.4.2 — 2026-08-22

- Added a protected full-package builder for the discussed collections. Each package receives an interior PDF, 300-DPI front cover, KDP-sized full wrap, listing kit, and preflight report.
- Generated 62 protected packages: 20 Market Opportunity, 22 Vocabulary Ladder, and 20 National Parks. Existing package folders are skipped rather than replaced.

## 2.4.1 — 2026-08-22

- Added the protected 20-book Market Opportunity Collection: separate, market-informed evergreen Word Search theme files that never overwrite existing books.
- Added a safe collection builder that requires 48 twelve-word puzzles, no repeated word within a book, topic-mapped Master Library selections, and Slade Puzzles authorship.
- Reviewed the existing Vocabulary Ladder and National Parks series without altering them: all 22 Vocabulary and 20 National Parks book files are repeat-free.

## 2.4.0 — 2026-08-22

- Added research-led Master Library expansion groups for book lovers, gardening, hobbies and crafts, faith and kindness, and seasonal celebrations.
- Added ready-made Guided Book Builder packs for reading, nostalgia, large-print friendly topics, mindfulness, gardening, holidays, Americana, and faith.
- Kept the new word lists generic and reusable, avoiding protected character and celebrity names in the new market-oriented collections.

## 2.3.6 — 2026-08-22

- Added a dedicated Master Library expansion source and enriched Space, Vehicles, Video Games, Pop Culture, Nature, Birdwatching, Homesteading, Mindfulness, Parenting, and World War II vocabulary.
- Added nine new ready-made word-bank groupings, including stargazing, space missions, car care, classic cars, road trips, gaming culture, birding, and family wellness.

## 2.3.5 — 2026-08-22

- Fixed the grouped Theme Library startup freeze by removing the full-library scan from launch and preventing repeated selection reloads.

## 2.3.4 — 2026-08-22

- Strengthened the Windows startup repair by forcing the main app window visible immediately in a normal on-screen position before any background work begins.

## 2.3.3 — 2026-08-21

- Fixed a Windows visibility issue that could leave the app running behind other windows; the main window now brings itself to the front when launched.

## 2.3.2 — 2026-08-21

- Replaced the console-based Windows launcher with a clean app launcher that closes the blank command prompt and shows a readable startup message if a future failure occurs.

## 2.3.1 — 2026-08-21

- Replaced the flat main Theme Library list with expandable folder and series groupings; search now narrows matching groups and books.

## 2.3.0 — 2026-08-21

- Added switchable Dark View (enabled by default), including dark workspace cards, fields, theme library, and controls.
- Added Word-Bank Health to estimate fresh vocabulary capacity by topic before creating another book.
- Strengthened duplicate-title warnings to catch very similar titles, and added automatic recoverable theme backups before major edits.
- Consolidated duplicate tool entry points into clearer Theme Tools, Planning & Research, Production Management, and Safety sections.

## 2.2.9 — 2026-08-21

- Added the one-click Publish Ready Check, which automatically verifies puzzle placement, repeat-free words, cover setup, KDP listing details, and package preparation before production.
- Added an automatic $1 Signature Edition premium to recommended list prices and clearly labels the edition pricing in listing notes.

## 2.2.8 — 2026-08-21

- Refreshed 106 active theme files to remove repeated words across each book, with a timestamped backup created before the refresh.
- Added an automatic difficulty marker to all cover-generation paths and added difficulty plus the verified “No repeated words across the book” promise to exported KDP listing information.

## 2.2.7 — 2026-08-21

- Added eight new cover palettes and a Signature Edition Halo layout for coordinated premium series design.
- Made the interior-only creation path respect the same hard no-repeat quality gate as complete-package production.

## 2.2.6 — 2026-08-21

- Made no repeated words a hard production rule for new Guided Builder, Blueprint, and companion-series books.
- Added an across-the-book repeat check to production quality checks and Project Check.
- Added the accurate “No Repeated Words” cover badge to validated Vocabulary Ladder books.

## 2.2.5 — 2026-08-21

- Applied a dedicated Vocabulary Ladder cover system: shared premium Gallery layout, grade-color progression, consistent imprint, and Signature Edition badges.
- Corrected vocabulary-series palette and layout values so every generated cover uses its intended design.

## 2.2.4 — 2026-08-21

- Refined Vocabulary Ladder progression so neighboring grades intentionally share useful vocabulary while retaining distinct puzzle selections.
- Added richer Word Quest welcome pages and Word Power Challenges to Vocabulary Ladder Signature Editions.

## 2.2.3 — 2026-08-21

- Added the Vocabulary Ladder Collection, with Grade 5–12 standard editions and matching Signature Editions.
- Added graded Vocabulary topic packs to the Guided Book Builder's Master Library.

## 2.2.2 — 2026-08-21

- Added large, organized Video Games & Gaming and Pop Culture & Entertainment libraries.
- Added reusable ready-made packs for retro games, modern games, game night, movies/TV, media trends, and throwback culture.
- Added word-to-group links so every reusable word records its applicable source topic and matching packs.

## 2.2.1 — 2026-08-21

- Added the Guided Builder's No-Repeat Book Capacity check for clear 48- and 100-puzzle planning.
- Expanded the Space & Astronomy and Vehicles & Automotive libraries with friendly, deduplicated book-ready vocabulary.

## 2.2.0 — 2026-08-21

- Added visible in-app version tracking and this local change record.
- Expanded the Guided Book Builder's Master Library with deep Space & Astronomy and Vehicles & Automotive packs.
- Kept the production workspace consolidated: planning, production, safety, help, and error records stay grouped in clear menus.

## 2.1.0

- Added Guided Book Builder review and approval flow, plain-English error log, help center, niche research, and production tools.

## 2.0.0

- Established the Book Studio workspace, cover tools, quality checks, KDP packaging, theme organization, and series workflow.
## 2.6.0 — 2026-08-22

- Added a guided CC0 picture board with topic collections, a one-click best match, and a saved-picture library.
- Added automatic picture-quality scoring, title-protection guidance, palette matching, recommended crop focus, and picture reuse history.
- Added series-aware cover memory so related books start with a consistent cover family without locking out individual choices.
- Upgraded Cover Variations to include Photo Hero when a picture is selected, and consolidated picture actions into one clear menu to keep Book Studio uncluttered.
## 2.7.0 — 2026-08-22

- Simplified Book Studio into an automatic-first workflow: choose a theme, review title and subtitle, optionally choose a picture, then create the complete package.
- Moved author, puzzle pattern, filename, cover colors, layout, callout, and imprint into a collapsible Customize section; the normal view is shorter and easier to use.
- Added automatic fresh puzzle patterns, automatic inside-pages filenames, automatic cover-plan summaries, and retained manual control when needed.
- Completed the active theme library to the Slade production standard: at least 48 puzzles, at least 12 distinct words per puzzle, and no repeated words within a book. Original files were backed up before completion.
- Added a repeatable local theme-completion tool and production-readiness metadata for future theme audits.
## 2.8.0 — 2026-08-22

- Audited and strengthened the KDP listing kit: seven separate keyword-box phrases, current category direction, truthful price guidance, and clearer metadata, rights, and AI-disclosure checks.
- Removed the misleading pre-upload royalty estimate; final printing cost and royalty now stay with KDP's current calculator.
- Added a safe refresh tool for existing listing files that preserves the previous version beside each refreshed kit.
- Added Library & Quality Center: one non-destructive location for capacity, dated library audits, source records, and word-review reminders.
- Added source provenance to the Master Library so future refreshes can distinguish curated topic vocabulary from spelling-reference material.
- Expanded the Guided Book Builder approval summary with buyer-facing details, no-repeat confirmation, cover direction, source, saved folder, and price.
- Consolidated Book Studio menu wording and moved duplicate safety/library actions into clearer groups without changing the generation workflow.

## 3.10.0 — 2026-08-22
- Choosing a focused topic in Guided Book Builder now automatically loads its clean vocabulary, title/subtitle direction, no-repeat puzzle count, cover recommendation, badge, and picture-search terms; every suggestion remains editable.
- Created three non-destructive, preflight-passing sample packages to validate the live package workflow across history, space, and automotive topics.

## 3.10.1 — 2026-08-22
- Expanded the local Photo Hero library with three matched visual variants each for American History, Bible/Faith, Birds, and Weather.
- Made local topic-matched photos the clear default in Book Studio: “Use Best Matching Picture” and “See Other Matching Pictures” are now visible before advanced picture options.
- Connected the sample-package smoke test to the same automatic picture picker used by Book Studio and verified photo-based covers for history, space, and vehicles.

## 3.10.2 — 2026-08-22
# 3.10.3 — Editorial Covers and Topic Previews

- Rebuilt Photo Hero so photos stay visible and the cover no longer relies on one oversized rounded title card.
- Added topic-specific back-cover copy with a relevant discovery note and a refined full-wrap layout.
- Added **Preview This Topic**, which automatically uses a recommended local background when available before creating the cover preview.
# 3.10.4 — Stronger KDP Listing Kits

- Reworked automatic keyword suggestions to add distinct, topic-relevant search paths instead of repeating the title.
- Added a reader-focused HTML-ready description, clearer three-category guidance, and exact AI-art disclosure guidance for the built-in photo library.
- Added a pre-publish reminder that puzzle books are generally not low-content, plus an Expanded Distribution expectation check for word-search books.
# 3.10.5 — Production Lock and Hard Stops

- Added a production-lock archive and first-five-books review tracker for a controlled launch.
- Added a final hard-stop gate before complete package creation for missing book details, repeated words, weak focused-topic fit, missing Photo Hero art, and incomplete listing data.
- Added production-lock and first-five-tracker actions under Safety & Settings.
# 3.11.0 — Focused Library & Builder Refresh

- Rebuilt the Master Library around focused Bible/Faith, Gardening/Homesteading, National Parks, Pets, and Decades/Nostalgia sources.
- Added dedicated source groups and buyer-friendly topic packs, with clean links between related topics.
- Added plain capacity records for 48- and 100-puzzle books at both 12 and 20 words per puzzle.
- Refreshed the Book Studio library panel and Guided Book Builder so starting from a focused topic is clearer and less crowded.
# 3.12.0 — Production Safeguards & Proof Review

- Added a Quick Proof Bundle: a buyer thumbnail, three-puzzle reader PDF, listing preview, and simple review checklist.
- Every complete package now includes a proof-review folder and originality report automatically.
- Package scorecards now verify the proof bundle and originality check alongside KDP files.
- Simplified main-screen production actions and added a ready-only filter to the Production Dashboard.
- Corrected every cover layout to use the actual book format instead of assuming “Large Print.”
- Added a stale-blurb guard so back-cover facts cannot carry over from an unrelated old theme.
