<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { browseArticles, getFacets, type BrowseFilters } from '$lib/api/endpoints';
  import Card from '$lib/components/common/Card.svelte';
  import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';
  import Button from '$lib/components/common/Button.svelte';
  import Input from '$lib/components/common/Input.svelte';
  import Select from '$lib/components/common/Select.svelte';

  const today = new Date().toISOString().slice(0,10);
  const thirtyDaysAgo = new Date(Date.now() - 29*24*3600*1000).toISOString().slice(0,10);

  let filters: BrowseFilters = {
    date_from: thirtyDaysAgo,
    date_to: today,
    publications: [],
    sections: [],
    tags: [],
    q: '',
    sort: 'date_desc'
  };

  // facets for pickers
  $: facetsQuery = createQuery({
    queryKey: ['facets', filters.date_from, filters.date_to, filters.q],
    queryFn: () => getFacets(filters.date_from, filters.date_to, filters.q || undefined)
  });

  // browse query
  $: browseQuery = createQuery({
    queryKey: ['browse', filters],
    queryFn: () => browseArticles(filters, 50, 0)
  });

  function toggle(list: string[], v: string): string[] {
    return list.includes(v) ? list.filter(x => x !== v) : [...list, v];
  }
</script>

<svelte:head>
  <title>Browse Articles - SW VA News Hub</title>
  <meta name="description" content="Explore extracted articles with filters and search" />
  <link rel="prefetch" href="/api/articles/browse" />
</svelte:head>

<div class="container mx-auto p-4 max-w-7xl">
  <h1 class="text-3xl font-bold mb-4">Browse Articles</h1>

  <Card elevated={true}>
    <div class="grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
      <div>
        <label class="block text-sm font-medium mb-1">From</label>
        <Input type="date" bind:value={filters.date_from} />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">To</label>
        <Input type="date" bind:value={filters.date_to} />
      </div>
      <div class="md:col-span-2">
        <label class="block text-sm font-medium mb-1">Search</label>
        <Input placeholder="title or content..." bind:value={filters.q} />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Sort</label>
        <select class="select select-sm w-full" bind:value={filters.sort}>
          <option value="date_desc">Newest</option>
          <option value="date_asc">Oldest</option>
          <option value="title">Title</option>
        </select>
      </div>
      <div>
        <Button on:click={() => browseQuery.refetch()}>Apply</Button>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
      <div>
        <label class="block text-sm font-medium mb-1">Publications</label>
        <div class="flex flex-wrap gap-2 max-h-40 overflow-auto p-1 border rounded">
          {#if $facetsQuery.isLoading}
            <LoadingSpinner size="sm" />
          {:else}
            {#each $facetsQuery.data?.publications || [] as pub}
              <button class="badge badge-outline cursor-pointer"
                class:badge-primary={filters.publications?.includes(pub.key)}
                on:click={() => filters.publications = toggle(filters.publications || [], pub.key)}>
                {pub.key} ({pub.count})
              </button>
            {/each}
          {/if}
        </div>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Sections</label>
        <div class="flex flex-wrap gap-2 max-h-40 overflow-auto p-1 border rounded">
          {#if $facetsQuery.isLoading}
            <LoadingSpinner size="sm" />
          {:else}
            {#each $facetsQuery.data?.sections || [] as sec}
              <button class="badge badge-outline cursor-pointer"
                class:badge-secondary={filters.sections?.includes(sec.key)}
                on:click={() => filters.sections = toggle(filters.sections || [], sec.key)}>
                {sec.key} ({sec.count})
              </button>
            {/each}
          {/if}
        </div>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Tags</label>
        <div class="flex flex-wrap gap-2 max-h-40 overflow-auto p-1 border rounded">
          {#if $facetsQuery.isLoading}
            <LoadingSpinner size="sm" />
          {:else}
            {#each $facetsQuery.data?.tags || [] as tag}
              <button class="badge badge-outline cursor-pointer"
                class:badge-accent={filters.tags?.includes(tag.key)}
                on:click={() => filters.tags = toggle(filters.tags || [], tag.key)}>
                {tag.key} ({tag.count})
              </button>
            {/each}
          {/if}
        </div>
      </div>
    </div>
  </Card>

  <div class="mt-4">
    {#if $browseQuery.isLoading}
      <div class="flex items-center gap-2 text-slate-600"><LoadingSpinner /> Loading…</div>
    {:else}
      <div class="text-sm text-slate-500 mb-2">{ $browseQuery.data?.count || 0 } results</div>
      <div class="grid grid-cols-1 gap-3">
        {#each $browseQuery.data?.items || [] as item}
          <Card hoverable={true}>
            <div class="flex flex-col md:flex-row md:items-center gap-2">
              <div class="md:w-2/3">
                <h3 class="font-semibold">{item.title}</h3>
                <p class="text-slate-600 dark:text-slate-400 text-sm line-clamp-3">{item.summary}</p>
              </div>
              <div class="md:w-1/3 text-sm text-right text-slate-500">
                <div>{item.publication || '—'} · {item.section || '—'}</div>
                <div>{item.date_published || item.edition_date || item.date_extracted}</div>
              </div>
            </div>
          </Card>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
.badge { @apply px-2 py-1 rounded text-xs; }
.badge-primary { @apply bg-blue-600 text-white; }
.badge-secondary { @apply bg-green-600 text-white; }
.badge-accent { @apply bg-purple-600 text-white; }
.badge-outline { @apply border border-slate-300 text-slate-600 dark:text-slate-300; }
</style>

