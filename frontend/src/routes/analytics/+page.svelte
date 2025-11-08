<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { getTrending, getTimeline } from '$lib/api/endpoints';
	import Card from '$lib/components/common/Card.svelte';
	import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';
	import SkeletonCard from '$lib/components/common/SkeletonCard.svelte';
	import SkeletonChart from '$lib/components/common/SkeletonChart.svelte';
	import AnimatedCounter from '$lib/components/common/AnimatedCounter.svelte';
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
	<div class="mb-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
		<h1 class="text-3xl font-bold mb-2">Analytics Dashboard</h1>
		<p class="text-slate-600 dark:text-slate-400">
			Insights into news trends, coverage patterns, and hot topics
		</p>
	</div>

	<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
		<!-- Section Volume Chart -->
		<div class="animate-in fade-in slide-in-from-left-4 duration-500" style="animation-delay: 100ms;">
			<Card elevated={true}>
				<div class="flex items-center gap-2 mb-4">
					<BarChart3 class="w-5 h-5 text-blue-600" />
					<h2 class="text-xl font-semibold">Coverage by Section</h2>
				</div>
				{#if $trendingSectionsQuery.isLoading}
					<SkeletonChart type="bar" height={300} />
				{:else if sectionBarData.length > 0}
					<BarChart data={sectionBarData} height={300} />
				{:else}
					<p class="text-slate-600 dark:text-slate-400 text-center py-8">No data available</p>
				{/if}
			</Card>
		</div>

		<!-- Top Section Timeline -->
		<div class="animate-in fade-in slide-in-from-right-4 duration-500" style="animation-delay: 200ms;">
			<Card elevated={true}>
				<div class="flex items-center gap-2 mb-4">
					<TrendingUp class="w-5 h-5 text-green-600" />
					<h2 class="text-xl font-semibold">
						{topSectionKey ? `${topSectionKey} - 30 Day Trend` : 'Section Trend'}
					</h2>
				</div>
				{#if $topSectionTimelineQuery.isLoading}
					<SkeletonChart type="line" height={250} />
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
	</div>

	<!-- Trending Tags Chart -->
	<div class="mb-6 animate-in fade-in slide-in-from-bottom-4 duration-500" style="animation-delay: 300ms;">
		<Card elevated={true}>
			<div class="flex items-center gap-2 mb-4">
				<Tag class="w-5 h-5 text-purple-600" />
				<h2 class="text-xl font-semibold">Trending Tags</h2>
			</div>
			{#if $trendingTagsQuery.isLoading}
				<SkeletonChart type="bar" height={280} />
			{:else if tagBarData.length > 0}
				<BarChart data={tagBarData} height={280} horizontal={true} />
			{:else}
				<p class="text-slate-600 dark:text-slate-400 text-center py-8">No trending tags</p>
			{/if}
		</Card>
	</div>

	<!-- Top Entities -->
	<div class="mb-6 animate-in fade-in slide-in-from-bottom-4 duration-500" style="animation-delay: 400ms;">
		<Card elevated={true}>
			<div class="flex items-center gap-2 mb-4">
				<Users class="w-5 h-5 text-orange-600" />
				<h2 class="text-xl font-semibold">Top Mentioned Entities</h2>
			</div>
			{#if $trendingEntitiesQuery.isLoading}
				<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
					{#each Array(12) as _}
						<SkeletonCard rows={2} />
					{/each}
				</div>
			{:else if $trendingEntitiesQuery.data && $trendingEntitiesQuery.data.length > 0}
				<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
					{#each $trendingEntitiesQuery.data.slice(0, 12) as entity, i}
						<div class="animate-in fade-in slide-in-from-bottom-2 duration-300" style="animation-delay: {i * 50}ms;">
							<TrendCard
								kind={entity.kind}
								itemKey={entity.key}
								score={entity.score}
								zscore={entity.zscore}
								details={entity.details}
								clickable={false}
							/>
						</div>
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
		<div class="animate-in fade-in zoom-in-50 duration-500" style="animation-delay: 500ms;">
			<Card elevated={true} hoverable={true}>
				<div class="text-center py-4">
					<div class="text-3xl font-bold text-blue-600 dark:text-blue-400 mb-1">
						{#if $trendingSectionsQuery.isLoading}
							<LoadingSpinner size="sm" />
						{:else}
							<AnimatedCounter value={$trendingSectionsQuery.data?.length || 0} />
						{/if}
					</div>
					<div class="text-sm text-slate-600 dark:text-slate-400">Active Sections</div>
				</div>
			</Card>
		</div>

		<div class="animate-in fade-in zoom-in-50 duration-500" style="animation-delay: 600ms;">
			<Card elevated={true} hoverable={true}>
				<div class="text-center py-4">
					<div class="text-3xl font-bold text-purple-600 dark:text-purple-400 mb-1">
						{#if $trendingTagsQuery.isLoading}
							<LoadingSpinner size="sm" />
						{:else}
							<AnimatedCounter value={$trendingTagsQuery.data?.length || 0} />
						{/if}
					</div>
					<div class="text-sm text-slate-600 dark:text-slate-400">Trending Tags</div>
				</div>
			</Card>
		</div>

		<div class="animate-in fade-in zoom-in-50 duration-500" style="animation-delay: 700ms;">
			<Card elevated={true} hoverable={true}>
				<div class="text-center py-4">
					<div class="text-3xl font-bold text-orange-600 dark:text-orange-400 mb-1">
						{#if $trendingEntitiesQuery.isLoading}
							<LoadingSpinner size="sm" />
						{:else}
							<AnimatedCounter value={$trendingEntitiesQuery.data?.length || 0} />
						{/if}
					</div>
					<div class="text-sm text-slate-600 dark:text-slate-400">Mentioned Entities</div>
				</div>
			</Card>
		</div>
	</div>
</div>

<style>
	@keyframes fade-in {
		from { opacity: 0; }
		to { opacity: 1; }
	}
	
	@keyframes slide-in-from-bottom-4 {
		from { transform: translateY(1rem); opacity: 0; }
		to { transform: translateY(0); opacity: 1; }
	}
	
	@keyframes slide-in-from-bottom-2 {
		from { transform: translateY(0.5rem); opacity: 0; }
		to { transform: translateY(0); opacity: 1; }
	}
	
	@keyframes slide-in-from-left-4 {
		from { transform: translateX(-1rem); opacity: 0; }
		to { transform: translateX(0); opacity: 1; }
	}
	
	@keyframes slide-in-from-right-4 {
		from { transform: translateX(1rem); opacity: 0; }
		to { transform: translateX(0); opacity: 1; }
	}
	
	@keyframes zoom-in-50 {
		from { transform: scale(0.95); opacity: 0; }
		to { transform: scale(1); opacity: 1; }
	}
	
	.animate-in {
		animation-fill-mode: both;
	}
</style>
