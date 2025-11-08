<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { searchArticles, getSimilarArticles, getTrending } from '$lib/api/endpoints';
	import { debounce } from '$lib/utils/timing';
	import Input from '$lib/components/common/Input.svelte';
	import Button from '$lib/components/common/Button.svelte';
	import Card from '$lib/components/common/Card.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';
	import { Search } from 'lucide-svelte';

	let query = '';
	let debouncedQuery = '';
	let selectedArticleId: number | null = null;

	const handleInput = debounce((value: string) => {
		debouncedQuery = value;
	}, 300);

	$: handleInput(query);

	$: searchQuery = createQuery({
		queryKey: ['search', debouncedQuery],
		queryFn: () => searchArticles(debouncedQuery),
		enabled: debouncedQuery.length > 2
	});

	$: trendingQuery = createQuery({
		queryKey: ['trending', 'section'],
		queryFn: () => getTrending('section', undefined, 20)
	});

	$: similarQuery = createQuery({
		queryKey: ['similar', selectedArticleId],
		queryFn: () => getSimilarArticles(selectedArticleId!),
		enabled: selectedArticleId !== null
	});

	function handleShowSimilar(id: number) {
		selectedArticleId = id;
	}
</script>

<svelte:head>
	<title>Discover - SW VA News Hub</title>
</svelte:head>

<div class="container mx-auto p-4 max-w-6xl">
	<h1 class="text-3xl font-bold mb-6">Discover</h1>

	<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
		<!-- Search Section -->
		<Card>
			<h2 class="text-xl font-semibold mb-4">Search All Articles</h2>
			<div class="relative mb-4">
				<Input
					type="search"
					placeholder="Search BM25 (e.g., school budget)"
					bind:value={query}
					class="pr-10"
				/>
				<Search
					class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none"
				/>
			</div>

			{#if $searchQuery.isLoading}
				<div class="flex justify-center py-8">
					<LoadingSpinner />
				</div>
			{:else if $searchQuery.data && $searchQuery.data.length > 0}
				<div class="space-y-3 max-h-[600px] overflow-y-auto">
					{#each $searchQuery.data as result}
						<div
							class="p-4 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
						>
							<div class="flex items-start justify-between gap-2 mb-2">
								<h3 class="font-semibold">{result.title}</h3>
								{#if result.section}
									<Badge size="sm">{result.section}</Badge>
								{/if}
							</div>
							{#if result.summary}
								<p class="text-sm text-slate-600 dark:text-slate-400 mb-2">
									{result.summary.slice(0, 200)}...
								</p>
							{/if}
							<div class="flex items-center gap-2">
								<Button
									href="/articles/{result.article_id}/source"
									target="_blank"
									size="sm"
									variant="primary"
								>
									Open Source
								</Button>
								<Button
									size="sm"
									variant="ghost"
									on:click={() => handleShowSimilar(result.article_id)}
								>
									Similar
								</Button>
								<span class="text-xs text-slate-500">Score: {result.score.toFixed(2)}</span>
							</div>
						</div>
					{/each}
				</div>
			{:else if debouncedQuery.length > 0}
				<p class="text-slate-600 dark:text-slate-400 text-center py-8">
					No results for "{debouncedQuery}"
				</p>
			{:else}
				<p class="text-slate-600 dark:text-slate-400 text-center py-8">
					Enter a query to search all dates
				</p>
			{/if}
		</Card>

		<!-- Trending Section -->
		<Card>
			<h2 class="text-xl font-semibold mb-4">Trending Sections</h2>
			{#if $trendingQuery.isLoading}
				<div class="flex justify-center py-8">
					<LoadingSpinner />
				</div>
			{:else if $trendingQuery.data}
				<div class="space-y-2 max-h-[600px] overflow-y-auto">
					{#each $trendingQuery.data as item}
						<div
							class="p-3 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
						>
							<div class="flex items-center justify-between">
								<strong class="text-sm">{item.key}</strong>
								<div class="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
									<span>Score: {Number(item.score || 0).toFixed(2)}</span>
									{#if item.zscore !== null}
										<Badge size="sm" variant={item.zscore > 2 ? 'warning' : 'default'}>
											Z: {Number(item.zscore).toFixed(2)}
										</Badge>
									{/if}
								</div>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<p class="text-slate-600 dark:text-slate-400 text-center py-8">
					No trending items yet
				</p>
			{/if}
		</Card>
	</div>

	<!-- Similar Articles Section -->
	{#if selectedArticleId && $similarQuery.data}
		<Card class="mt-6">
			<h2 class="text-xl font-semibold mb-4">Similar Articles</h2>
			<div class="space-y-3">
				{#each $similarQuery.data as article}
					<div
						class="p-4 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
					>
						<div class="flex items-start justify-between gap-2 mb-2">
							<h3 class="font-semibold">{article.title}</h3>
							{#if article.section}
								<Badge size="sm">{article.section}</Badge>
							{/if}
						</div>
						{#if article.summary}
							<p class="text-sm text-slate-600 dark:text-slate-400 mb-2">
								{article.summary.slice(0, 200)}...
							</p>
						{/if}
						<div class="flex items-center gap-2">
							<Button
								href="/articles/{article.article_id}/source"
								target="_blank"
								size="sm"
								variant="primary"
							>
								Open Source
							</Button>
							{#if article.distance !== undefined}
								<span class="text-xs text-slate-500"
									>Distance: {article.distance.toFixed(2)}</span
								>
							{:else if article.score !== undefined}
								<span class="text-xs text-slate-500">Score: {article.score.toFixed(2)}</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</Card>
	{/if}
</div>
