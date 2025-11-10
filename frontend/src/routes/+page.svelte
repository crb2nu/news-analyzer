<script lang="ts">
	import { browser } from '$app/environment';
	import { tick } from 'svelte';
	import { page } from '$app/stores';
	import { createQuery } from '@tanstack/svelte-query';
	import {
		getFeedDates,
		getFeedArticles,
		searchArticles,
		getSimilarArticles,
		getTrending,
		getTimeline
	} from '$lib/api/endpoints';
	import { updateUrlParams } from '$lib/utils/url-state';
	import { debounce } from '$lib/utils/timing';
	import { readArticles } from '$lib/stores/read-tracker';
	import ArticleCard from '$lib/components/feed/ArticleCard.svelte';
	import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';
	import FilterPanel from '$lib/components/workspace/FilterPanel.svelte';
	import SearchPanel from '$lib/components/workspace/SearchPanel.svelte';
	import InsightsPanel from '$lib/components/workspace/InsightsPanel.svelte';
	import Card from '$lib/components/common/Card.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import Button from '$lib/components/common/Button.svelte';
	import type { Article, TrendingKind } from '$lib/types/api';
import { computeArticleStats } from '$lib/utils/articles';
import { buildInsightLinks, type InsightNode, type InsightLink } from '$lib/utils/network';

type FilterStat = {
	label: string;
	value: string | number;
	helper?: string;
	accent: 'blue' | 'green' | 'purple' | 'orange';
};

	// URL-driven filters
	let selectedDate = $page.url.searchParams.get('date') || '';
	let selectedSection = $page.url.searchParams.get('section') || '';
	let feedSearchQuery = $page.url.searchParams.get('q') || '';
	let eventsOnly = $page.url.searchParams.get('eventsOnly') === '1';
	let hideRead = $page.url.searchParams.get('hideRead') === '1';

	// Global search state
	let globalSearch = '';
	let debouncedGlobalSearch = '';
	const runGlobalSearch = debounce((value: string) => {
		debouncedGlobalSearch = value.trim();
	}, 300);
	$: runGlobalSearch(globalSearch);

	// Focus & discovery
let selectedSimilarArticleId: number | null = null;
let focusedArticleId: number | null = null;
let activeTrend: { kind: TrendingKind; key: string } | null = null;
let lastTrendDate: string | null = null;
let filterStats: FilterStat[] = [];
let networkNodes: InsightNode[] = [];
let networkLinks: InsightLink[] = [];

	const datesQuery = createQuery({
		queryKey: ['feed', 'dates'],
		queryFn: () => getFeedDates(21)
	});

	$: if ($datesQuery.data?.dates.length && !selectedDate) {
		selectedDate = $datesQuery.data.dates[0].date;
		updateUrlParams({ date: selectedDate });
	}

	// Reset trend focus when date changes
	$: if (selectedDate !== lastTrendDate) {
		activeTrend = null;
		lastTrendDate = selectedDate;
	}

	$: articlesQuery = createQuery({
		queryKey: ['feed', 'articles', selectedDate, { section: selectedSection, search: feedSearchQuery }],
		queryFn: () =>
			getFeedArticles(selectedDate, {
				section: selectedSection || undefined,
				search: feedSearchQuery || undefined
			}),
		enabled: !!selectedDate
	});

	$: filteredArticles = (($articlesQuery.data?.items || []) as Article[]).filter((article) => {
		if (eventsOnly && !article.events?.length) return false;
		if (hideRead && $readArticles.has(article.id)) return false;
		return true;
	});

	$: sections = ($articlesQuery.data?.items || []).reduce(
		(acc, article) => {
			const section = article.section || 'General';
			acc[section] = (acc[section] || 0) + 1;
			return acc;
		},
		{} as Record<string, number>
	);

	$: sectionOptions = Object.entries(sections)
		.sort((a, b) => b[1] - a[1])
		.map(([name, count]) => ({ name, count }));

	$: stats = computeArticleStats(filteredArticles, $readArticles);
	$: {
		const entries: Array<FilterStat | null> = [
			{
				label: 'Articles in view',
				value: stats.total || '—',
				helper: `${stats.sectionCount} sections`,
				accent: 'blue'
			},
			{
				label: 'Unread',
				value: stats.unread,
				helper: `${stats.unreadPercent}% of feed`,
				accent: 'purple'
			},
			{
				label: 'Events surfaced',
				value: stats.withEvents,
				helper: `${stats.withEventsPercent}% with events`,
				accent: 'green'
			},
			stats.topSection
				? {
					label: 'Top section',
					value: stats.topSection.name,
					helper: `${stats.topSection.count} stories`,
					accent: 'orange'
				}
				: null
		];
		filterStats = entries.filter((stat): stat is FilterStat => Boolean(stat));
	}

	$: globalSearchQuery = createQuery({
		queryKey: ['global-search', debouncedGlobalSearch],
		queryFn: () => searchArticles(debouncedGlobalSearch),
		enabled: debouncedGlobalSearch.length > 2
	});

	$: similarQuery = createQuery({
		queryKey: ['similar', selectedSimilarArticleId],
		queryFn: () => getSimilarArticles(selectedSimilarArticleId!, 6),
		enabled: selectedSimilarArticleId !== null
	});

	$: trendingSectionsQuery = createQuery({
		queryKey: ['trending', 'section', selectedDate],
		queryFn: () => getTrending('section', selectedDate || undefined, 12),
		enabled: !!selectedDate
	});

	$: trendingTagsQuery = createQuery({
		queryKey: ['trending', 'tag', selectedDate],
		queryFn: () => getTrending('tag', selectedDate || undefined, 12),
		enabled: !!selectedDate
	});

	$: trendingEntitiesQuery = createQuery({
		queryKey: ['trending', 'entity', selectedDate],
		queryFn: () => getTrending('entity', selectedDate || undefined, 12),
		enabled: !!selectedDate
	});

	$: trendingTopicsQuery = createQuery({
		queryKey: ['trending', 'topic', selectedDate],
		queryFn: () => getTrending('topic', selectedDate || undefined, 10),
		enabled: !!selectedDate
	});

	$: if (!activeTrend && $trendingSectionsQuery.data?.length) {
		activeTrend = {
			kind: 'section',
			key: $trendingSectionsQuery.data[0].key
		};
	}

	$: timelineQuery = createQuery({
		queryKey: ['timeline', activeTrend?.kind, activeTrend?.key],
		queryFn: () => getTimeline(activeTrend!.kind, activeTrend!.key, 30),
		enabled: !!activeTrend
	});

	$: networkNodes = [
		...($trendingEntitiesQuery.data?.map((item) => ({
			id: `entity-${item.key}`,
			label: item.key,
			type: 'entity' as const,
			score: item.score
		})) || []),
		...($trendingTopicsQuery.data?.map((item) => ({
			id: `topic-${item.key}`,
			label: item.key,
			type: 'topic' as const,
			score: item.score
		})) || []),
		...($trendingTagsQuery.data?.map((item) => ({
			id: `tag-${item.key}`,
			label: item.key,
			type: 'tag' as const,
			score: item.score
		})) || [])
	];

	$: networkLinks = buildInsightLinks(networkNodes);

	function handleDateChange(date: string) {
		selectedDate = date;
		updateUrlParams({ date });
	}

	function handleSectionChange(section: string) {
		selectedSection = section;
		updateUrlParams({ section });
	}

	function handleFeedSearch(value: string) {
		feedSearchQuery = value;
		updateUrlParams({ q: value });
	}

	function handleEventsOnlyChange(value: boolean) {
		eventsOnly = value;
		updateUrlParams({ eventsOnly: value ? '1' : '' });
	}

	function handleHideReadChange(value: boolean) {
		hideRead = value;
		updateUrlParams({ hideRead: value ? '1' : '' });
	}

	function handleTrendSelect(detail: { kind: TrendingKind; key: string }) {
		activeTrend = detail;

		if (detail.kind === 'section') {
			handleSectionChange(detail.key);
		} else {
			handleFeedSearch(detail.key);
		}
	}

	function handleGlobalSearchChange(value: string) {
		globalSearch = value;
	}

	function handleFocusArticle(id: number) {
		focusArticleById(id);
	}

	async function focusArticleById(id: number) {
		focusedArticleId = id;
		if (!browser) return;
		await tick();
		const element = document.querySelector<HTMLElement>(`[data-article-id="${id}"]`);
		element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
		setTimeout(() => {
			if (focusedArticleId === id) {
				focusedArticleId = null;
			}
		}, 4000);
	}

	function handleShowSimilar(id: number) {
		selectedSimilarArticleId = id;
	}

	function clearSimilar() {
		selectedSimilarArticleId = null;
	}
</script>

<svelte:head>
	<title>Insights Workspace - SW VA News Hub</title>
</svelte:head>

<div class="container mx-auto max-w-7xl px-4 py-8 space-y-8">
	<div>
		<h1 class="text-3xl font-bold">Insights Workspace</h1>
		<p class="text-slate-600 dark:text-slate-400">
			Browse the latest edition, monitor trending signals, and run deep discovery without leaving the page.
		</p>
	</div>

	<div class="grid grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)_360px] gap-6">
		<aside class="space-y-6">
			{#if $datesQuery.isLoading}
				<div class="rounded-xl border border-slate-200 dark:border-slate-800 p-6">
					<LoadingSpinner />
				</div>
			{:else if $datesQuery.data}
				<FilterPanel
					dates={$datesQuery.data.dates}
					{selectedDate}
					sections={sectionOptions}
					{selectedSection}
					eventsOnly={eventsOnly}
					hideRead={hideRead}
					searchText={feedSearchQuery}
					stats={filterStats}
					on:dateChange={(e) => handleDateChange(e.detail)}
					on:sectionChange={(e) => handleSectionChange(e.detail)}
					on:searchChange={(e) => handleFeedSearch(e.detail)}
					on:eventsOnlyChange={(e) => handleEventsOnlyChange(e.detail)}
					on:hideReadChange={(e) => handleHideReadChange(e.detail)}
					on:refresh={() => $articlesQuery.refetch()}
				/>
			{/if}
		</aside>

		<section class="space-y-6">
			<div class="rounded-xl p-6 shadow-md text-white bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600">
				<p class="text-sm uppercase tracking-wide opacity-80">Edition Overview</p>
				<h2 class="text-2xl font-semibold mt-2">{selectedDate || '—'}</h2>
				<p class="text-sm mt-2 text-blue-50">
					{stats.total} story{stats.total === 1 ? '' : 'ies'} • {stats.sectionCount} sections • {stats.withEvents} events captured
				</p>
			</div>

			{#if $articlesQuery.isLoading}
				<div class="flex justify-center py-20">
					<LoadingSpinner size="lg" />
				</div>
			{:else if $articlesQuery.error}
				<div class="rounded-xl border border-red-200 bg-red-50 p-6 text-red-800">
					<p>Failed to load articles: {$articlesQuery.error.message}</p>
					<Button class="mt-4" on:click={() => $articlesQuery.refetch()}>Try again</Button>
				</div>
			{:else if filteredArticles.length === 0}
				<div class="rounded-xl border border-slate-200 dark:border-slate-800 p-10 text-center text-slate-500">
					<p>No articles match the current filters.</p>
				</div>
			{:else}
				<div class="space-y-6">
					{#each filteredArticles as article (article.id)}
						<ArticleCard
							{article}
							read={$readArticles.has(article.id)}
							focused={focusedArticleId === article.id}
							on:toggleRead={(event) => readArticles.toggle(event.detail)}
							on:copyLink={(event) => navigator.clipboard.writeText(`${window.location.origin}/articles/${event.detail}/source`).catch(console.error)}
						/>
					{/each}
				</div>
			{/if}
		</section>

		<aside class="space-y-6">
			<InsightsPanel
				sectionTrends={$trendingSectionsQuery.data || []}
				tagTrends={$trendingTagsQuery.data || []}
				entityTrends={$trendingEntitiesQuery.data || []}
				timelineData={$timelineQuery.data || []}
				timelineLabel={activeTrend?.key || null}
				timelineKind={activeTrend?.kind || null}
				isTrendingLoading={$trendingSectionsQuery.isLoading || $trendingTagsQuery.isLoading || $trendingEntitiesQuery.isLoading}
				isTimelineLoading={$timelineQuery.isLoading}
				networkNodes={networkNodes}
				networkLinks={networkLinks}
				on:trendSelect={(e) => handleTrendSelect(e.detail)}
			/>

			<SearchPanel
				query={globalSearch}
				debouncedQuery={debouncedGlobalSearch}
				results={$globalSearchQuery.data || []}
				isLoading={$globalSearchQuery.isLoading}
				on:queryChange={(e) => handleGlobalSearchChange(e.detail)}
				on:focusArticle={(e) => handleFocusArticle(e.detail)}
				on:showSimilar={(e) => handleShowSimilar(e.detail)}
			/>

			{#if selectedSimilarArticleId}
				<Card class="space-y-3">
					<div class="flex items-center justify-between">
						<div>
							<h3 class="font-semibold">Similar Articles</h3>
							<p class="text-xs text-slate-500">Vector matches for article #{selectedSimilarArticleId}</p>
						</div>
						<button class="text-xs text-blue-600" on:click={clearSimilar}>Clear</button>
					</div>

					{#if $similarQuery.isLoading}
						<div class="flex justify-center py-4">
							<LoadingSpinner />
						</div>
					{:else if $similarQuery.data?.length}
						<div class="space-y-3 max-h-[300px] overflow-y-auto pr-1">
							{#each $similarQuery.data as article}
								<div class="border border-slate-200 dark:border-slate-700 rounded-lg p-3">
									<div class="flex items-start justify-between gap-2">
										<h4 class="font-semibold text-sm">{article.title}</h4>
										{#if article.section}
											<Badge size="sm">{article.section}</Badge>
										{/if}
									</div>
									<p class="text-xs text-slate-500 mt-1 line-clamp-2">
										{article.summary || 'Summary pending'}
									</p>
									<div class="flex items-center gap-2 mt-2 text-xs text-slate-500">
										{#if article.distance !== undefined}
											<span>Distance {article.distance.toFixed(2)}</span>
										{/if}
										<Button size="xs" variant="ghost" on:click={() => handleFocusArticle(article.article_id)}>
											Focus
										</Button>
										<Button size="xs" variant="primary" href={`/articles/${article.article_id}/source`} target="_blank">
											Open Source
										</Button>
									</div>
								</div>
							{/each}
						</div>
					{:else}
						<p class="text-sm text-slate-500">No matches yet.</p>
					{/if}
				</Card>
			{/if}
		</aside>
	</div>
</div>
