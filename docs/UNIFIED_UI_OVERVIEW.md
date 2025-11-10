# Unified Insights Workspace

**Date:** 2025-11-10  \
**Owner:** Frontend  \
**Scope:** Browsing, discovery, and analytics experience inside the News Analyzer frontend.

## 1. Context & Findings
- Current UI splits browsing (`/`), discovery (`/discover`), analytics (`/analytics`), and manual browsing (`/browse`) across separate full pages. Switching context forces full page reloads and duplicates filtering/search logic.
- Feed filters (date, section, keyword, events) already exist but are isolated from analytics insights (trending sections, tags) and discovery features (BM25 search, similar articles, topic graphs).
- Users need a single workspace that highlights “what matters right now” (analytics), lets them scan and triage summaries (browsing), and dig deeper when something stands out (discovery) without losing their place.

## 2. Goals
1. **Unify** browsing, discovery, and analytics into a single responsive view surfaced at the home route.
2. **Cross-link filters** so actions taken in insights panels (e.g., clicking a trending section) immediately refine the article list.
3. **Preserve context** by keeping article filters and discovery controls synchronized via URL params and shared stores.
4. **Highlight signals** via compact KPIs, sparklines, and network snippets without overwhelming the reading experience.

## 3. Layout Overview
```
┌─────────────┬──────────────────────────────────────────────┬──────────────┐
│ Filter Rail │  Article Stream (browse)                     │  Insights    │
│ (Date,      │  - Feed filters + stats                      │  - Trending  │
│ sections,   │  - Article cards w/ quick actions            │  - Global    │
│ toggles)    │  - Inline timeline / metrics                 │    search    │
│             │                                              │  - Similar   │
│             │                                              │    articles  │
│             │                                              │  - Mini net  │
└─────────────┴──────────────────────────────────────────────┴──────────────┘
```
- **Filter Rail (left, ~280px):** stacked controls for date selection, section chips, text filter, and toggles (events-only, hide read) plus quick stats.
- **Article Stream (center, fluid):** retains `ArticleCard` list, but adds hero summary + timeline hook for the selected focus (date/section/trend).
- **Insights & Discovery (right, ~360px):** trending cards, BM25 search with action buttons, similar articles drawer, and a compact topic/entity network visualization reused from the Discover page.

## 4. Interaction Model
| Action | Result |
|--------|--------|
| Selecting a date or section from the filter rail | Updates URL params (`date`, `section`) and refetches feed data as before.
| Clicking a trending section/entity | Dispatches a `select` event that either sets `selectedSection` or populates the feed search query so browsing and analytics stay in sync.
| Running a global search | Shows ranked BM25 results; “Open Source” launches the original article while “Similar” pins the vector-similar list in place for side-by-side review.
| Choosing a similar article | Highlights that article inside the main article stream (scroll into view) and keeps a summary pill in the insights column.
| Switching focus cards | Re-drives the inline timeline chart (via `/analytics/timeline`) without leaving the page.

## 5. Data & State
- **Feed queries:** `getFeedDates`, `getFeedArticles` (unchanged) keyed by selected date and section.
- **Insights queries:** `getTrending(kind)` for `section`, `tag`, `entity`; `getTimeline(kind, key)` for the active trending focus; derived stats computed locally (`computeArticleStats`).
- **Discovery queries:** debounced `searchArticles(query)` and `getSimilarArticles(articleId)` when user explores specific stories.
- **Network sample:** reuse `getTrending('entity')` + `getTrending('topic')` results to seed `NetworkGraph` data for lightweight relationship exploration.

## 6. Implementation Notes
- Add `workspace` components (`FilterPanel`, `InsightsPanel`, `SearchPanel`, `StatCard`) under `src/lib/components/workspace` to keep layout-specific UI isolated.
- Extend `TrendCard` with a `select` event and optional relative progress bars so other views (discover, analytics) share the same visualization primitives.
- Promote the new workspace to the default home route; legacy dedicated pages remain for deep dives but are reachable via nav.
- Introduce small utilities (`computeArticleStats`, `buildInsightLinks`) with unit tests to keep derived metrics and graph edges deterministic.
- Network graph data now merges topics, entities, and tags with deterministic link generation for stable force layouts.

## 7. Acceptance Criteria
- Home route renders the unified layout with all three pillars visible on desktop and stacked on mobile.
- Filters propagate across browsing + insights (e.g., clicking a trending section updates the article list).
- Search, similar-article, and timeline panels function without navigation.
- Basic vitest coverage exists for the new stats helper.
- Documentation (README + this note) describes the new experience.
