# Quick Start Guide - News Analyzer Frontend

Get the SvelteKit frontend up and running in minutes.

---

## Prerequisites

- **Node.js** 20.x or later
- **npm** 10.x or later (or pnpm/yarn)
- **Git**
- Backend API running at `http://localhost:8000`

---

## Installation

### 1. Create New SvelteKit Project

```bash
# Navigate to project root
cd news-analyzer

# Create frontend directory
npm create svelte@latest frontend

# Follow prompts:
# ✔ Which Svelte app template? › SvelteKit demo app
# ✔ Add type checking with TypeScript? › Yes, using TypeScript syntax
# ✔ Select additional options › ESLint, Prettier, Playwright, Vitest

cd frontend
```

### 2. Install Dependencies

```bash
# Core dependencies
npm install

# Add TailwindCSS
npx svelte-add@latest tailwindcss
npm install

# Add TanStack Query for data fetching
npm install @tanstack/svelte-query

# Add additional utilities
npm install clsx tailwind-merge
npm install -D @sveltejs/adapter-static

# Add charting library
npm install layercake d3-scale d3-shape d3-array

# Add icons
npm install lucide-svelte

# Add form validation
npm install zod

# Add local storage persistence
npm install svelte-persisted-store
```

### 3. Configure Project

#### Update `svelte.config.js`

```javascript
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),

  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: '200.html',
      precompress: true,
      strict: true,
    }),
    alias: {
      $lib: './src/lib',
    },
  },
};

export default config;
```

#### Create `.env` file

```bash
# .env
PUBLIC_API_BASE_URL=http://localhost:8000
PUBLIC_APP_NAME="SW VA News Hub"
```

#### Update `vite.config.ts`

```typescript
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}'],
    environment: 'jsdom',
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
```

---

## Project Structure Setup

### Create Core Directories

```bash
mkdir -p src/lib/{api,components,stores,utils,types,styles,schemas}
mkdir -p src/lib/components/{layout,feed,events,discover,analytics,common,charts}
mkdir -p src/tests/{unit,integration,e2e}
```

### Create Base Files

#### API Client (`src/lib/api/client.ts`)

```typescript
import { PUBLIC_API_BASE_URL } from '$env/static/public';

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
    if (error instanceof APIError) throw error;
    throw new APIError(0, 'Network Error', String(error));
  }
}
```

#### Query Client Setup (`src/lib/api/query-client.ts`)

```typescript
import { QueryClient } from '@tanstack/svelte-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 30 * 60 * 1000, // 30 minutes
      retry: 2,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
  },
});
```

#### Root Layout (`src/routes/+layout.svelte`)

```svelte
<script lang="ts">
  import { QueryClientProvider } from '@tanstack/svelte-query';
  import { queryClient } from '$lib/api/query-client';
  import '../app.css';
</script>

<QueryClientProvider client={queryClient}>
  <div class="app">
    <slot />
  </div>
</QueryClientProvider>
```

#### Global Styles (`src/app.css`)

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* Color tokens */
    --color-primary: 59 130 246; /* blue-500 */
    --color-text: 15 23 42; /* slate-900 */
    --color-bg: 255 255 255;
    --color-border: 226 232 240; /* slate-200 */
  }

  [data-theme='dark'] {
    --color-text: 248 250 252; /* slate-50 */
    --color-bg: 15 23 42; /* slate-900 */
    --color-border: 51 65 85; /* slate-700 */
  }

  body {
    @apply bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-50;
    font-family: 'Inter', system-ui, sans-serif;
  }
}
```

#### Tailwind Config (`tailwind.config.ts`)

```typescript
import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        primary: 'rgb(var(--color-primary) / <alpha-value>)',
      },
    },
  },
  plugins: [],
} satisfies Config;
```

---

## Create Your First Page

### Feed Page (`src/routes/+page.svelte`)

```svelte
<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { fetchAPI } from '$lib/api/client';

  interface FeedDate {
    date: string;
    total: number;
    summarized: number;
  }

  const datesQuery = createQuery({
    queryKey: ['feed', 'dates'],
    queryFn: () => fetchAPI<{ dates: FeedDate[] }>('/feed/dates'),
  });

  let selectedDate = '';

  $: if ($datesQuery.data?.dates.length && !selectedDate) {
    selectedDate = $datesQuery.data.dates[0].date;
  }

  interface Article {
    id: number;
    title: string;
    summary: string;
    section: string;
  }

  const articlesQuery = createQuery({
    queryKey: ['feed', 'articles', selectedDate],
    queryFn: () =>
      fetchAPI<{ items: Article[] }>(`/feed?date_str=${selectedDate}`),
    enabled: !!selectedDate,
  });
</script>

<div class="container mx-auto p-4">
  <header class="mb-8">
    <h1 class="text-3xl font-bold mb-2">SW VA News Hub</h1>
    <p class="text-slate-600 dark:text-slate-400">
      Daily highlights from Southwest Virginia
    </p>
  </header>

  <div class="mb-4">
    <label for="date-select" class="block text-sm font-medium mb-2">
      Select Date
    </label>
    <select
      id="date-select"
      bind:value={selectedDate}
      class="px-3 py-2 border border-slate-300 dark:border-slate-700 rounded-lg"
    >
      {#if $datesQuery.data}
        {#each $datesQuery.data.dates as { date, total, summarized }}
          <option value={date}>
            {new Date(date).toLocaleDateString()} ({summarized}/{total})
          </option>
        {/each}
      {/if}
    </select>
  </div>

  {#if $articlesQuery.isLoading}
    <p class="text-slate-600">Loading articles...</p>
  {:else if $articlesQuery.error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4">
      <p class="text-red-800">Error: {$articlesQuery.error.message}</p>
    </div>
  {:else if $articlesQuery.data}
    <div class="space-y-4">
      {#each $articlesQuery.data.items as article (article.id)}
        <article class="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
          <h2 class="text-xl font-semibold mb-2">{article.title}</h2>
          {#if article.section}
            <span class="inline-block px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded mb-3">
              {article.section}
            </span>
          {/if}
          <p class="text-slate-700 dark:text-slate-300">{article.summary}</p>
          <a
            href="/articles/{article.id}/source"
            target="_blank"
            rel="noopener"
            class="inline-block mt-4 text-blue-600 dark:text-blue-400 hover:underline"
          >
            Read full article →
          </a>
        </article>
      {/each}
    </div>
  {/if}
</div>
```

---

## Run Development Server

```bash
npm run dev -- --open
```

Visit `http://localhost:5173` to see your app!

---

## Build for Production

```bash
# Build static site
npm run build

# Preview production build
npm run preview
```

The built site will be in the `build/` directory, ready to deploy to any static hosting service.

---

## Next Steps

### 1. Add More Features

**Implement Search:**
```bash
# Create search page
mkdir src/routes/discover
touch src/routes/discover/+page.svelte
```

```svelte
<!-- src/routes/discover/+page.svelte -->
<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { fetchAPI } from '$lib/api/client';

  let query = '';
  let debouncedQuery = '';

  function debounce(fn: (value: string) => void, delay: number) {
    let timeout: ReturnType<typeof setTimeout>;
    return (value: string) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => fn(value), delay);
    };
  }

  const handleInput = debounce((value) => {
    debouncedQuery = value;
  }, 300);

  $: handleInput(query);

  const searchQuery = createQuery({
    queryKey: ['search', debouncedQuery],
    queryFn: () => fetchAPI(`/search?q=${debouncedQuery}`),
    enabled: debouncedQuery.length > 2,
  });
</script>

<div class="container mx-auto p-4">
  <h1 class="text-3xl font-bold mb-4">Search Articles</h1>

  <input
    type="search"
    bind:value={query}
    placeholder="Search all articles..."
    class="w-full px-4 py-2 border rounded-lg"
  />

  {#if $searchQuery.data}
    <div class="mt-4 space-y-4">
      {#each $searchQuery.data as result}
        <div class="border rounded-lg p-4">
          <h3 class="font-semibold">{result.title}</h3>
          <p class="text-sm text-slate-600">{result.summary}</p>
        </div>
      {/each}
    </div>
  {/if}
</div>
```

**Add Theme Toggle:**
```svelte
<!-- src/lib/components/ThemeToggle.svelte -->
<script lang="ts">
  import { browser } from '$app/environment';
  import { writable } from 'svelte/store';

  type Theme = 'light' | 'dark' | 'system';

  const theme = writable<Theme>('system');

  if (browser) {
    const stored = localStorage.getItem('theme') as Theme;
    if (stored) theme.set(stored);

    theme.subscribe((value) => {
      localStorage.setItem('theme', value);
      const root = document.documentElement;

      if (value === 'dark') {
        root.setAttribute('data-theme', 'dark');
      } else if (value === 'light') {
        root.setAttribute('data-theme', 'light');
      } else {
        root.removeAttribute('data-theme');
      }
    });
  }

  function toggleTheme() {
    theme.update((current) => {
      if (current === 'light') return 'dark';
      if (current === 'dark') return 'system';
      return 'light';
    });
  }
</script>

<button
  on:click={toggleTheme}
  class="px-3 py-2 rounded-lg border"
  aria-label="Toggle theme"
>
  {#if $theme === 'light'}
    ☀️ Light
  {:else if $theme === 'dark'}
    🌙 Dark
  {:else}
    🌗 System
  {/if}
</button>
```

### 2. Set Up Testing

**Create First Test:**
```typescript
// src/tests/unit/utils/date.test.ts
import { describe, it, expect } from 'vitest';

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString();
}

describe('formatDate', () => {
  it('formats ISO date string', () => {
    expect(formatDate('2025-11-07')).toBeTruthy();
  });
});
```

**Run Tests:**
```bash
npm run test:unit
```

### 3. Add E2E Tests

```typescript
// src/tests/e2e/feed.spec.ts
import { test, expect } from '@playwright/test';

test('displays articles on feed page', async ({ page }) => {
  await page.goto('/');

  await page.waitForSelector('article');
  const articles = await page.locator('article').count();
  expect(articles).toBeGreaterThan(0);
});
```

**Run E2E Tests:**
```bash
npm run test:e2e
```

### 4. Deploy

**Deploy to Netlify:**
```bash
# Install Netlify CLI
npm install -g netlify-cli

# Build
npm run build

# Deploy
netlify deploy --prod --dir=build
```

**Deploy to Vercel:**
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel --prod
```

---

## Troubleshooting

### API Connection Issues

If you can't connect to the backend:

1. Ensure backend is running: `curl http://localhost:8000/health`
2. Check CORS settings in backend
3. Verify `.env` file has correct `PUBLIC_API_BASE_URL`

### Build Errors

```bash
# Clear cache and reinstall
rm -rf node_modules .svelte-kit
npm install

# Check TypeScript
npm run check
```

### Hot Reload Not Working

```bash
# Restart dev server
npm run dev -- --open --force
```

---

## Resources

- [SvelteKit Documentation](https://kit.svelte.dev/docs)
- [TanStack Query Docs](https://tanstack.com/query/latest/docs/svelte/overview)
- [Tailwind CSS Docs](https://tailwindcss.com/docs)
- [Full Architecture Document](../FRONTEND_ARCHITECTURE.md)
- [API Integration Guide](./API_INTEGRATION_GUIDE.md)

---

## Summary

You now have:
- ✅ SvelteKit project with TypeScript
- ✅ TailwindCSS for styling
- ✅ TanStack Query for data fetching
- ✅ Basic feed page displaying articles
- ✅ API integration with backend
- ✅ Dark mode support
- ✅ Testing setup

Continue building by following the [Implementation Roadmap](../FRONTEND_ARCHITECTURE.md#implementation-roadmap) in the architecture document!
