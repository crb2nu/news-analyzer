Metadata Extraction & Mapping Plan
=================================

Goals
-----
- Normalize rich metadata for each article so the UI, summaries, events, and notifications are consistent and queryable.
- Keep extraction sources (PDF/HTML/Facebook) pluggable but map to one unified schema.

Target Schema (PostgreSQL)
--------------------------
- articles
  - id: int PK
  - title: text
  - content: text (clean body)
  - content_hash: varchar(32) unique (md5 of normalized content)
  - url: text (canonical link if present)
  - source_type: varchar(10) ('pdf'|'html'|'fb'|'other')
  - source_url: text (origin URL) / source_file: text (MinIO path)
  - page_number: int, column_number: int (for e-edition PDFs)
  - section: varchar(100) (normalized; e.g., 'Local','Sports','Obituaries','Public Safety')
  - author: varchar(200)
  - tags: jsonb (keywords, named entities)
  - word_count: int
  - date_published: timestamptz
  - raw_html: text (optional, for source view)
  - metadata: jsonb (catch‑all, full fidelity)
  - location_name: text, location_lat: float8, location_lon: float8
  - event_dates: jsonb (array of {start_time,end_time,confidence})
  - processing_status: varchar(20) ('extracted'|'summarized'|'notified')

- summaries
  - article_id: int FK → articles(id)
  - summary_text: text
  - summary_type: 'brief'|'bulletin'|...
  - model_used, tokens_used, generation_time_ms

- article_events
  - article_id: int FK
  - title, description
  - start_time, end_time (timestamptz)
  - location_name, location_meta jsonb

Extraction → Mapping
--------------------
1) PDF (pdfminer‑six)
   - title: first bold/large text near top; fallback to first line before body
   - section: inferred from header/footer text, page labels, or URL path
   - page_number/column_number: parsed from e‑edition metadata or layout heuristics
   - date_published: taken from edition date (CLI argument / discover) per page
   - location_name: regex + gazetteer pass (optional)
   - event_dates: event_parser on body → [ISO times]
   - metadata: {edition_id, pdf_path, bbox samples}

2) HTML (trafilatura/BS4)
   - title: <meta property="og:title"> → <title> → h1
   - section: meta[name="section"] → breadcrumbs → URL path segments
   - author: meta[name="author"] → byline patterns
   - date_published: meta[property="article:published_time"] → time[datetime]
   - raw_html: stored for source views
   - metadata: full meta tags map

3) Facebook Pages (Graph API)
   - source_type: 'fb'
   - title: first 100 chars of message or event name
   - content: message/description
   - date_published: created_time / start_time
   - url: permalink_url
   - location_name/lat/lon: from event place
   - event_dates: start_time/end_time
   - metadata: raw JSON blob (redacted to fields we keep)

Normalization Rules
-------------------
- Section normalization (keep UI consistent):
  obits|obituary|obituaries → Obituaries
  police|police and courts|crime → Public Safety
  editorial|opinion → Opinion
  local, news, sports, business → title‑case
  default → General

- Tags & Entities: optional spaCy/transformers pass to enrich tags jsonb

- Locations: simple regex + optional Nominatim/geocoder enrichment (config‑gated)

Pipeline Touchpoints
--------------------
- scraper/discover.py: ensure section and edition_date are attached to each page URL
- extractor/processor.py: produce Article dataclass with fields above
- extractor/database.py: already has columns and upserts; add small helpers if needed:
  - set_section_normalized(section)
  - store_events(article_id, events[])

Quality & Deduping
------------------
- Compute md5 of normalized content (strip whitespace, collapse punctuation) → content_hash
- Skip insert if hash exists for edition_date
- Keep processing_history entries per run (source identifier = edition id or URL)

UI/Feed Impact
--------------
- Feed groups by date; section chips and events‑only toggle rely on normalized section + article_events
- Source view uses raw_html if present; else streams MinIO PDF

Next Steps
----------
1) Add SECTION_NORMALIZE map to extractor to align with frontend
2) Expand event_parser with time range + venue normalization
3) Optional: add pg_trgm index for fuzzy title dedupe (similar titles across editions)

