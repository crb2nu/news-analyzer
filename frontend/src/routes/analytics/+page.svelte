<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { getTrending, getTimeline } from '$lib/api/endpoints';
	import Card from '$lib/components/common/Card.svelte';
	import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';
	import TimelineChart from '$lib/components/charts/TimelineChart.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import TrendCard from '$lib/components/charts/TrendCard.svelte';
	import { BarChart3, TrendingUp, Tag, Users } from 'lucide-svelte';

	// Get trending data for different types
	$: trendingSectionsQuery = createQuery({
		queryKey: ['trending', 'section'],
		queryFn: () => getTrending('section', undefined, 10)
	});

	$: trendingTagsQuery = createQuery({
		queryKey: ['trending', 'tag'],
		queryFn: () => getTrending('tag', undefined, 10)
	});

	$: trendingEntitiesQuery = createQuery({
		queryKey: ['trending', 'entity'],
		queryFn: () => getTrending('entity', undefined, 10)
	});

	// Get timeline for top section
	$: topSectionKey = $trendingSectionsQuery.data?.[0]?.key;

	$: topSectionTimelineQuery = createQuery({
		queryKey: ['timeline', 'section', topSectionKey],
		queryFn: () => getTimeline('section', topSectionKey!, 30),
		enabled: !!topSectionKey
	});

	// Prepare bar chart data from trending sections
	$: sectionBarData =
		$trendingSectionsQuery.data?.slice(0, 8).map((item) => ({
			label: item.key,
			value: item.score,
			color: item.zscore && item.zscore > 2 ? 'rgb(239, 68, 68)' : item.zscore && item.zscore > 1 ? 'rgb(245, 158, 11)' : 'rgb(59, 130, 246)'
		})) || [];

	$: tagBarData =
		$trendingTagsQuery.data?.slice(0, 10).map((item) => ({
			label: item.key.length > 15 ? item.key.slice(0, 15) + '...' : item.key,
			value: item.score
		})) || [];
</script>

<svelte:head>
	<title>Analytics - SW VA News Hub</title>
</svelte:head>

<div class="container mx-auto p-4 max-w-7xl">
	<div class="mb-6">
		<h1 class="text-3xl font-bold mb-2">Analytics Dashboard</h1>
		<p class="text-slate-600 dark:text-slate-400">
			Insights into news trends, coverage patterns, and hot topics
		</p>
	</div>

	<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
		<!-- Section Volume Chart -->
		<Card>
			<div class="flex items-center gap-2 mb-4">
				<BarChart3 class="w-5 h-5 text-blue-600" />
				<h2 class="text-xl font-semibold">Coverage by Section</h2>
			</div>
			{#if $trendingSectionsQuery.isLoading}
				<div class="flex justify-center py-8">
					<LoadingSpinner />
				</div>
			{:else if sectionBarData.length > 0}
				<BarChart data={sectionBarData} height={300} />
			{:else}
				<p class="text-slate-600 dark:text-slate-400 text-center py-8">No data available</p>
			{/if}
		</Card>

		<!-- Top Section Timeline -->
		<Card>
			<div class="flex items-center gap-2 mb-4">
				<TrendingUp class="w-5 h-5 text-green-600" />
				<h2 class="text-xl font-semibold">
					{topSectionKey ? `${topSectionKey} - 30 Day Trend` : 'Section Trend'}
				</h2>
			</div>
			{#if $topSectionTimelineQuery.isLoading}
				<div class="flex justify-center py-8">
					<LoadingSpinner />
				</div>
			{:else if $topSectionTimelineQuery.data && $topSectionTimelineQuery.data.length > 0}
				<TimelineChart
					data={$topSectionTimelineQuery.data}
					height={250}
					color="rgb(34, 197, 94)"
					yAxisLabel="Articles"
				/>
			{:else}
				<p class="text-slate-600 dark:text-slate-400 text-center py-8">No timeline data</p>
			{/if}
		</Card>
	</div>

	<!-- Trending Tags Chart -->
	<div class="mb-6">
		<Card>
			<div class="flex items-center gap-2 mb-4">
				<Tag class="w-5 h-5 text-purple-600" />
				<h2 class="text-xl font-semibold">Trending Tags</h2>
			</div>
			{#if $trendingTagsQuery.isLoading}
				<div class="flex justify-center py-8">
					<LoadingSpinner />
				</div>
			{:else if tagBarData.length > 0}
				<BarChart data={tagBarData} height={280} horizontal={true} />
			{:else}
				<p class="text-slate-600 dark:text-slate-400 text-center py-8">No trending tags</p>
			{/if}
		</Card>
	</div>

	<!-- Top Entities -->
	<div class="mb-6">
		<Card>
			<div class="flex items-center gap-2 mb-4">
				<Users class="w-5 h-5 text-orange-600" />
				<h2 class="text-xl font-semibold">Top Mentioned Entities</h2>
			</div>
			{#if $trendingEntitiesQuery.isLoading}
				<div class="flex justify-center py-8">
					<LoadingSpinner />
				</div>
			{:else if $trendingEntitiesQuery.data && $trendingEntitiesQuery.data.length > 0}
				<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
					{#each $trendingEntitiesQuery.data.slice(0, 12) as entity}
						<TrendCard
							kind={entity.kind}
							itemKey={entity.key}
							score={entity.score}
							zscore={entity.zscore}
							details={entity.details}
							clickable={false}
						/>
					{/each}
				</div>
			{:else}
				<p class="text-slate-600 dark:text-slate-400 text-center py-8">
					No entity data available
				</p>
			{/if}
		</Card>
	</div>

	<!-- Stats Summary -->
	<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
		<Card>
			<div class="text-center py-4">
				<div class="text-3xl font-bold text-blue-600 dark:text-blue-400 mb-1">
					{$trendingSectionsQuery.data?.length || 0}
				</div>
				<div class="text-sm text-slate-600 dark:text-slate-400">Active Sections</div>
			</div>
		</Card>

		<Card>
			<div class="text-center py-4">
				<div class="text-3xl font-bold text-purple-600 dark:text-purple-400 mb-1">
					{$trendingTagsQuery.data?.length || 0}
				</div>
				<div class="text-sm text-slate-600 dark:text-slate-400">Trending Tags</div>
			</div>
		</Card>

		<Card>
			<div class="text-center py-4">
				<div class="text-3xl font-bold text-orange-600 dark:text-orange-400 mb-1">
					{$trendingEntitiesQuery.data?.length || 0}
				</div>
				<div class="text-sm text-slate-600 dark:text-slate-400">Mentioned Entities</div>
			</div>
		</Card>
	</div>
</div>
