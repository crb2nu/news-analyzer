<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { searchArticles, getSimilarArticles, getTrending } from '$lib/api/endpoints';
	import { debounce } from '$lib/utils/timing';
	import type { TrendingKind } from '$lib/types/api';
	import Input from '$lib/components/common/Input.svelte';
	import Button from '$lib/components/common/Button.svelte';
	import Card from '$lib/components/common/Card.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';
	import TrendCard from '$lib/components/charts/TrendCard.svelte';
	import NetworkGraph from '$lib/components/charts/NetworkGraph.svelte';
	import { Search, Sparkles, Tags, Hash, Target, Network } from 'lucide-svelte';

	let query = '';
	let debouncedQuery = '';
	let selectedArticleId: number | null = null;
	let selectedTrendingType: TrendingKind = 'section';

	const trendingTypes: Array<{ value: TrendingKind; label: string; icon: any }> = [
		{ value: 'section', label: 'Sections', icon: Hash },
		{ value: 'tag', label: 'Tags', icon: Tags },
		{ value: 'entity', label: 'Entities', icon: Target },
		{ value: 'topic', label: 'Topics', icon: Sparkles }
	];

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
		queryKey: ['trending', selectedTrendingType],
		queryFn: () => getTrending(selectedTrendingType, undefined, 30)
	});

	// Get data for all types for network graph
	$: allEntitiesQuery = createQuery({
		queryKey: ['trending', 'entity', 'network'],
		queryFn: () => getTrending('entity', undefined, 15)
	});

	$: allTopicsQuery = createQuery({
		queryKey: ['trending', 'topic', 'network'],
		queryFn: () => getTrending('topic', undefined, 15)
	});

	// Build network graph data
	$: networkNodes = [
		...($allEntitiesQuery.data?.map(item => ({
			id: `entity-${item.key}`,
			label: item.key,
			type: 'entity' as const,
			score: item.score
		})) || []),
		...($allTopicsQuery.data?.map(item => ({
			id: `topic-${item.key}`,
			label: item.key,
			type: 'topic' as const,
			score: item.score
		})) || [])
	];

	// Create links based on co-occurrence (simulated - in real app would come from API)
	$: networkLinks = networkNodes.length > 1 ? networkNodes.slice(0, -1).map((node, i) => ({
		source: node.id,
		target: networkNodes[Math.min(i + 1 + Math.floor(Math.random() * 3), networkNodes.length - 1)].id,
		value: Math.random() * 2 + 1
	})) : [];

	$: similarQuery = createQuery({
		queryKey: ['similar', selectedArticleId],
		queryFn: () => getSimilarArticles(selectedArticleId!),
		enabled: selectedArticleId !== null
	});

	function handleShowSimilar(id: number) {
		selectedArticleId = id;
	}

	function selectTrendingType(type: TrendingKind) {
		selectedTrendingType = type;
	}
</script>

<svelte:head>
	<title>Discover - SW VA News Hub</title>
</svelte:head>

<div class="container mx-auto p-4 max-w-7xl">
	<div class="mb-6">
		<h1 class="text-3xl font-bold mb-2">Discover</h1>
		<p class="text-slate-600 dark:text-slate-400">
			Explore trending topics, search articles, and find connections
		</p>
	</div>

	<div class="grid grid-cols-1 xl:grid-cols-3 gap-6">
		<!-- Search Section -->
		<div class="xl:col-span-2">
			<Card>
				<h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
					<Search class="w-5 h-5" />
					Search All Articles
				</h2>
				<div class="relative mb-4">
					<Input
						type="search"
						placeholder="Search BM25 (e.g., school budget, election results)"
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
						Enter a query to search across all dates
					</p>
				{/if}
			</Card>

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

		<!-- Trending Section -->
		<div class="xl:col-span-1">
			<Card>
				<h2 class="text-xl font-semibold mb-4">Trending Now</h2>

				<!-- Trending Type Tabs -->
				<div class="flex gap-2 mb-4 overflow-x-auto pb-2">
					{#each trendingTypes as type}
						<button
							class="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors whitespace-nowrap"
							class:bg-blue-100={selectedTrendingType === type.value}
							class:text-blue-700={selectedTrendingType === type.value}
							class:dark:bg-blue-900={selectedTrendingType === type.value}
							class:dark:text-blue-300={selectedTrendingType === type.value}
							class:bg-slate-100={selectedTrendingType !== type.value}
							class:text-slate-700={selectedTrendingType !== type.value}
							class:dark:bg-slate-800={selectedTrendingType !== type.value}
							class:dark:text-slate-300={selectedTrendingType !== type.value}
							class:hover:bg-slate-200={selectedTrendingType !== type.value}
							class:dark:hover:bg-slate-700={selectedTrendingType !== type.value}
							on:click={() => selectTrendingType(type.value)}
						>
							<svelte:component this={type.icon} class="w-4 h-4" />
							{type.label}
						</button>
					{/each}
				</div>

				{#if $trendingQuery.isLoading}
					<div class="flex justify-center py-8">
						<LoadingSpinner />
					</div>
				{:else if $trendingQuery.data && $trendingQuery.data.length > 0}
					<div class="space-y-3 max-h-[700px] overflow-y-auto">
						{#each $trendingQuery.data as item}
							<TrendCard
								kind={item.kind}
								itemKey={item.key}
								score={item.score}
								zscore={item.zscore}
								details={item.details}
							/>
						{/each}
					</div>
				{:else}
					<p class="text-slate-600 dark:text-slate-400 text-center py-8">
						No trending {selectedTrendingType}s yet
					</p>
				{/if}
			</Card>
		</div>
	</div>

	<!-- Network Graph Section -->
	{#if networkNodes.length > 0}
		<div class="mt-6">
			<Card>
				<div class="flex items-center gap-2 mb-4">
					<Network class="w-5 h-5 text-indigo-600" />
					<h2 class="text-xl font-semibold">Topic & Entity Network</h2>
				</div>
				<p class="text-sm text-slate-600 dark:text-slate-400 mb-4">
					Interactive visualization showing relationships between trending topics and entities. Drag nodes to explore connections.
				</p>
				{#if $allEntitiesQuery.isLoading || $allTopicsQuery.isLoading}
					<div class="flex justify-center py-12">
						<LoadingSpinner />
					</div>
				{:else}
					<NetworkGraph
						nodes={networkNodes}
						links={networkLinks}
						width={1000}
						height={500}
					/>
				{/if}
			</Card>
		</div>
	{/if}
</div>
