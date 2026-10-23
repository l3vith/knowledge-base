# Source-derived metadata retrieval

The index stores useful document and page metadata and uses validated structural hints to reduce retrieval work. It adds no paid ingestion calls, embedding calls or model training. The public API, ten trace stages, exact source citations and semantic answer checks are unchanged.

## Collected information and its purpose

- **Document identity:** existing source ID and filename, streaming SHA-256 and file size. Optional backfill source PDFs must match the indexed identity and page count.
- **Declared PDF properties:** title, author, subject, creator, producer and dates, where available. A bounded author/subject hint can enter planning; creation/modification dates are not treated as publication or reporting dates.
- **Document structure:** native outline hierarchy, Markdown headings, section breadcrumbs and inferred inclusive physical page ranges. Parents include their child sections.
- **Contents and index entries:** titles, printed Arabic/Roman labels, ranges, source anchor pages, resolution method and confidence. Unresolved entries are retained for diagnostics.
- **Page navigation:** physical page, printed label, PDF label rules and internal same-document link destinations. External links are never followed.
- **Source locators:** table, figure, chart, exhibit, appendix and numbered section references; source captions and their pages.
- **Table/context features:** source table headers/counts, units, mentioned years and numeric density. Headers, explicit units/years and requested tables provide bounded ranking hints. Mentioned years do not become hard date filters.
- **Extraction diagnostics:** OCR flag, text-character count, page dimensions, rotation and image count. Geometry and extraction features are stored for inspection; they are not all active ranking signals.

Missing properties stay missing. This covers supported useful metadata, not every possible PDF annotation, font or arbitrary custom field. Source text and vector representations remain unchanged during metadata-only upgrades.

## Printed pages are validated

A printed page number is not assumed to equal the PDF physical page. Contents references resolve through unique actual source headings, body-validated internal link destinations, explicit page labels, or an offset supported by at least two distinct heading anchors. Target content must corroborate label/offset matches. Ambiguous references remain unresolved. Back-of-book index ranges have separate handling and bounded expansion.

Native bookmarks whose titles cannot be corroborated on the target source page receive lower confidence. Only allowed source origins with confidence at least 0.85 can guide section focus. Confidence describes navigation reliability, not factual support. Range boundaries inferred from headings can still be imperfect.

## Query behavior

The existing document identity/period guard runs first. For each allowed document, source sections/captions are matched to the original query obligations. Generic overlap with the document title or entity cannot trigger focus. A non-exhaustive query is focused only when every obligation has a specific validated structural match.

At most two ranges per obligation contribute two ranked pages plus each range start. Explicit table/figure/section or page references can prioritize a target before the global page cap. Existing lexical/vector rankings remain available. Local page survey retains three independent outside pages when focused; scoped source FTS retains up to eight independent outside element hits. Exhaustive queries keep their broader selection behavior within existing resource caps. These fallbacks reduce, but cannot eliminate, the risk of missed evidence.

A bounded metadata score adjusts local MiniLM reranking. Contents/index pages receive a small penalty unless requested. Generic metadata alone reorders candidates without expanding their page pool. Same-document table/figure dependencies can add at most four elements per query. Generic section references do not eagerly pull entire background sections.

Only original source elements proceed to evidence verification. Metadata does not authorize an answer, establish absence, replace source quotations or bypass semantic verification. The planner receives a small structural preview, not the full metadata payload. Trace outputs record matched ranges, confidence, selected pages and unresolved-reference counts.

## Ingestion, compatibility and upgrade

New/repeated indexing builds navigation after source segmentation using cached parses, cards and vectors where available. Old parse-cache entries gain native PDF page metadata without paid calls. Existing cache version and SQLite schema remain compatible; navigation lives in document card JSON. Generation-bound document cards are cached locally to avoid repeated JSON decoding.

Older collections remain usable without navigation. To enrich an existing collection:

```bash
python -m scripts.enrich_metadata --collection demo --source-dir /absolute/path/to/source/pdfs
```

The source directory is optional. Without it, the upgrade uses stored text and any previously collected metadata; native PDF information cannot be newly recovered. Source PDFs supplied for enrichment are identity checked. The operation backs up SQLite, copies unchanged vectors, builds a staging generation and promotes atomically. A failure leaves the active generation intact. It preserves the previous generation according to the existing registry retention policy. Account for temporary duplicate-index disk usage.

Set `KB_METADATA_NAVIGATION=0` to disable query navigation, metadata boosts and dependency expansion for ablation. Default is enabled. No new public endpoint is added.

## Validation and measured limits

The non-slow suite passes 164 tests, with seven slow model tests deselected. Coverage includes hierarchy, Arabic/Roman contents/index resolution, bad offsets, actual PDF labels/links, explicit late-page selection, low-confidence hints, source dependencies, legacy cards and atomic source/vector-preserving enrichment.

A local comparison on the existing 24-page collection reused identical saved public query plans and real cached embedding/reranking models. It made no LLM calls and spent no API credits:

- Factual C31: candidate elements 56 → 42 (25% fewer), retaining the one previously cited source.
- Analytical C18: candidate elements 86 → 86, retaining all 18 previously cited sources.

After integrating the teammate’s relevance-order and budget changes, both metadata variants use 86 analytical candidates (the earlier comparison used 89).

These are retrieval-work and prior-citation-retention checks, not a new end-to-end latency benchmark, recall over all relevant source passages, or official answer-accuracy result. Timings from one local pass are diagnostic only. Analytical precision/latency and writer-context omissions still require further work. The original official benchmark and evaluator are unchanged. Portable measured counts are in [the diagnostic summary](diagnostics/metadata-navigation/summary.json).
