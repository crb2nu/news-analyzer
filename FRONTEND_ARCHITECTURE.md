# News Analyzer Frontend Architecture

**Version:** 1.0
**Date:** 2025-11-07
**Stack:** SvelteKit + TypeScript + Static Adapter

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technology Stack](#technology-stack)
3. [Architecture Overview](#architecture-overview)
4. [Component Hierarchy](#component-hierarchy)
5. [Data Flow & State Management](#data-flow--state-management)
6. [UI/UX Design System](#uiux-design-system)
7. [Performance Strategy](#performance-strategy)
8. [File Structure](#file-structure)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Testing Strategy](#testing-strategy)

---

## Executive Summary

This document outlines a modern, production-ready frontend architecture for the News Analyzer summarizer service. The solution leverages **SvelteKit** with static site generation to deliver a fast, accessible, and maintainable user interface that integrates seamlessly with the existing FastAPI backend.

### Key Requirements Met

✅ **Modern, responsive, interactive UI** - Svelte's reactive paradigm
✅ **Real-time search and filtering** - Client-side filtering + API search
✅ **Data visualization** - D3.js integration for trends/analytics
✅ **Desktop-first responsive design** - Progressive enhancement for mobile
✅ **Dark/light theme support** - CSS custom properties + system preference detection
✅ **Accessibility compliance** - ARIA, semantic HTML, keyboard navigation
✅ **Performance optimization** - Static generation, code splitting, lazy loading
✅ **Progressive enhancement** - Works without JavaScript for core content

---

## Technology Stack

### Core Framework
- **SvelteKit 2.x** - Meta-framework with static adapter
- **Svelte 5** - Component framework with fine-grained reactivity
- **TypeScript 5.x** - Type safety and developer experience
- **Vite 5.x** - Build tool and dev server

### Data Visualization
- **D3.js 7.x** - Low-level charting primitives
- **Layer Cake** - Svelte-native charting components
- **Apache ECharts** - Production-ready interactive charts (fallback option)

### UI Components & Styling
- **TailwindCSS 4.x** - Utility-first CSS framework
- **HeadlessUI for Svelte** - Accessible component primitives
- **Lucide Svelte** - Icon library
- **CSS Custom Properties** - Theme variables

### State Management
- **Svelte Stores** - Built-in reactive stores
- **Context API** - Component tree state sharing
- **TanStack Query (Svelte)** - Server state management with caching

### Data Fetching
- **SvelteKit fetch** - SSG-compatible fetch with caching
- **TanStack Query** - Query caching, invalidation, optimistic updates

### Development Tools
- **Vitest** - Unit testing
- **Playwright** - E2E testing
- **ESLint + Prettier** - Code quality
- **Svelte Check** - Type checking

### Build & Deployment
- **@sveltejs/adapter-static** - Static site generation
- **Compression** - Brotli/Gzip for static assets
- **Image optimization** - Sharp for responsive images

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (User)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              SvelteKit Static Site (CDN)                    │
│  ┌─────────────┬──────────────┬──────────────────────────┐ │
│  │   Routes    │  Components  │  Stores & State          │ │
│  │  (Pages)    │  (UI Parts)  │  (Reactive Data)         │ │
│  └─────────────┴──────────────┴──────────────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              API Layer (TanStack Query)                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Query Cache │ Mutation Queue │ Invalidation Logic  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                           │
│  /feed  /search  /analytics  /events  /similar             │
└─────────────────────────────────────────────────────────────┘
```

### Rendering Strategy

**Static Site Generation (SSG) with Client-Side Hydration**

1. **Build Time:**
   - Pre-render shell with initial data
   - Generate static HTML for SEO and fast First Contentful Paint
   - Extract critical CSS inline

2. **Runtime:**
   - Hydrate with Svelte components
   - Fetch dynamic data via API
   - Client-side routing for SPA experience

3. **Data Flow:**
   - Initial load: Static HTML → Hydrate → API fetch
   - Navigation: Client-side routing → Cached or fresh API data
   - Updates: Real-time via API polling or user actions

---

## Component Hierarchy

### Page Components (Routes)

```
src/routes/
├── +layout.svelte              # Root layout (theme, nav, footer)
├── +layout.ts                  # Global load function
├── +page.svelte                # Home/Feed view
├── +page.ts                    # Feed data loading
├── discover/
│   ├── +page.svelte           # Discover/Search view
│   └── +page.ts               # Search data loading
├── events/
│   ├── +page.svelte           # Events calendar view
│   └── +page.ts               # Events data loading
├── analytics/
│   ├── +page.svelte           # Analytics dashboard
│   ├── +page.ts               # Analytics data loading
│   └── [kind]/[key]/
│       └── +page.svelte       # Drill-down timeline view
└── articles/
    └── [id]/
        ├── +page.svelte       # Article detail view
        └── +page.ts           # Article data loading
```

### Feature Components

```
src/lib/components/
├── layout/
│   ├── Header.svelte           # App header with nav
│   ├── Footer.svelte           # App footer
│   ├── Sidebar.svelte          # Collapsible sidebar (filters)
│   └── ThemeToggle.svelte      # Dark/light mode switcher
├── feed/
│   ├── FeedView.svelte         # Main feed container
│   ├── ArticleCard.svelte      # Individual article card
│   ├── ArticleList.svelte      # List of article cards
│   ├── FeedFilters.svelte      # Date/section/search filters
│   ├── SectionChips.svelte     # Quick filter chips
│   └── EmptyState.svelte       # No results placeholder
├── events/
│   ├── EventsCalendar.svelte   # Calendar grid view
│   ├── EventsList.svelte       # List view of events
│   ├── EventCard.svelte        # Individual event card
│   └── EventsTimeline.svelte   # Timeline visualization
├── discover/
│   ├── SearchBox.svelte        # Global search input
│   ├── SearchResults.svelte    # Search results list
│   ├── TrendingList.svelte     # Trending items
│   ├── SimilarArticles.svelte  # Similar articles widget
│   └── DiscoverGrid.svelte     # Layout for discover view
├── analytics/
│   ├── TrendingChart.svelte    # Z-score trend chart
│   ├── TimelineChart.svelte    # Time series line chart
│   ├── SparkLine.svelte        # Inline sparkline
│   ├── MetricsCard.svelte      # KPI card
│   └── AnalyticsDashboard.svelte # Dashboard layout
├── common/
│   ├── Button.svelte           # Reusable button component
│   ├── Card.svelte             # Card container
│   ├── Badge.svelte            # Badge/chip component
│   ├── Input.svelte            # Form input
│   ├── Select.svelte           # Dropdown select
│   ├── Checkbox.svelte         # Checkbox input
│   ├── LoadingSpinner.svelte   # Loading indicator
│   ├── ErrorBoundary.svelte    # Error handling wrapper
│   ├── Modal.svelte            # Modal dialog
│   ├── Tooltip.svelte          # Tooltip component
│   └── Skeleton.svelte         # Skeleton loading state
└── charts/
    ├── LineChart.svelte        # Line chart wrapper
    ├── BarChart.svelte         # Bar chart wrapper
    ├── AreaChart.svelte        # Area chart wrapper
    └── ChartLegend.svelte      # Chart legend component
```

### Component Design Patterns

**1. Compound Components**
```svelte
<Card>
  <Card.Header>
    <Card.Title>Article Title</Card.Title>
  </Card.Header>
  <Card.Body>
    Content...
  </Card.Body>
  <Card.Footer>
    Actions...
  </Card.Footer>
</Card>
```

**2. Render Props (Svelte Slots)**
```svelte
<ArticleList {articles} let:article>
  <ArticleCard {article} />
</ArticleList>
```

**3. Headless Components**
```svelte
<Combobox bind:value={selected}>
  <ComboboxInput placeholder="Search..." />
  <ComboboxOptions>
    {#each items as item}
      <ComboboxOption value={item}>{item.name}</ComboboxOption>
    {/each}
  </ComboboxOptions>
</Combobox>
```

---

## Data Flow & State Management

### State Management Architecture

**1. Server State (API Data)**
- Managed by TanStack Query
- Automatic caching, refetching, and background updates
- Query keys organized by resource type

```typescript
// src/lib/api/queries.ts
export const feedQueries = {
  all: ['feed'] as const,
  dates: () => [...feedQueries.all, 'dates'] as const,
  articles: (date: string, filters: FeedFilters) =>
    [...feedQueries.all, 'articles', date, filters] as const,
};

export function useFeedArticles(date: string, filters: FeedFilters) {
  return createQuery({
    queryKey: feedQueries.articles(date, filters),
    queryFn: () => fetchFeedArticles(date, filters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
```

**2. Client State (UI State)**
- Theme preference (localStorage + Svelte store)
- Filter selections (URL params + Svelte store)
- Read articles (localStorage + Svelte store)
- UI toggles (Svelte stores)

```typescript
// src/lib/stores/ui.ts
import { writable, derived } from 'svelte/store';
import { persisted } from 'svelte-persisted-store';

export const theme = persisted<'light' | 'dark' | 'system'>('theme', 'system');
export const readArticles = persisted<Set<number>>('readArticles', new Set());
export const sidebarOpen = writable<boolean>(false);
export const activeView = writable<'feed' | 'events' | 'discover'>('feed');
```

**3. Form State**
- Managed by component-local state
- Validation with Zod schemas
- Debounced inputs for search

```typescript
// src/lib/schemas/filters.ts
import { z } from 'zod';

export const feedFiltersSchema = z.object({
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  section: z.string().optional(),
  search: z.string().optional(),
  eventsOnly: z.boolean().default(false),
});

export type FeedFilters = z.infer<typeof feedFiltersSchema>;
```

### URL State Synchronization

All filter state is synchronized with URL parameters for shareability:

```typescript
// src/lib/utils/url-state.ts
import { goto } from '$app/navigation';
import { page } from '$app/stores';

export function updateUrlParams(params: Record<string, string | undefined>) {
  const url = new URL(window.location.href);
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      url.searchParams.set(key, value);
    } else {
      url.searchParams.delete(key);
    }
  });
  goto(url.toString(), { replaceState: true, noScroll: true });
}
```

### Data Fetching Strategy

**Query Patterns:**

1. **Pre-fetching on Hover**
```svelte
<script>
  import { queryClient } from '$lib/api/client';
  import { articleQueries } from '$lib/api/queries';

  function prefetchArticle(id: number) {
    queryClient.prefetchQuery({
      queryKey: articleQueries.detail(id),
      queryFn: () => fetchArticle(id),
    });
  }
</script>

<a
  href="/articles/{article.id}"
  on:mouseenter={() => prefetchArticle(article.id)}
>
  {article.title}
</a>
```

2. **Optimistic Updates**
```typescript
const markReadMutation = createMutation({
  mutationFn: (id: number) => markArticleRead(id),
  onMutate: async (id) => {
    // Cancel outgoing refetches
    await queryClient.cancelQueries({ queryKey: feedQueries.all });

    // Snapshot previous value
    const previous = queryClient.getQueryData(feedQueries.articles(date, filters));

    // Optimistically update
    queryClient.setQueryData(feedQueries.articles(date, filters), (old) => ({
      ...old,
      items: old.items.map(item =>
        item.id === id ? { ...item, read: true } : item
      ),
    }));

    return { previous };
  },
  onError: (err, id, context) => {
    // Rollback on error
    queryClient.setQueryData(
      feedQueries.articles(date, filters),
      context.previous
    );
  },
});
```

3. **Infinite Scroll (Pagination)**
```typescript
export function useInfiniteFeed(filters: FeedFilters) {
  return createInfiniteQuery({
    queryKey: feedQueries.infinite(filters),
    queryFn: ({ pageParam = 0 }) =>
      fetchFeedArticles(filters, { offset: pageParam, limit: 20 }),
    getNextPageParam: (lastPage, pages) =>
      lastPage.hasMore ? pages.length * 20 : undefined,
  });
}
```

---

## UI/UX Design System

### Design Tokens

**Color System**
```css
/* src/lib/styles/tokens.css */
:root {
  /* Neutrals */
  --color-neutral-50: #fafafa;
  --color-neutral-100: #f5f5f5;
  --color-neutral-900: #171717;
  --color-neutral-950: #0a0a0a;

  /* Brand */
  --color-primary-500: #3b82f6;
  --color-primary-600: #2563eb;
  --color-primary-700: #1d4ed8;

  /* Semantic */
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --color-info: #06b6d4;

  /* Surface */
  --surface-primary: var(--color-neutral-50);
  --surface-secondary: var(--color-neutral-100);
  --surface-tertiary: var(--color-neutral-200);

  /* Text */
  --text-primary: var(--color-neutral-950);
  --text-secondary: var(--color-neutral-600);
  --text-tertiary: var(--color-neutral-400);

  /* Borders */
  --border-color: var(--color-neutral-200);
  --border-radius: 8px;
  --border-radius-sm: 4px;
  --border-radius-lg: 12px;

  /* Spacing (8pt grid) */
  --spacing-1: 0.5rem;  /* 8px */
  --spacing-2: 1rem;    /* 16px */
  --spacing-3: 1.5rem;  /* 24px */
  --spacing-4: 2rem;    /* 32px */
  --spacing-6: 3rem;    /* 48px */
  --spacing-8: 4rem;    /* 64px */

  /* Typography */
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'Fira Code', monospace;

  --text-xs: 0.75rem;   /* 12px */
  --text-sm: 0.875rem;  /* 14px */
  --text-base: 1rem;    /* 16px */
  --text-lg: 1.125rem;  /* 18px */
  --text-xl: 1.25rem;   /* 20px */
  --text-2xl: 1.5rem;   /* 24px */
  --text-3xl: 1.875rem; /* 30px */

  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);

  /* Transitions */
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 350ms cubic-bezier(0.4, 0, 0.2, 1);
}

[data-theme="dark"] {
  --surface-primary: var(--color-neutral-950);
  --surface-secondary: var(--color-neutral-900);
  --surface-tertiary: var(--color-neutral-800);

  --text-primary: var(--color-neutral-50);
  --text-secondary: var(--color-neutral-400);
  --text-tertiary: var(--color-neutral-600);

  --border-color: var(--color-neutral-800);
}
```

### Typography Scale

```css
/* Headings */
.h1 { font-size: var(--text-3xl); font-weight: 700; line-height: 1.2; }
.h2 { font-size: var(--text-2xl); font-weight: 600; line-height: 1.3; }
.h3 { font-size: var(--text-xl); font-weight: 600; line-height: 1.4; }
.h4 { font-size: var(--text-lg); font-weight: 500; line-height: 1.4; }

/* Body */
.body-lg { font-size: var(--text-lg); line-height: 1.6; }
.body { font-size: var(--text-base); line-height: 1.6; }
.body-sm { font-size: var(--text-sm); line-height: 1.5; }

/* Utility */
.caption { font-size: var(--text-xs); line-height: 1.4; color: var(--text-secondary); }
.overline { font-size: var(--text-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
```

### Layout System

**Grid System**
```css
.container {
  max-width: 1280px;
  margin-inline: auto;
  padding-inline: var(--spacing-4);
}

.grid {
  display: grid;
  gap: var(--spacing-4);
}

.grid-cols-1 { grid-template-columns: repeat(1, minmax(0, 1fr)); }
.grid-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid-cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }

@media (min-width: 768px) {
  .md\:grid-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .md\:grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (min-width: 1024px) {
  .lg\:grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .lg\:grid-cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
```

**Feed Layout (Desktop-First)**
```
┌─────────────────────────────────────────────────────────────────┐
│  Header (fixed)                                                 │
│  [Logo] [Nav: Feed | Events | Discover | Analytics] [Theme]    │
├──────────────┬──────────────────────────────────────────────────┤
│              │  Main Content                                    │
│  Sidebar     │  ┌────────────────────────────────────────────┐ │
│  (Filters)   │  │  Article Card                              │ │
│              │  │  - Title                                   │ │
│  Date        │  │  - Meta (section, date, location)          │ │
│  Section     │  │  - Summary                                 │ │
│  Search      │  │  - Actions (read, share, similar)          │ │
│  Toggles     │  └────────────────────────────────────────────┘ │
│              │  ┌────────────────────────────────────────────┐ │
│              │  │  Article Card                              │ │
│              │  └────────────────────────────────────────────┘ │
│              │  ...                                             │
└──────────────┴──────────────────────────────────────────────────┘
```

### Accessibility Guidelines

**1. Keyboard Navigation**
- All interactive elements focusable via Tab
- Skip links for main content
- Logical tab order
- Escape to close modals/dropdowns
- Arrow keys for navigating lists/menus

**2. ARIA Labels**
```svelte
<button
  aria-label="Toggle dark mode"
  aria-pressed={$theme === 'dark'}
  on:click={toggleTheme}
>
  {#if $theme === 'dark'}
    <IconSun />
  {:else}
    <IconMoon />
  {/if}
</button>

<nav aria-label="Main navigation">
  <ul role="list">
    <li><a href="/" aria-current={$page.url.pathname === '/'}>Feed</a></li>
    <li><a href="/events">Events</a></li>
  </ul>
</nav>
```

**3. Screen Reader Support**
- Live regions for status updates (`aria-live="polite"`)
- Descriptive labels for form inputs
- Alt text for images
- Semantic HTML (`<article>`, `<nav>`, `<main>`)

**4. Color Contrast**
- Minimum 4.5:1 for normal text
- Minimum 3:1 for large text (18px+)
- Focus indicators with 3:1 contrast

**5. Motion Preferences**
```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Performance Strategy

### Build Optimization

**1. Code Splitting**
```typescript
// src/routes/analytics/+page.ts
export const load = async () => {
  // Lazy load chart library only on analytics page
  const { LineChart } = await import('$lib/components/charts/LineChart.svelte');
  return { LineChart };
};
```

**2. Tree Shaking**
- Use named imports from libraries
- Avoid importing entire packages
```typescript
// ❌ Bad
import * as d3 from 'd3';

// ✅ Good
import { scaleLinear, line } from 'd3-scale';
```

**3. Asset Optimization**
- Responsive images with `<picture>` + WebP/AVIF
- SVG for icons (inlined or sprite sheet)
- Font subsetting for web fonts
- Lazy load images below the fold

**4. Critical CSS Extraction**
```javascript
// svelte.config.js
import { extractCss } from '@sveltejs/vite-plugin-svelte';

export default {
  kit: {
    adapter: adapter({
      fallback: '200.html',
      precompress: true, // Brotli + Gzip
    }),
  },
  vitePlugin: {
    experimental: {
      inspector: true,
    },
  },
};
```

### Runtime Optimization

**1. Virtual Scrolling**
For large lists (100+ items), use virtual scrolling:
```svelte
<script>
  import VirtualList from '@sveltejs/svelte-virtual-list';
</script>

<VirtualList items={articles} let:item>
  <ArticleCard article={item} />
</VirtualList>
```

**2. Debouncing & Throttling**
```typescript
import { debounce } from '$lib/utils/timing';

const handleSearch = debounce((query: string) => {
  updateUrlParams({ q: query });
}, 300);
```

**3. Memoization**
```svelte
<script>
  import { derived } from 'svelte/store';

  const filteredArticles = derived(
    [articles, filters],
    ([$articles, $filters]) => filterArticles($articles, $filters)
  );
</script>
```

**4. Request Batching**
```typescript
// Batch multiple analytics requests into single call
const fetchAnalytics = createQuery({
  queryKey: ['analytics', date],
  queryFn: () => Promise.all([
    fetchTrending('section', date),
    fetchTrending('tag', date),
    fetchTrending('entity', date),
  ]),
});
```

### Caching Strategy

**1. TanStack Query Cache**
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 30 * 60 * 1000, // 30 minutes
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});
```

**2. Service Worker (Optional)**
```typescript
// src/service-worker.ts
import { build, files, version } from '$service-worker';

const CACHE_NAME = `cache-${version}`;
const ASSETS = [...build, ...files];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('/api/')) {
    // Network-first for API
    event.respondWith(networkFirst(event.request));
  } else {
    // Cache-first for static assets
    event.respondWith(cacheFirst(event.request));
  }
});
```

**3. Browser Storage**
- Feed preferences: `localStorage`
- Read articles: `localStorage` (with periodic cleanup)
- Theme preference: `localStorage` + CSS variable

### Performance Budget

| Metric | Target |
|--------|--------|
| First Contentful Paint (FCP) | < 1.5s |
| Largest Contentful Paint (LCP) | < 2.5s |
| Time to Interactive (TTI) | < 3.5s |
| Cumulative Layout Shift (CLS) | < 0.1 |
| First Input Delay (FID) | < 100ms |
| Total Bundle Size | < 200KB (gzipped) |
| Initial JS | < 100KB (gzipped) |
| Route-specific JS | < 50KB (gzipped) |

---

## File Structure

```
news-analyzer-frontend/
├── package.json
├── svelte.config.js
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── playwright.config.ts
├── vitest.config.ts
├── .env.example
├── .prettierrc
├── .eslintrc.cjs
├── static/
│   ├── favicon.ico
│   ├── robots.txt
│   ├── manifest.json
│   └── fonts/
│       └── inter-var.woff2
├── src/
│   ├── app.html                # HTML template
│   ├── app.css                 # Global styles
│   ├── hooks.server.ts         # Server hooks
│   ├── hooks.client.ts         # Client hooks
│   ├── routes/
│   │   ├── +layout.svelte
│   │   ├── +layout.ts
│   │   ├── +page.svelte        # Feed view
│   │   ├── +page.ts
│   │   ├── discover/
│   │   │   ├── +page.svelte
│   │   │   └── +page.ts
│   │   ├── events/
│   │   │   ├── +page.svelte
│   │   │   └── +page.ts
│   │   ├── analytics/
│   │   │   ├── +page.svelte
│   │   │   ├── +page.ts
│   │   │   └── [kind]/[key]/
│   │   │       └── +page.svelte
│   │   └── articles/
│   │       └── [id]/
│   │           ├── +page.svelte
│   │           └── +page.ts
│   ├── lib/
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Header.svelte
│   │   │   │   ├── Footer.svelte
│   │   │   │   ├── Sidebar.svelte
│   │   │   │   └── ThemeToggle.svelte
│   │   │   ├── feed/
│   │   │   │   ├── FeedView.svelte
│   │   │   │   ├── ArticleCard.svelte
│   │   │   │   ├── ArticleList.svelte
│   │   │   │   ├── FeedFilters.svelte
│   │   │   │   └── SectionChips.svelte
│   │   │   ├── events/
│   │   │   │   ├── EventsCalendar.svelte
│   │   │   │   ├── EventsList.svelte
│   │   │   │   ├── EventCard.svelte
│   │   │   │   └── EventsTimeline.svelte
│   │   │   ├── discover/
│   │   │   │   ├── SearchBox.svelte
│   │   │   │   ├── SearchResults.svelte
│   │   │   │   ├── TrendingList.svelte
│   │   │   │   └── SimilarArticles.svelte
│   │   │   ├── analytics/
│   │   │   │   ├── TrendingChart.svelte
│   │   │   │   ├── TimelineChart.svelte
│   │   │   │   ├── SparkLine.svelte
│   │   │   │   ├── MetricsCard.svelte
│   │   │   │   └── AnalyticsDashboard.svelte
│   │   │   ├── common/
│   │   │   │   ├── Button.svelte
│   │   │   │   ├── Card.svelte
│   │   │   │   ├── Badge.svelte
│   │   │   │   ├── Input.svelte
│   │   │   │   ├── Select.svelte
│   │   │   │   ├── Checkbox.svelte
│   │   │   │   ├── LoadingSpinner.svelte
│   │   │   │   ├── ErrorBoundary.svelte
│   │   │   │   ├── Modal.svelte
│   │   │   │   ├── Tooltip.svelte
│   │   │   │   └── Skeleton.svelte
│   │   │   └── charts/
│   │   │       ├── LineChart.svelte
│   │   │       ├── BarChart.svelte
│   │   │       ├── AreaChart.svelte
│   │   │       └── ChartLegend.svelte
│   │   ├── api/
│   │   │   ├── client.ts          # Fetch client with error handling
│   │   │   ├── queries.ts         # TanStack Query definitions
│   │   │   └── endpoints.ts       # API endpoint constants
│   │   ├── stores/
│   │   │   ├── ui.ts              # UI state (theme, sidebar, etc.)
│   │   │   ├── preferences.ts     # User preferences
│   │   │   └── read-tracker.ts    # Read articles tracking
│   │   ├── utils/
│   │   │   ├── date.ts            # Date formatting utilities
│   │   │   ├── url-state.ts       # URL param synchronization
│   │   │   ├── timing.ts          # Debounce/throttle
│   │   │   ├── filters.ts         # Article filtering logic
│   │   │   └── validation.ts      # Input validation
│   │   ├── schemas/
│   │   │   ├── article.ts         # Article types
│   │   │   ├── filters.ts         # Filter types
│   │   │   └── analytics.ts       # Analytics types
│   │   ├── styles/
│   │   │   ├── tokens.css         # Design tokens
│   │   │   ├── reset.css          # CSS reset
│   │   │   └── utilities.css      # Utility classes
│   │   └── types/
│   │       ├── api.ts             # API response types
│   │       └── global.d.ts        # Global type declarations
│   └── tests/
│       ├── unit/
│       │   ├── utils/
│       │   │   ├── date.test.ts
│       │   │   └── filters.test.ts
│       │   └── components/
│       │       └── ArticleCard.test.ts
│       └── e2e/
│           ├── feed.spec.ts
│           ├── search.spec.ts
│           └── events.spec.ts
└── docs/
    ├── ARCHITECTURE.md         # This file
    ├── CONTRIBUTING.md
    ├── COMPONENTS.md
    └── API_INTEGRATION.md
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

**Sprint 1.1: Project Setup**
- [ ] Initialize SvelteKit project with TypeScript
- [ ] Configure Tailwind CSS
- [ ] Set up ESLint, Prettier, Svelte Check
- [ ] Configure static adapter
- [ ] Set up Vitest for unit tests
- [ ] Set up Playwright for E2E tests
- [ ] Create design token CSS file
- [ ] Implement theme system (dark/light/system)

**Sprint 1.2: Core Layout & Routing**
- [ ] Create root layout with header/footer
- [ ] Implement responsive navigation
- [ ] Set up routing structure (feed, events, discover, analytics)
- [ ] Create ThemeToggle component
- [ ] Implement basic responsive grid system
- [ ] Add loading states and error boundaries

**Sprint 1.3: API Integration Layer**
- [ ] Set up TanStack Query
- [ ] Create API client with error handling
- [ ] Define query keys and query functions
- [ ] Implement type-safe API response schemas
- [ ] Add request/response interceptors
- [ ] Configure caching strategy

### Phase 2: Feed & Core Features (Week 3-4)

**Sprint 2.1: Feed View**
- [ ] Build FeedView container component
- [ ] Create ArticleCard component
- [ ] Implement ArticleList with virtualization
- [ ] Build FeedFilters (date, section, search)
- [ ] Add SectionChips for quick filtering
- [ ] Implement client-side filtering logic
- [ ] Add empty state component
- [ ] Implement read tracking with localStorage

**Sprint 2.2: Article Detail & Actions**
- [ ] Create article detail page
- [ ] Implement source view integration
- [ ] Add "mark read/unread" functionality
- [ ] Add "copy link" action
- [ ] Implement keyboard navigation (j/k/Enter)
- [ ] Add article sharing functionality
- [ ] Create tooltip component for metadata

**Sprint 2.3: Search & Discovery**
- [ ] Build SearchBox component with debouncing
- [ ] Create SearchResults list view
- [ ] Implement BM25 search integration
- [ ] Build SimilarArticles widget
- [ ] Add search result highlighting
- [ ] Implement search history (optional)

### Phase 3: Events & Analytics (Week 5-6)

**Sprint 3.1: Events View**
- [ ] Create EventsCalendar component
- [ ] Build EventsList view
- [ ] Implement EventCard component
- [ ] Add EventsTimeline visualization
- [ ] Integrate events API endpoint
- [ ] Group events by date
- [ ] Add event filtering (upcoming, past)
- [ ] Link events to source articles

**Sprint 3.2: Analytics Dashboard**
- [ ] Set up chart library (Layer Cake or ECharts)
- [ ] Create TrendingChart (z-score visualization)
- [ ] Build TimelineChart (time series)
- [ ] Implement SparkLine component
- [ ] Create MetricsCard for KPIs
- [ ] Build AnalyticsDashboard layout
- [ ] Add trending sections, tags, entities, topics
- [ ] Implement drill-down views (timeline for specific items)

**Sprint 3.3: Data Visualization**
- [ ] Create reusable LineChart component
- [ ] Build BarChart component
- [ ] Implement AreaChart component
- [ ] Add ChartLegend component
- [ ] Implement responsive chart sizing
- [ ] Add chart interactions (hover, tooltip)
- [ ] Optimize chart rendering performance

### Phase 4: Polish & Optimization (Week 7-8)

**Sprint 4.1: Performance Optimization**
- [ ] Audit bundle size with rollup-plugin-visualizer
- [ ] Implement code splitting for routes
- [ ] Add image lazy loading
- [ ] Optimize fonts (subsetting, preloading)
- [ ] Add service worker for offline support (optional)
- [ ] Implement virtual scrolling for large lists
- [ ] Add prefetching on hover
- [ ] Optimize TanStack Query cache settings

**Sprint 4.2: Accessibility & UX Polish**
- [ ] Audit with axe DevTools
- [ ] Add ARIA labels and roles
- [ ] Implement keyboard navigation
- [ ] Test with screen readers (NVDA, VoiceOver)
- [ ] Ensure color contrast ratios
- [ ] Add focus indicators
- [ ] Implement skip links
- [ ] Add loading skeletons
- [ ] Improve error messages

**Sprint 4.3: Testing & Documentation**
- [ ] Write unit tests for utility functions
- [ ] Write component tests for key components
- [ ] Write E2E tests for critical user flows
- [ ] Document component API (props, events, slots)
- [ ] Create Storybook or component showcase (optional)
- [ ] Write deployment guide
- [ ] Create user guide

### Phase 5: Deployment & Monitoring (Week 9)

**Sprint 5.1: Build & Deployment**
- [ ] Configure build for production
- [ ] Set up CI/CD pipeline (GitHub Actions)
- [ ] Deploy to static hosting (Netlify, Vercel, or Cloudflare Pages)
- [ ] Configure CDN caching
- [ ] Set up custom domain
- [ ] Add SSL certificate
- [ ] Configure redirects and fallbacks

**Sprint 5.2: Monitoring & Analytics**
- [ ] Add web vitals tracking
- [ ] Set up error tracking (Sentry or similar)
- [ ] Add privacy-respecting analytics (Plausible or umami)
- [ ] Create performance monitoring dashboard
- [ ] Set up uptime monitoring
- [ ] Document monitoring setup

---

## Testing Strategy

### Unit Tests (Vitest)

**Test Utilities**
```typescript
// src/tests/utils/date.test.ts
import { describe, it, expect } from 'vitest';
import { formatDate, parseDate } from '$lib/utils/date';

describe('date utilities', () => {
  it('formats ISO date to readable format', () => {
    expect(formatDate('2025-11-07')).toBe('Nov 7, 2025');
  });

  it('parses readable date to ISO format', () => {
    expect(parseDate('Nov 7, 2025')).toBe('2025-11-07');
  });
});
```

**Test Components**
```typescript
// src/tests/unit/components/ArticleCard.test.ts
import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import ArticleCard from '$lib/components/feed/ArticleCard.svelte';

describe('ArticleCard', () => {
  it('renders article title', () => {
    const article = {
      id: 1,
      title: 'Test Article',
      summary: 'Test summary',
    };

    render(ArticleCard, { article });
    expect(screen.getByText('Test Article')).toBeInTheDocument();
  });

  it('shows read indicator when article is read', () => {
    const article = { id: 1, title: 'Test', read: true };
    render(ArticleCard, { article });
    expect(screen.getByRole('article')).toHaveClass('read');
  });
});
```

### Integration Tests

```typescript
// src/tests/integration/feed-filtering.test.ts
import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import FeedView from '$lib/components/feed/FeedView.svelte';

describe('Feed filtering', () => {
  it('filters articles by section', async () => {
    render(FeedView, { articles: mockArticles });

    const sectionSelect = screen.getByLabelText('Filter by section');
    await fireEvent.change(sectionSelect, { target: { value: 'Sports' } });

    expect(screen.getAllByRole('article')).toHaveLength(5);
  });

  it('filters articles by search query', async () => {
    render(FeedView, { articles: mockArticles });

    const searchInput = screen.getByPlaceholderText('Search articles');
    await fireEvent.input(searchInput, { target: { value: 'budget' } });

    expect(screen.getAllByRole('article')).toHaveLength(2);
  });
});
```

### E2E Tests (Playwright)

```typescript
// src/tests/e2e/feed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Feed view', () => {
  test('loads and displays articles', async ({ page }) => {
    await page.goto('/');

    // Wait for articles to load
    await page.waitForSelector('article');

    // Check that articles are displayed
    const articles = await page.locator('article').count();
    expect(articles).toBeGreaterThan(0);
  });

  test('filters articles by section', async ({ page }) => {
    await page.goto('/');

    // Select a section
    await page.selectOption('select[aria-label="Filter by section"]', 'Sports');

    // Verify URL updated
    expect(page.url()).toContain('section=Sports');

    // Verify filtered results
    const sectionLabels = await page.locator('.meta').allTextContents();
    expect(sectionLabels.every(label => label.includes('Sports'))).toBe(true);
  });

  test('marks article as read', async ({ page }) => {
    await page.goto('/');

    const firstArticle = page.locator('article').first();
    await firstArticle.locator('button:has-text("Mark read")').click();

    // Verify visual indicator
    await expect(firstArticle).toHaveClass(/read/);

    // Verify persisted in localStorage
    const readArticles = await page.evaluate(() =>
      localStorage.getItem('readArticles')
    );
    expect(readArticles).toBeTruthy();
  });
});
```

### Visual Regression Tests (Optional)

```typescript
// src/tests/visual/article-card.spec.ts
import { test, expect } from '@playwright/test';

test('ArticleCard visual snapshot', async ({ page }) => {
  await page.goto('/storybook/article-card');
  await expect(page).toHaveScreenshot('article-card-default.png');
});

test('ArticleCard dark mode snapshot', async ({ page }) => {
  await page.goto('/storybook/article-card');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page).toHaveScreenshot('article-card-dark.png');
});
```

---

## API Integration

### Environment Variables

```bash
# .env.example
PUBLIC_API_BASE_URL=http://localhost:8000
PUBLIC_APP_NAME="SW VA News Hub"
PUBLIC_ENABLE_ANALYTICS=false
PUBLIC_SENTRY_DSN=
```

### API Client

```typescript
// src/lib/api/client.ts
import { PUBLIC_API_BASE_URL } from '$env/static/public';

class APIError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message: string
  ) {
    super(message);
    this.name = 'APIError';
  }
}

export async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${PUBLIC_API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new APIError(
      response.status,
      response.statusText,
      `API request failed: ${endpoint}`
    );
  }

  return response.json();
}
```

### Query Definitions

```typescript
// src/lib/api/queries.ts
import { createQuery } from '@tanstack/svelte-query';
import { fetchAPI } from './client';
import type { FeedResponse, FeedFilters } from '$lib/types/api';

export const feedQueries = {
  all: ['feed'] as const,
  dates: () => [...feedQueries.all, 'dates'] as const,
  articles: (date: string, filters: FeedFilters) =>
    [...feedQueries.all, 'articles', date, filters] as const,
};

export function useFeedDates() {
  return createQuery({
    queryKey: feedQueries.dates(),
    queryFn: () => fetchAPI<{ dates: Array<{ date: string; total: number }> }>('/feed/dates'),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useFeedArticles(date: string, filters: FeedFilters) {
  return createQuery({
    queryKey: feedQueries.articles(date, filters),
    queryFn: () => {
      const params = new URLSearchParams({
        date_str: date,
        limit: '50',
        ...(filters.section && { section: filters.section }),
        ...(filters.search && { q: filters.search }),
      });
      return fetchAPI<FeedResponse>(`/feed?${params}`);
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
```

---

## Deployment

### Static Build Configuration

```javascript
// svelte.config.js
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),

  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: '200.html', // SPA fallback for client-side routing
      precompress: true, // Enable Brotli and Gzip compression
      strict: true,
    }),
    prerender: {
      handleHttpError: ({ path, referrer, message }) => {
        // Ignore missing API endpoints during build
        if (path.startsWith('/api/')) {
          return;
        }
        throw new Error(message);
      },
    },
  },
};

export default config;
```

### Deployment Targets

**Netlify**
```toml
# netlify.toml
[build]
  command = "npm run build"
  publish = "build"

[[redirects]]
  from = "/api/*"
  to = "https://your-backend-url.com/:splat"
  status = 200

[[redirects]]
  from = "/*"
  to = "/200.html"
  status = 200

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"

[[headers]]
  for = "/build/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
```

**Vercel**
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "build",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://your-backend-url.com/:path*"
    }
  ],
  "headers": [
    {
      "source": "/build/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    }
  ]
}
```

**Cloudflare Pages**
```toml
# wrangler.toml
name = "news-analyzer"
compatibility_date = "2024-01-01"

[site]
  bucket = "./build"

[[routes]]
  pattern = "/api/*"
  custom_service = "your-backend-worker"
```

---

## Next Steps

1. **Review & Approve Architecture**: Stakeholder review of this document
2. **Set Up Development Environment**: Initialize project, install dependencies
3. **Create Design Mockups**: High-fidelity designs for key views (optional)
4. **Begin Phase 1 Implementation**: Start with project setup and core layout
5. **Iterative Development**: Follow roadmap with weekly sprints
6. **Continuous Testing**: Write tests alongside feature development
7. **User Feedback**: Gather feedback after Phase 2 for early adjustments

---

## Appendix

### Technology Alternatives Considered

| Category | Selected | Alternative | Rationale |
|----------|----------|-------------|-----------|
| Framework | SvelteKit | Next.js, Nuxt | Better performance, simpler API, client preference |
| Styling | Tailwind CSS | CSS Modules, Emotion | Faster development, consistency, great DX |
| Charts | Layer Cake | Recharts, Victory | Svelte-native, flexible, lightweight |
| State | Svelte Stores + TanStack Query | Redux, Zustand | Built-in reactivity, server state separation |
| Testing | Vitest + Playwright | Jest + Cypress | Faster, better DX, modern tooling |

### Resources

- [SvelteKit Documentation](https://kit.svelte.dev/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [TanStack Query for Svelte](https://tanstack.com/query/latest/docs/svelte/overview)
- [Layer Cake Charting](https://layercake.graphics/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Web.dev Performance](https://web.dev/performance/)

---

**Document Status:** Draft v1.0
**Author:** Claude (AI Assistant)
**Last Updated:** 2025-11-07
