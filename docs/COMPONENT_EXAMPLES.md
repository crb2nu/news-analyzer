# Component Implementation Examples

Detailed component examples with TypeScript, accessibility, and best practices.

---

## Table of Contents

1. [Layout Components](#layout-components)
2. [Feed Components](#feed-components)
3. [Common Components](#common-components)
4. [Chart Components](#chart-components)
5. [Form Components](#form-components)

---

## Layout Components

### Header Component

**File:** `src/lib/components/layout/Header.svelte`

```svelte
<script lang="ts">
  import { page } from '$app/stores';
  import ThemeToggle from './ThemeToggle.svelte';
  import { Menu, Search } from 'lucide-svelte';
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher<{ toggleSidebar: void }>();

  let mobileMenuOpen = false;

  const navItems = [
    { href: '/', label: 'Feed', icon: '📰' },
    { href: '/events', label: 'Events', icon: '📅' },
    { href: '/discover', label: 'Discover', icon: '🔍' },
    { href: '/analytics', label: 'Analytics', icon: '📊' },
  ];

  $: currentPath = $page.url.pathname;
</script>

<header class="sticky top-0 z-50 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
  <div class="container mx-auto px-4">
    <div class="flex items-center justify-between h-16">
      <!-- Logo -->
      <div class="flex items-center gap-4">
        <button
          class="lg:hidden p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
          on:click={() => dispatch('toggleSidebar')}
          aria-label="Toggle sidebar"
        >
          <Menu class="w-5 h-5" />
        </button>

        <a href="/" class="flex items-center gap-2">
          <span class="text-2xl">📰</span>
          <span class="text-xl font-bold hidden sm:inline">SW VA News Hub</span>
        </a>
      </div>

      <!-- Desktop Navigation -->
      <nav class="hidden md:flex items-center gap-1" aria-label="Main navigation">
        {#each navItems as item}
          <a
            href={item.href}
            class="px-4 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            class:bg-slate-100={currentPath === item.href}
            class:dark:bg-slate-800={currentPath === item.href}
            aria-current={currentPath === item.href ? 'page' : undefined}
          >
            <span class="mr-2">{item.icon}</span>
            {item.label}
          </a>
        {/each}
      </nav>

      <!-- Theme Toggle -->
      <div class="flex items-center gap-2">
        <ThemeToggle />
      </div>
    </div>

    <!-- Mobile Navigation -->
    {#if mobileMenuOpen}
      <nav class="md:hidden py-4 border-t border-slate-200 dark:border-slate-800" aria-label="Mobile navigation">
        {#each navItems as item}
          <a
            href={item.href}
            class="block px-4 py-3 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
            class:bg-slate-100={currentPath === item.href}
            on:click={() => (mobileMenuOpen = false)}
          >
            <span class="mr-2">{item.icon}</span>
            {item.label}
          </a>
        {/each}
      </nav>
    {/if}
  </div>
</header>

<style>
  /* Optional scoped styles */
</style>
```

### Theme Toggle Component

**File:** `src/lib/components/layout/ThemeToggle.svelte`

```svelte
<script lang="ts">
  import { browser } from '$app/environment';
  import { writable } from 'svelte/store';
  import { Sun, Moon, Monitor } from 'lucide-svelte';

  type Theme = 'light' | 'dark' | 'system';

  const theme = writable<Theme>('system');

  // Initialize from localStorage
  if (browser) {
    const stored = localStorage.getItem('theme') as Theme | null;
    if (stored && ['light', 'dark', 'system'].includes(stored)) {
      theme.set(stored);
    }
  }

  // Apply theme changes
  $: if (browser) {
    localStorage.setItem('theme', $theme);
    applyTheme($theme);
  }

  function applyTheme(mode: Theme) {
    const root = document.documentElement;

    if (mode === 'dark') {
      root.setAttribute('data-theme', 'dark');
      root.classList.add('dark');
    } else if (mode === 'light') {
      root.setAttribute('data-theme', 'light');
      root.classList.remove('dark');
    } else {
      // System preference
      const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      root.setAttribute('data-theme', isDark ? 'dark' : 'light');
      root.classList.toggle('dark', isDark);
    }
  }

  function cycleTheme() {
    theme.update((current) => {
      if (current === 'light') return 'dark';
      if (current === 'dark') return 'system';
      return 'light';
    });
  }

  const icons = {
    light: Sun,
    dark: Moon,
    system: Monitor,
  };

  $: Icon = icons[$theme];
</script>

<button
  on:click={cycleTheme}
  class="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
  aria-label="Toggle theme: {$theme}"
  title="Theme: {$theme}"
>
  <svelte:component this={Icon} class="w-5 h-5" />
</button>
```

---

## Feed Components

### Article Card Component

**File:** `src/lib/components/feed/ArticleCard.svelte`

```svelte
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { ExternalLink, Copy, Eye, EyeOff } from 'lucide-svelte';
  import type { Article } from '$lib/types/api';
  import Badge from '../common/Badge.svelte';
  import Button from '../common/Button.svelte';

  export let article: Article;
  export let read = false;

  const dispatch = createEventDispatcher<{
    toggleRead: number;
    copyLink: number;
  }>();

  function formatDate(date: string | null): string {
    if (!date) return '';
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  }

  function getSummaryParagraphs(summary: string): string[] {
    return summary.split(/\n{2,}/).map(p => p.trim()).filter(Boolean);
  }

  $: paragraphs = article.summary ? getSummaryParagraphs(article.summary) : [];
</script>

<article
  class="card group"
  class:read
  data-article-id={article.id}
  tabindex="0"
  role="article"
  aria-labelledby="article-title-{article.id}"
>
  <!-- Header -->
  <div class="flex items-start justify-between gap-4 mb-3">
    <h2
      id="article-title-{article.id}"
      class="text-xl font-semibold leading-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors"
    >
      {article.title}
    </h2>

    {#if read}
      <Badge variant="secondary" size="sm">Read</Badge>
    {/if}
  </div>

  <!-- Metadata -->
  <div class="flex flex-wrap items-center gap-2 mb-4 text-sm text-slate-600 dark:text-slate-400">
    {#if article.section}
      <Badge>{article.section}</Badge>
    {/if}

    {#if article.location_name}
      <span>📍 {article.location_name}</span>
    {/if}

    {#if article.date_published}
      <span>{formatDate(article.date_published)}</span>
    {/if}

    {#if article.word_count}
      <span>{article.word_count} words</span>
    {/if}

    {#if article.events?.length}
      <Badge variant="accent">
        📅 {article.events.length} {article.events.length === 1 ? 'event' : 'events'}
      </Badge>
    {/if}
  </div>

  <!-- Summary -->
  {#if paragraphs.length > 0}
    <div class="prose dark:prose-invert max-w-none mb-4">
      {#each paragraphs as paragraph}
        <p class="text-slate-700 dark:text-slate-300 mb-3 last:mb-0">
          {paragraph}
        </p>
      {/each}
    </div>
  {:else}
    <p class="text-slate-500 dark:text-slate-500 italic mb-4">
      Summary pending...
    </p>
  {/if}

  <!-- Events (inline preview) -->
  {#if article.events && article.events.length > 0}
    <div class="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-4">
      <strong class="block mb-2">Upcoming Events:</strong>
      <ul class="space-y-1 text-sm">
        {#each article.events.slice(0, 3) as event}
          <li>
            {#if event.start_time}
              <time datetime={event.start_time}>
                {formatDate(event.start_time)}
              </time>
              {#if event.location_name}
                • {event.location_name}
              {/if}
            {:else}
              {event.title || 'Event'}
            {/if}
          </li>
        {/each}
      </ul>
      {#if article.events.length > 3}
        <p class="text-xs text-slate-600 dark:text-slate-400 mt-2">
          +{article.events.length - 3} more
        </p>
      {/if}
    </div>
  {/if}

  <!-- Actions -->
  <div class="flex items-center gap-2 pt-4 border-t border-slate-200 dark:border-slate-700">
    <Button
      href="/articles/{article.id}/source"
      target="_blank"
      rel="noopener noreferrer"
      variant="primary"
      size="sm"
    >
      <ExternalLink class="w-4 h-4 mr-1" />
      Read Full Article
    </Button>

    <Button
      variant="ghost"
      size="sm"
      on:click={() => dispatch('toggleRead', article.id)}
      aria-label={read ? 'Mark as unread' : 'Mark as read'}
    >
      {#if read}
        <EyeOff class="w-4 h-4 mr-1" />
        Mark Unread
      {:else}
        <Eye class="w-4 h-4 mr-1" />
        Mark Read
      {/if}
    </Button>

    <Button
      variant="ghost"
      size="sm"
      on:click={() => dispatch('copyLink', article.id)}
      aria-label="Copy link"
    >
      <Copy class="w-4 h-4 mr-1" />
      Copy Link
    </Button>
  </div>
</article>

<style>
  .card {
    @apply bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6;
    @apply transition-all duration-200;
    @apply hover:shadow-md hover:border-slate-300 dark:hover:border-slate-600;
    @apply focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2;
  }

  .card.read {
    @apply opacity-60;
  }

  .card.read:hover {
    @apply opacity-80;
  }
</style>
```

### Feed Filters Component

**File:** `src/lib/components/feed/FeedFilters.svelte`

```svelte
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Search, X } from 'lucide-svelte';
  import Select from '../common/Select.svelte';
  import Input from '../common/Input.svelte';
  import Checkbox from '../common/Checkbox.svelte';
  import Button from '../common/Button.svelte';

  export let selectedDate: string;
  export let dates: Array<{ date: string; total: number; summarized: number }> = [];
  export let selectedSection: string = '';
  export let sections: Array<{ name: string; count: number }> = [];
  export let searchQuery: string = '';
  export let eventsOnly: boolean = false;
  export let hideRead: boolean = false;

  const dispatch = createEventDispatcher<{
    dateChange: string;
    sectionChange: string;
    searchChange: string;
    eventsOnlyChange: boolean;
    hideReadChange: boolean;
    refresh: void;
    clearSearch: void;
  }>();

  function formatDateOption(date: string, total: number, summarized: number): string {
    const d = new Date(date);
    const formatted = d.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    });
    return `${formatted} (${summarized}/${total})`;
  }
</script>

<div class="filters-container">
  <!-- Date Selection -->
  <div class="filter-group">
    <label for="date-select" class="label">Date</label>
    <Select
      id="date-select"
      value={selectedDate}
      on:change={(e) => dispatch('dateChange', e.detail)}
      aria-label="Select date"
    >
      {#each dates as { date, total, summarized }}
        <option value={date}>
          {formatDateOption(date, total, summarized)}
        </option>
      {/each}
    </Select>
  </div>

  <!-- Section Filter -->
  <div class="filter-group">
    <label for="section-select" class="label">Section</label>
    <Select
      id="section-select"
      value={selectedSection}
      on:change={(e) => dispatch('sectionChange', e.detail)}
      aria-label="Filter by section"
    >
      <option value="">All sections ({sections.reduce((sum, s) => sum + s.count, 0)})</option>
      {#each sections as { name, count }}
        <option value={name}>{name} ({count})</option>
      {/each}
    </Select>
  </div>

  <!-- Search -->
  <div class="filter-group flex-1">
    <label for="search-input" class="label">Search</label>
    <div class="relative">
      <Input
        id="search-input"
        type="search"
        placeholder="Search title or summary..."
        value={searchQuery}
        on:input={(e) => dispatch('searchChange', e.detail)}
        class="pr-10"
      />
      {#if searchQuery}
        <button
          class="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-slate-100 dark:hover:bg-slate-700 rounded"
          on:click={() => dispatch('clearSearch')}
          aria-label="Clear search"
        >
          <X class="w-4 h-4" />
        </button>
      {:else}
        <Search class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
      {/if}
    </div>
  </div>

  <!-- Toggles -->
  <div class="filter-group">
    <Checkbox
      id="events-only"
      checked={eventsOnly}
      on:change={(e) => dispatch('eventsOnlyChange', e.detail)}
    >
      Only articles with events
    </Checkbox>
  </div>

  <div class="filter-group">
    <Checkbox
      id="hide-read"
      checked={hideRead}
      on:change={(e) => dispatch('hideReadChange', e.detail)}
    >
      Hide read articles
    </Checkbox>
  </div>

  <!-- Refresh Button -->
  <div class="filter-group">
    <Button
      variant="secondary"
      on:click={() => dispatch('refresh')}
      aria-label="Refresh feed"
    >
      🔄 Refresh
    </Button>
  </div>
</div>

<style>
  .filters-container {
    @apply flex flex-wrap items-end gap-4 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700;
  }

  .filter-group {
    @apply flex flex-col gap-1;
  }

  .label {
    @apply text-sm font-medium text-slate-700 dark:text-slate-300;
  }

  @media (max-width: 768px) {
    .filter-group {
      @apply w-full;
    }
  }
</style>
```

---

## Common Components

### Button Component

**File:** `src/lib/components/common/Button.svelte`

```svelte
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { HTMLButtonAttributes, HTMLAnchorAttributes } from 'svelte/elements';

  type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
  type Size = 'sm' | 'md' | 'lg';

  interface BaseProps {
    variant?: Variant;
    size?: Size;
    disabled?: boolean;
    loading?: boolean;
    class?: string;
  }

  type ButtonProps = BaseProps & HTMLButtonAttributes;
  type AnchorProps = BaseProps & HTMLAnchorAttributes & { href: string };

  type $$Props = ButtonProps | AnchorProps;

  export let variant: Variant = 'primary';
  export let size: Size = 'md';
  export let disabled: boolean = false;
  export let loading: boolean = false;

  let className: string = '';
  export { className as class };

  const dispatch = createEventDispatcher<{ click: MouseEvent }>();

  const variantClasses: Record<Variant, string> = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
    secondary: 'bg-slate-200 text-slate-900 hover:bg-slate-300 focus:ring-slate-500 dark:bg-slate-700 dark:text-slate-100 dark:hover:bg-slate-600',
    ghost: 'bg-transparent hover:bg-slate-100 dark:hover:bg-slate-800 focus:ring-slate-500',
    danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
  };

  const sizeClasses: Record<Size, string> = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg',
  };

  $: classes = [
    'inline-flex items-center justify-center font-medium rounded-lg',
    'transition-colors duration-200',
    'focus:outline-none focus:ring-2 focus:ring-offset-2',
    'disabled:opacity-50 disabled:cursor-not-allowed',
    variantClasses[variant],
    sizeClasses[size],
    className,
  ].filter(Boolean).join(' ');

  function handleClick(e: MouseEvent) {
    if (!disabled && !loading) {
      dispatch('click', e);
    }
  }
</script>

{#if $$restProps.href}
  <a
    {...$$restProps}
    class={classes}
    aria-disabled={disabled || loading}
    on:click={handleClick}
  >
    {#if loading}
      <svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    {/if}
    <slot />
  </a>
{:else}
  <button
    {...$$restProps}
    type={$$restProps.type || 'button'}
    class={classes}
    {disabled}
    on:click={handleClick}
  >
    {#if loading}
      <svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    {/if}
    <slot />
  </button>
{/if}
```

### Card Component

**File:** `src/lib/components/common/Card.svelte`

```svelte
<script lang="ts" context="module">
  import { setContext, getContext } from 'svelte';

  const CARD_CONTEXT = Symbol('card');

  export interface CardContext {
    variant: 'default' | 'flat' | 'outlined';
  }

  export function setCardContext(context: CardContext) {
    setContext(CARD_CONTEXT, context);
  }

  export function getCardContext(): CardContext | undefined {
    return getContext(CARD_CONTEXT);
  }
</script>

<script lang="ts">
  import type { HTMLAttributes } from 'svelte/elements';

  type Variant = 'default' | 'flat' | 'outlined';

  interface $$Props extends HTMLAttributes<HTMLDivElement> {
    variant?: Variant;
    padding?: boolean;
  }

  export let variant: Variant = 'default';
  export let padding: boolean = true;

  let className: string = '';
  export { className as class };

  setCardContext({ variant });

  const variantClasses: Record<Variant, string> = {
    default: 'bg-white dark:bg-slate-800 shadow-sm border border-slate-200 dark:border-slate-700',
    flat: 'bg-slate-50 dark:bg-slate-900',
    outlined: 'border-2 border-slate-200 dark:border-slate-700',
  };

  $: classes = [
    'rounded-lg',
    variantClasses[variant],
    padding && 'p-6',
    className,
  ].filter(Boolean).join(' ');
</script>

<div {...$$restProps} class={classes}>
  <slot />
</div>
```

**Card.Header.svelte:**
```svelte
<script lang="ts">
  let className: string = '';
  export { className as class };
</script>

<div class="mb-4 {className}">
  <slot />
</div>
```

**Card.Title.svelte:**
```svelte
<script lang="ts">
  let className: string = '';
  export { className as class };
</script>

<h3 class="text-lg font-semibold {className}">
  <slot />
</h3>
```

**Card.Body.svelte:**
```svelte
<script lang="ts">
  let className: string = '';
  export { className as class };
</script>

<div class="{className}">
  <slot />
</div>
```

**Card.Footer.svelte:**
```svelte
<script lang="ts">
  let className: string = '';
  export { className as class };
</script>

<div class="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700 {className}">
  <slot />
</div>
```

### Badge Component

**File:** `src/lib/components/common/Badge.svelte`

```svelte
<script lang="ts">
  type Variant = 'default' | 'primary' | 'secondary' | 'accent' | 'success' | 'warning' | 'danger';
  type Size = 'sm' | 'md' | 'lg';

  export let variant: Variant = 'default';
  export let size: Size = 'md';

  let className: string = '';
  export { className as class };

  const variantClasses: Record<Variant, string> = {
    default: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200',
    primary: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    secondary: 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-200',
    accent: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
    success: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    danger: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  };

  const sizeClasses: Record<Size, string> = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  };

  $: classes = [
    'inline-flex items-center font-medium rounded-full',
    variantClasses[variant],
    sizeClasses[size],
    className,
  ].filter(Boolean).join(' ');
</script>

<span class={classes}>
  <slot />
</span>
```

---

## Chart Components

### Sparkline Component

**File:** `src/lib/components/charts/SparkLine.svelte`

```svelte
<script lang="ts">
  export let values: number[];
  export let width: number = 120;
  export let height: number = 24;
  export let color: string = 'currentColor';
  export let strokeWidth: number = 2;

  $: max = Math.max(...values, 1);
  $: min = Math.min(...values, 0);
  $: range = max - min || 1;

  $: points = values
    .map((value, index) => {
      const x = (index / (values.length - 1 || 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x},${y}`;
    })
    .join(' ');
</script>

<svg {width} {height} class="inline-block align-middle" aria-label="Trend sparkline">
  <polyline
    fill="none"
    stroke={color}
    stroke-width={strokeWidth}
    stroke-linecap="round"
    stroke-linejoin="round"
    points={points}
  />
</svg>
```

### Line Chart Component (Using Layer Cake)

**File:** `src/lib/components/charts/LineChart.svelte`

```svelte
<script lang="ts">
  import { LayerCake, Svg, Html } from 'layercake';
  import { scaleTime, scaleLinear } from 'd3-scale';
  import Line from './Line.svelte';
  import AxisX from './AxisX.svelte';
  import AxisY from './AxisY.svelte';

  export let data: Array<{ x: Date; y: number }>;
  export let xLabel: string = '';
  export let yLabel: string = '';

  $: sortedData = [...data].sort((a, b) => a.x.getTime() - b.x.getTime());
</script>

<div class="chart-container">
  <LayerCake
    padding={{ top: 10, right: 20, bottom: 30, left: 40 }}
    x={d => d.x}
    y={d => d.y}
    xScale={scaleTime()}
    yScale={scaleLinear()}
    data={sortedData}
  >
    <Svg>
      <AxisX {xLabel} />
      <AxisY {yLabel} />
      <Line />
    </Svg>

    <Html>
      <slot />
    </Html>
  </LayerCake>
</div>

<style>
  .chart-container {
    width: 100%;
    height: 300px;
  }
</style>
```

**Line.svelte (inner component):**
```svelte
<script lang="ts">
  import { getContext } from 'svelte';
  import { line } from 'd3-shape';

  const { data, xGet, yGet } = getContext('LayerCake');

  $: path = line()
    .x(d => $xGet(d))
    .y(d => $yGet(d))
  ($data);
</script>

<path
  d={path}
  fill="none"
  stroke="rgb(59, 130, 246)"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
/>
```

---

## Form Components

### Input Component

**File:** `src/lib/components/common/Input.svelte`

```svelte
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { HTMLInputAttributes } from 'svelte/elements';

  interface $$Props extends HTMLInputAttributes {
    error?: string;
  }

  export let value: string = '';
  export let error: string | undefined = undefined;

  let className: string = '';
  export { className as class };

  const dispatch = createEventDispatcher<{
    input: string;
    change: string;
  }>();

  function handleInput(e: Event) {
    const target = e.target as HTMLInputElement;
    value = target.value;
    dispatch('input', value);
  }

  function handleChange(e: Event) {
    const target = e.target as HTMLInputElement;
    dispatch('change', target.value);
  }

  $: classes = [
    'px-3 py-2 border rounded-lg',
    'bg-white dark:bg-slate-800',
    'text-slate-900 dark:text-slate-100',
    'placeholder:text-slate-400 dark:placeholder:text-slate-500',
    'focus:outline-none focus:ring-2 focus:ring-offset-2',
    error
      ? 'border-red-500 focus:ring-red-500'
      : 'border-slate-300 dark:border-slate-700 focus:ring-blue-500',
    'disabled:opacity-50 disabled:cursor-not-allowed',
    className,
  ].filter(Boolean).join(' ');
</script>

<div class="input-wrapper">
  <input
    {...$$restProps}
    {value}
    class={classes}
    on:input={handleInput}
    on:change={handleChange}
    on:focus
    on:blur
  />

  {#if error}
    <p class="mt-1 text-sm text-red-600 dark:text-red-400" role="alert">
      {error}
    </p>
  {/if}
</div>

<style>
  .input-wrapper {
    @apply w-full;
  }
</style>
```

### Select Component

**File:** `src/lib/components/common/Select.svelte`

```svelte
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { HTMLSelectAttributes } from 'svelte/elements';

  interface $$Props extends HTMLSelectAttributes {
    error?: string;
  }

  export let value: string = '';
  export let error: string | undefined = undefined;

  let className: string = '';
  export { className as class };

  const dispatch = createEventDispatcher<{
    change: string;
  }>();

  function handleChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    value = target.value;
    dispatch('change', value);
  }

  $: classes = [
    'px-3 py-2 border rounded-lg',
    'bg-white dark:bg-slate-800',
    'text-slate-900 dark:text-slate-100',
    'focus:outline-none focus:ring-2 focus:ring-offset-2',
    error
      ? 'border-red-500 focus:ring-red-500'
      : 'border-slate-300 dark:border-slate-700 focus:ring-blue-500',
    'disabled:opacity-50 disabled:cursor-not-allowed',
    className,
  ].filter(Boolean).join(' ');
</script>

<div class="select-wrapper">
  <select
    {...$$restProps}
    {value}
    class={classes}
    on:change={handleChange}
    on:focus
    on:blur
  >
    <slot />
  </select>

  {#if error}
    <p class="mt-1 text-sm text-red-600 dark:text-red-400" role="alert">
      {error}
    </p>
  {/if}
</div>

<style>
  .select-wrapper {
    @apply w-full;
  }
</style>
```

### Checkbox Component

**File:** `src/lib/components/common/Checkbox.svelte`

```svelte
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { HTMLInputAttributes } from 'svelte/elements';

  interface $$Props extends Omit<HTMLInputAttributes, 'type'> {
    checked?: boolean;
  }

  export let checked: boolean = false;
  export let id: string;

  let className: string = '';
  export { className as class };

  const dispatch = createEventDispatcher<{
    change: boolean;
  }>();

  function handleChange(e: Event) {
    const target = e.target as HTMLInputElement;
    checked = target.checked;
    dispatch('change', checked);
  }
</script>

<div class="flex items-center gap-2">
  <input
    {...$$restProps}
    type="checkbox"
    {id}
    {checked}
    class="w-4 h-4 rounded border-slate-300 dark:border-slate-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-2 {className}"
    on:change={handleChange}
  />
  <label for={id} class="text-sm text-slate-700 dark:text-slate-300 cursor-pointer">
    <slot />
  </label>
</div>
```

---

## Usage Examples

### Complete Feed Page

**File:** `src/routes/+page.svelte`

```svelte
<script lang="ts">
  import { page } from '$app/stores';
  import { createQuery } from '@tanstack/svelte-query';
  import { getFeedDates, getFeedArticles } from '$lib/api/endpoints/feed';
  import { updateUrlParams } from '$lib/utils/url-state';
  import { readArticles } from '$lib/stores/read-tracker';

  import FeedFilters from '$lib/components/feed/FeedFilters.svelte';
  import ArticleCard from '$lib/components/feed/ArticleCard.svelte';
  import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';

  // Read URL params
  $: selectedDate = $page.url.searchParams.get('date') || '';
  $: selectedSection = $page.url.searchParams.get('section') || '';
  $: searchQuery = $page.url.searchParams.get('q') || '';
  $: eventsOnly = $page.url.searchParams.get('eventsOnly') === '1';
  $: hideRead = $page.url.searchParams.get('hideRead') === '1';

  // Fetch dates
  const datesQuery = createQuery({
    queryKey: ['feed', 'dates'],
    queryFn: () => getFeedDates(14),
  });

  // Auto-select first date
  $: if ($datesQuery.data?.dates.length && !selectedDate) {
    selectedDate = $datesQuery.data.dates[0].date;
    updateUrlParams({ date: selectedDate });
  }

  // Fetch articles
  const articlesQuery = createQuery({
    queryKey: ['feed', 'articles', selectedDate, { section: selectedSection, search: searchQuery }],
    queryFn: () => getFeedArticles(selectedDate, {
      section: selectedSection || undefined,
      search: searchQuery || undefined,
    }),
    enabled: !!selectedDate,
  });

  // Client-side filtering
  $: filteredArticles = $articlesQuery.data?.items.filter(article => {
    if (hideRead && $readArticles.has(article.id)) return false;
    if (eventsOnly && !article.events?.length) return false;
    return true;
  }) || [];

  // Extract sections for filter
  $: sections = $articlesQuery.data?.items.reduce((acc, article) => {
    const section = article.section || 'General';
    acc[section] = (acc[section] || 0) + 1;
    return acc;
  }, {} as Record<string, number>) || {};

  $: sectionOptions = Object.entries(sections).map(([name, count]) => ({
    name,
    count,
  }));

  function handleToggleRead(articleId: number) {
    readArticles.update(set => {
      if (set.has(articleId)) {
        set.delete(articleId);
      } else {
        set.add(articleId);
      }
      return new Set(set);
    });
  }

  async function handleCopyLink(articleId: number) {
    const url = `${window.location.origin}/articles/${articleId}/source`;
    await navigator.clipboard.writeText(url);
    // Show toast notification
  }
</script>

<svelte:head>
  <title>Feed - SW VA News Hub</title>
</svelte:head>

<div class="container mx-auto p-4 max-w-4xl">
  <!-- Filters -->
  {#if $datesQuery.data}
    <FeedFilters
      {selectedDate}
      dates={$datesQuery.data.dates}
      {selectedSection}
      sections={sectionOptions}
      {searchQuery}
      {eventsOnly}
      {hideRead}
      on:dateChange={(e) => updateUrlParams({ date: e.detail })}
      on:sectionChange={(e) => updateUrlParams({ section: e.detail })}
      on:searchChange={(e) => updateUrlParams({ q: e.detail })}
      on:eventsOnlyChange={(e) => updateUrlParams({ eventsOnly: e.detail ? '1' : '' })}
      on:hideReadChange={(e) => updateUrlParams({ hideRead: e.detail ? '1' : '' })}
      on:refresh={() => $articlesQuery.refetch()}
      on:clearSearch={() => updateUrlParams({ q: '' })}
    />
  {/if}

  <!-- Articles -->
  <div class="mt-6">
    {#if $articlesQuery.isLoading}
      <div class="flex justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    {:else if $articlesQuery.error}
      <div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-6 text-center">
        <p class="text-red-800 dark:text-red-200">
          Failed to load articles: {$articlesQuery.error.message}
        </p>
        <button
          class="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
          on:click={() => $articlesQuery.refetch()}
        >
          Try Again
        </button>
      </div>
    {:else if filteredArticles.length === 0}
      <div class="text-center py-12 text-slate-600 dark:text-slate-400">
        <p class="text-lg">No articles found</p>
        <p class="text-sm mt-2">Try adjusting your filters</p>
      </div>
    {:else}
      <div class="space-y-6">
        {#each filteredArticles as article (article.id)}
          <ArticleCard
            {article}
            read={$readArticles.has(article.id)}
            on:toggleRead={(e) => handleToggleRead(e.detail)}
            on:copyLink={(e) => handleCopyLink(e.detail)}
          />
        {/each}
      </div>
    {/if}
  </div>
</div>
```

---

This component examples document provides production-ready implementations with:

- ✅ TypeScript type safety
- ✅ Accessibility (ARIA labels, keyboard nav)
- ✅ Dark mode support
- ✅ Responsive design
- ✅ Reusable patterns
- ✅ Event handling
- ✅ Error states
- ✅ Loading states

Refer to the architecture document for overall system design and API integration guide for data fetching patterns.
