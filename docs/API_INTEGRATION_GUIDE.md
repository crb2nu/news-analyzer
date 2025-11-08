# API Integration Guide

This guide details how the SvelteKit frontend integrates with the FastAPI backend.

---

## API Endpoints Overview

### Base URL
```
Development: http://localhost:8000
Production: https://your-api-domain.com
```

---

## Endpoint Reference

### Feed Endpoints

#### GET `/feed/dates`
Returns recent dates with article counts.

**Parameters:**
- `limit` (optional): Number of dates to return (default: 14)

**Response:**
```json
{
  "dates": [
    {
      "date": "2025-11-07",
      "total": 25,
      "summarized": 23
    }
  ]
}
```

**SvelteKit Integration:**
```typescript
// src/lib/api/endpoints/feed.ts
import { fetchAPI } from '$lib/api/client';

export async function getFeedDates(limit = 14) {
  return fetchAPI<{ dates: FeedDate[] }>(`/feed/dates?limit=${limit}`);
}

// Usage in component
import { createQuery } from '@tanstack/svelte-query';

const datesQuery = createQuery({
  queryKey: ['feed', 'dates'],
  queryFn: () => getFeedDates(14),
  staleTime: 10 * 60 * 1000, // 10 minutes
});
```

#### GET `/feed`
Returns articles with summaries for a specific date.

**Parameters:**
- `date_str` (optional): ISO date string (default: today)
- `limit` (optional): Max articles to return (default: 50)
- `section` (optional): Filter by section name
- `q` (optional): Search query

**Response:**
```json
{
  "date": "2025-11-07",
  "count": 25,
  "items": [
    {
      "id": 123,
      "title": "Article Title",
      "summary": "Article summary...",
      "section": "News",
      "location_name": "Blacksburg, VA",
      "date_published": "2025-11-07T10:30:00Z",
      "word_count": 450,
      "events": [
        {
          "title": "Event Title",
          "start_time": "2025-11-10T18:00:00Z",
          "location_name": "Town Hall"
        }
      ]
    }
  ]
}
```

**SvelteKit Integration:**
```typescript
// src/lib/api/endpoints/feed.ts
export interface FeedFilters {
  section?: string;
  search?: string;
}

export async function getFeedArticles(
  date: string,
  filters: FeedFilters = {},
  limit = 50
) {
  const params = new URLSearchParams({
    date_str: date,
    limit: String(limit),
  });

  if (filters.section) params.set('section', filters.section);
  if (filters.search) params.set('q', filters.search);

  return fetchAPI<FeedResponse>(`/feed?${params}`);
}

// Usage with URL state sync
// src/routes/+page.svelte
<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { derived } from 'svelte/store';

  const filters = derived(page, ($page) => ({
    section: $page.url.searchParams.get('section') || undefined,
    search: $page.url.searchParams.get('q') || undefined,
  }));

  const articlesQuery = createQuery({
    queryKey: derived([page, filters], ([$page, $filters]) => [
      'feed',
      'articles',
      $page.url.searchParams.get('date') || 'today',
      $filters,
    ]),
    queryFn: ({ queryKey }) => getFeedArticles(queryKey[2], queryKey[3]),
  });

  function updateFilters(newFilters: Partial<FeedFilters>) {
    const url = new URL($page.url);
    Object.entries(newFilters).forEach(([key, value]) => {
      if (value) {
        url.searchParams.set(key, value);
      } else {
        url.searchParams.delete(key);
      }
    });
    goto(url, { replaceState: true, noScroll: true });
  }
</script>
```

---

### Search Endpoints

#### GET `/search`
BM25 text search across all articles.

**Parameters:**
- `q` (required): Search query
- `limit` (optional): Max results (default: 20, max: 50)

**Response:**
```json
[
  {
    "article_id": 123,
    "title": "Article Title",
    "section": "News",
    "summary": "Summary text...",
    "score": 0.87
  }
]
```

**SvelteKit Integration:**
```typescript
// src/lib/api/endpoints/search.ts
export async function searchArticles(query: string, limit = 20) {
  const params = new URLSearchParams({
    q: query,
    limit: String(Math.min(limit, 50)),
  });
  return fetchAPI<SearchResult[]>(`/search?${params}`);
}

// Debounced search component
// src/lib/components/discover/SearchBox.svelte
<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { debounce } from '$lib/utils/timing';

  let searchQuery = '';
  let debouncedQuery = '';

  const handleInput = debounce((value: string) => {
    debouncedQuery = value;
  }, 300);

  $: handleInput(searchQuery);

  const searchResults = createQuery({
    queryKey: ['search', debouncedQuery],
    queryFn: () => searchArticles(debouncedQuery),
    enabled: debouncedQuery.length > 2,
  });
</script>

<input
  type="search"
  bind:value={searchQuery}
  placeholder="Search all articles..."
/>

{#if $searchResults.isLoading}
  <LoadingSpinner />
{:else if $searchResults.data}
  <SearchResults results={$searchResults.data} />
{/if}
```

#### GET `/similar`
Find similar articles using vector search.

**Parameters:**
- `id` (required): Article ID
- `limit` (optional): Max results (default: 10, max: 50)

**Response:**
```json
[
  {
    "article_id": 456,
    "title": "Similar Article",
    "section": "News",
    "summary": "Summary...",
    "distance": 0.23
  }
]
```

**SvelteKit Integration:**
```typescript
// src/lib/api/endpoints/search.ts
export async function getSimilarArticles(articleId: number, limit = 10) {
  const params = new URLSearchParams({
    id: String(articleId),
    limit: String(Math.min(limit, 50)),
  });
  return fetchAPI<SimilarArticle[]>(`/similar?${params}`);
}

// Prefetch on hover
// src/lib/components/feed/ArticleCard.svelte
<script lang="ts">
  import { queryClient } from '$lib/api/client';

  export let article: Article;

  function prefetchSimilar() {
    queryClient.prefetchQuery({
      queryKey: ['similar', article.id],
      queryFn: () => getSimilarArticles(article.id),
    });
  }
</script>

<article on:mouseenter={prefetchSimilar}>
  <!-- Article content -->
</article>
```

---

### Analytics Endpoints

#### GET `/analytics/trending`
Returns trending items by kind.

**Parameters:**
- `kind` (required): `section` | `tag` | `entity` | `topic`
- `date_str` (optional): ISO date (default: today)
- `limit` (optional): Max results (default: 20)

**Response:**
```json
[
  {
    "kind": "section",
    "key": "Sports",
    "score": 15.5,
    "zscore": 2.3,
    "details": {}
  }
]
```

**SvelteKit Integration:**
```typescript
// src/lib/api/endpoints/analytics.ts
export type TrendingKind = 'section' | 'tag' | 'entity' | 'topic';

export async function getTrending(
  kind: TrendingKind,
  date?: string,
  limit = 20
) {
  const params = new URLSearchParams({
    kind,
    limit: String(limit),
  });
  if (date) params.set('date_str', date);

  return fetchAPI<TrendingItem[]>(`/analytics/trending?${params}`);
}

// Multi-kind trending dashboard
// src/routes/analytics/+page.svelte
<script lang="ts">
  const kinds: TrendingKind[] = ['section', 'tag', 'entity', 'topic'];

  const trendingQueries = kinds.map((kind) =>
    createQuery({
      queryKey: ['trending', kind, date],
      queryFn: () => getTrending(kind, date),
    })
  );
</script>

<div class="grid grid-cols-2 gap-4">
  {#each kinds as kind, i}
    <TrendingCard
      {kind}
      items={$trendingQueries[i].data}
      loading={$trendingQueries[i].isLoading}
    />
  {/each}
</div>
```

#### GET `/analytics/timeline`
Returns time series data for a specific item.

**Parameters:**
- `kind` (required): Item kind
- `key` (required): Item key
- `days` (optional): Days of history (default: 30)

**Response:**
```json
[
  {
    "date": "2025-11-01",
    "count": 5,
    "sum_score": 12.5
  },
  {
    "date": "2025-11-02",
    "count": 8,
    "sum_score": 18.3
  }
]
```

**SvelteKit Integration:**
```typescript
// src/lib/api/endpoints/analytics.ts
export async function getTimeline(
  kind: TrendingKind,
  key: string,
  days = 30
) {
  const params = new URLSearchParams({
    kind,
    key,
    days: String(days),
  });
  return fetchAPI<TimelineData[]>(`/analytics/timeline?${params}`);
}

// Timeline chart component
// src/lib/components/analytics/TimelineChart.svelte
<script lang="ts">
  export let kind: TrendingKind;
  export let itemKey: string;

  const timelineQuery = createQuery({
    queryKey: ['timeline', kind, itemKey],
    queryFn: () => getTimeline(kind, itemKey, 30),
  });

  $: chartData = $timelineQuery.data?.map(d => ({
    x: new Date(d.date),
    y: d.count,
  })) || [];
</script>

{#if $timelineQuery.data}
  <LineChart data={chartData} />
{/if}
```

---

### Events Endpoints

#### GET `/events`
Returns upcoming community events.

**Parameters:**
- `days` (optional): Days ahead to query (default: 30)

**Response:**
```json
{
  "days": 30,
  "events": {
    "2025-11-10": [
      {
        "id": 1,
        "title": "Town Council Meeting",
        "start_time": "2025-11-10T18:00:00Z",
        "location_name": "Town Hall",
        "description": "Monthly meeting...",
        "article_id": 123
      }
    ]
  }
}
```

**SvelteKit Integration:**
```typescript
// src/lib/api/endpoints/events.ts
export async function getEvents(days = 30) {
  const params = new URLSearchParams({ days: String(days) });
  return fetchAPI<EventsResponse>(`/events?${params}`);
}

// Events calendar component
// src/routes/events/+page.svelte
<script lang="ts">
  const eventsQuery = createQuery({
    queryKey: ['events', 30],
    queryFn: () => getEvents(30),
    staleTime: 15 * 60 * 1000, // 15 minutes
  });

  $: eventsByDate = $eventsQuery.data?.events || {};
  $: sortedDates = Object.keys(eventsByDate).sort();
</script>

{#each sortedDates as date}
  <section>
    <h3>{formatDate(date)}</h3>
    <EventsList events={eventsByDate[date]} />
  </section>
{/each}
```

---

### Article Endpoints

#### GET `/articles/{id}/source`
Returns original article source HTML.

**Response:**
HTML page with article content, summary, and events.

**SvelteKit Integration:**
```typescript
// Open in new tab (browser handles rendering)
<a
  href="/articles/{article.id}/source"
  target="_blank"
  rel="noopener noreferrer"
>
  Read full article ↗
</a>

// Or embed in iframe (if same-origin)
<iframe src="/articles/{article.id}/source" title={article.title} />
```

---

## Error Handling

### API Error Types

```typescript
// src/lib/api/client.ts
export class APIError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public detail?: string
  ) {
    super(`API Error ${status}: ${statusText}`);
    this.name = 'APIError';
  }
}

export async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${PUBLIC_API_BASE_URL}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const detail = await response.text().catch(() => '');
      throw new APIError(response.status, response.statusText, detail);
    }

    return response.json();
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }
    // Network error
    throw new APIError(0, 'Network Error', String(error));
  }
}
```

### Error Handling in Components

```svelte
<!-- src/lib/components/common/ErrorBoundary.svelte -->
<script lang="ts">
  import type { QueryObserverResult } from '@tanstack/svelte-query';

  export let query: QueryObserverResult;
  export let retry: () => void;
</script>

{#if query.isError}
  <div class="error-container">
    <h3>Something went wrong</h3>
    <p>{query.error?.message || 'An unexpected error occurred'}</p>
    <button on:click={retry}>Try again</button>
  </div>
{:else}
  <slot />
{/if}
```

```svelte
<!-- Usage -->
<script lang="ts">
  const articlesQuery = useFeedArticles(date, filters);
</script>

<ErrorBoundary query={$articlesQuery} retry={() => $articlesQuery.refetch()}>
  <ArticleList articles={$articlesQuery.data?.items || []} />
</ErrorBoundary>
```

---

## Caching Strategy

### TanStack Query Configuration

```typescript
// src/lib/api/client.ts
import { QueryClient } from '@tanstack/svelte-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stale time: how long data is considered fresh
      staleTime: 5 * 60 * 1000, // 5 minutes

      // Cache time: how long unused data stays in memory
      cacheTime: 30 * 60 * 1000, // 30 minutes

      // Retry failed requests
      retry: 2,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

      // Don't refetch on window focus (can be noisy)
      refetchOnWindowFocus: false,

      // Refetch on reconnect
      refetchOnReconnect: true,
    },
  },
});
```

### Cache Invalidation

```typescript
// Invalidate after mutation
import { queryClient } from '$lib/api/client';

async function markArticleRead(id: number) {
  await updateReadStatus(id);

  // Invalidate relevant queries
  queryClient.invalidateQueries({ queryKey: ['feed'] });
}

// Invalidate specific query
queryClient.invalidateQueries({
  queryKey: ['feed', 'articles', date],
});

// Remove from cache entirely
queryClient.removeQueries({ queryKey: ['search', oldQuery] });

// Manually update cache (optimistic update)
queryClient.setQueryData(['feed', 'articles', date], (old) => ({
  ...old,
  items: old.items.map(item =>
    item.id === id ? { ...item, read: true } : item
  ),
}));
```

---

## Rate Limiting & Retry Logic

### Client-Side Rate Limiting

```typescript
// src/lib/utils/rate-limiter.ts
export class RateLimiter {
  private queue: Array<() => Promise<any>> = [];
  private processing = false;

  constructor(
    private requestsPerSecond: number,
    private burstSize: number = requestsPerSecond
  ) {}

  async enqueue<T>(fn: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.queue.push(async () => {
        try {
          const result = await fn();
          resolve(result);
        } catch (error) {
          reject(error);
        }
      });
      this.process();
    });
  }

  private async process() {
    if (this.processing) return;
    this.processing = true;

    while (this.queue.length > 0) {
      const batch = this.queue.splice(0, this.burstSize);
      await Promise.all(batch.map((fn) => fn()));
      await this.sleep(1000 / this.requestsPerSecond);
    }

    this.processing = false;
  }

  private sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// Usage
const rateLimiter = new RateLimiter(10); // 10 requests/second

export async function fetchWithRateLimit<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  return rateLimiter.enqueue(() => fetchAPI<T>(endpoint, options));
}
```

---

## WebSocket Support (Future)

For real-time updates, the backend could add WebSocket support:

```typescript
// src/lib/api/websocket.ts
export class NewsWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(private url: string) {}

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.reconnect();
    };
  }

  private handleMessage(data: any) {
    if (data.type === 'article_updated') {
      // Invalidate feed cache
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    }
  }

  private reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000);
      setTimeout(() => this.connect(), delay);
    }
  }

  disconnect() {
    this.ws?.close();
  }
}
```

---

## Testing API Integration

### Mock API Responses

```typescript
// src/tests/mocks/api.ts
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const mockArticles = [
  {
    id: 1,
    title: 'Test Article',
    summary: 'Test summary',
    section: 'News',
  },
];

export const handlers = [
  rest.get('/feed/dates', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        dates: [
          { date: '2025-11-07', total: 10, summarized: 8 },
        ],
      })
    );
  }),

  rest.get('/feed', (req, res, ctx) => {
    const date = req.url.searchParams.get('date_str');
    const section = req.url.searchParams.get('section');

    let items = mockArticles;
    if (section) {
      items = items.filter((a) => a.section === section);
    }

    return res(
      ctx.status(200),
      ctx.json({ date, count: items.length, items })
    );
  }),
];

export const server = setupServer(...handlers);
```

```typescript
// src/tests/setup.ts
import { beforeAll, afterEach, afterAll } from 'vitest';
import { server } from './mocks/api';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### Integration Tests

```typescript
// src/tests/integration/feed-api.test.ts
import { describe, it, expect } from 'vitest';
import { getFeedArticles } from '$lib/api/endpoints/feed';

describe('Feed API', () => {
  it('fetches articles for a date', async () => {
    const result = await getFeedArticles('2025-11-07');
    expect(result.items).toHaveLength(10);
  });

  it('filters articles by section', async () => {
    const result = await getFeedArticles('2025-11-07', { section: 'Sports' });
    expect(result.items.every((a) => a.section === 'Sports')).toBe(true);
  });
});
```

---

## Production Considerations

### CORS Configuration

Ensure backend allows frontend origin:

```python
# Backend: summarizer/api.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Dev
        "https://your-frontend.com",  # Production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### API Versioning

```typescript
// Support multiple API versions
const API_VERSION = 'v1';
const API_BASE_URL = `${PUBLIC_API_BASE_URL}/${API_VERSION}`;
```

### Request Timeout

```typescript
export async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit & { timeout?: number }
): Promise<T> {
  const timeout = options?.timeout || 30000; // 30 seconds

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}
```

---

## Summary

This integration guide provides:
- Complete API endpoint documentation
- SvelteKit integration patterns
- Error handling strategies
- Caching and performance optimization
- Testing approaches
- Production considerations

Refer to the [FRONTEND_ARCHITECTURE.md](../FRONTEND_ARCHITECTURE.md) for overall architecture and the component documentation for UI implementation details.
