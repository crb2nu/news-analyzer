<script lang="ts">
	import { page } from '$app/stores';
	import { createQuery } from '@tanstack/svelte-query';
	import { getFeedDates, getFeedArticles } from '$lib/api/endpoints';
	import { updateUrlParams } from '$lib/utils/url-state';
	import { readArticles } from '$lib/stores/read-tracker';
	import FeedFilters from '$lib/components/feed/FeedFilters.svelte';
	import ArticleCard from '$lib/components/feed/ArticleCard.svelte';
	import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';
	import type { Article } from '$lib/types/api';

	// Read URL params
	$: selectedDate = $page.url.searchParams.get('date') || '';
	$: selectedSection = $page.url.searchParams.get('section') || '';
	$: searchQuery = $page.url.searchParams.get('q') || '';
	$: eventsOnly = $page.url.searchParams.get('eventsOnly') === '1';
	$: hideRead = $page.url.searchParams.get('hideRead') === '1';

	// Fetch dates
	const datesQuery = createQuery({
		queryKey: ['feed', 'dates'],
		queryFn: () => getFeedDates(14)
	});

	// Auto-select first date
	$: if ($datesQuery.data?.dates.length && !selectedDate) {
		selectedDate = $datesQuery.data.dates[0].date;
		updateUrlParams({ date: selectedDate });
	}

	// Fetch articles
	$: articlesQuery = createQuery({
		queryKey: ['feed', 'articles', selectedDate, { section: selectedSection, search: searchQuery }],
		queryFn: () =>
			getFeedArticles(selectedDate, {
				section: selectedSection || undefined,
				search: searchQuery || undefined
			}),
		enabled: !!selectedDate
	});

	// Client-side filtering
	$: filteredArticles = (($articlesQuery.data?.items || []) as Article[]).filter((article) => {
		if (hideRead && $readArticles.has(article.id)) return false;
		if (eventsOnly && !article.events?.length) return false;
		return true;
	});

	// Extract sections for filter
	$: sections = ($articlesQuery.data?.items || []).reduce(
		(acc, article) => {
			const section = article.section || 'General';
			acc[section] = (acc[section] || 0) + 1;
			return acc;
		},
		{} as Record<string, number>
	);

	$: sectionOptions = Object.entries(sections).map(([name, count]) => ({
		name,
		count
	}));

	function handleToggleRead(event: CustomEvent<number>) {
		readArticles.toggle(event.detail);
	}

	async function handleCopyLink(event: CustomEvent<number>) {
		const articleId = event.detail;
		const url = `${window.location.origin}/articles/${articleId}/source`;
		try {
			await navigator.clipboard.writeText(url);
			// Could show a toast notification here
		} catch (error) {
			console.error('Failed to copy link:', error);
		}
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
			<div
				class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-6 text-center"
			>
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
						on:toggleRead={handleToggleRead}
						on:copyLink={handleCopyLink}
					/>
				{/each}
			</div>

			<div class="mt-6 text-center text-sm text-slate-600 dark:text-slate-400">
				Showing {filteredArticles.length} of {$articlesQuery.data?.items.length || 0} articles
			</div>
		{/if}
	</div>
</div>
