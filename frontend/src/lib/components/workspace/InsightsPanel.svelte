<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { TrendingItem, TrendingKind, TimelineData } from '$lib/types/api';
	import TrendCard from '../charts/TrendCard.svelte';
	import TimelineChart from '../charts/TimelineChart.svelte';
	import NetworkGraph from '../charts/NetworkGraph.svelte';
	import LoadingSpinner from '../common/LoadingSpinner.svelte';
	import Badge from '../common/Badge.svelte';
	import { BarChart3, Share2, Sparkles } from 'lucide-svelte';
	import { countNodesByType, type InsightNode, type InsightLink } from '$lib/utils/network';

	export let sectionTrends: TrendingItem[] = [];
	export let tagTrends: TrendingItem[] = [];
	export let entityTrends: TrendingItem[] = [];
	export let timelineData: TimelineData[] = [];
	export let timelineLabel: string | null = null;
	export let timelineKind: TrendingKind | null = null;
	export let isTrendingLoading = false;
	export let isTimelineLoading = false;
	export let networkNodes: InsightNode[] = [];
	export let networkLinks: InsightLink[] = [];

	const dispatch = createEventDispatcher<{ trendSelect: { kind: TrendingKind; key: string } }>();

	let activeTab: TrendingKind = 'section';

	$: currentItems =
		activeTab === 'section'
			? sectionTrends
			: activeTab === 'tag'
				? tagTrends
				: entityTrends;

	$: maxScore = currentItems.reduce((max, item) => (item.score > max ? item.score : max), 0) || null;
	$: networkCounts = countNodesByType(networkNodes);
	$: timelineDelta = (() => {
		if (!timelineData.length) return null;
		const first = timelineData[0]?.count ?? 0;
		const last = timelineData[timelineData.length - 1]?.count ?? 0;
		const diff = last - first;
		const percent = first ? Math.round((diff / first) * 100) : null;
		return { diff, percent };
	})();
	$: highlightItems = (() => {
		const highlights: Array<{ label: string; value: string; helper?: string }> = [];
		if (sectionTrends[0]) {
			highlights.push({
				label: 'Top coverage',
				value: sectionTrends[0].key,
				helper: `Score ${sectionTrends[0].score.toFixed(1)}`
			});
		}
		const fastTag = tagTrends.find((t) => (t.zscore ?? 0) > 1.5) || tagTrends[0];
		if (fastTag) {
			highlights.push({
				label: 'Fastest rising tag',
				value: fastTag.key,
				helper: fastTag.zscore ? `z=${fastTag.zscore.toFixed(2)}` : undefined
			});
		}
		if (entityTrends[0]) {
			highlights.push({
				label: 'Most mentioned entity',
				value: entityTrends[0].key,
				helper: `Score ${entityTrends[0].score.toFixed(1)}`
			});
		}
		return highlights.slice(0, 3);
	})();
</script>

<div class="space-y-6">
	<div class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
		<div class="flex items-center justify-between mb-4">
			<div>
				<h3 class="text-lg font-semibold">Trending Signals</h3>
				<p class="text-xs text-slate-500 dark:text-slate-400">Click a card to filter the feed.</p>
			</div>
			<div class="flex gap-2 text-xs" role="tablist">
				{#each ['section', 'tag', 'entity'] as kind}
					<button
						type="button"
						class="px-3 py-1.5 rounded-full border"
						class:bg-blue-600={activeTab === kind}
						class:text-white={activeTab === kind}
						class:border-blue-600={activeTab === kind}
						class:bg-slate-100={activeTab !== kind}
						class:text-slate-700={activeTab !== kind}
						class:dark:bg-slate-800={activeTab !== kind}
						class:dark:text-slate-200={activeTab !== kind}
						class:dark:border-slate-700={activeTab !== kind}
						on:click={() => (activeTab = kind as TrendingKind)}
					>
						{kind === 'section' ? 'Sections' : kind === 'tag' ? 'Tags' : 'Entities'}
					</button>
				{/each}
			</div>
		</div>

		{#if isTrendingLoading}
			<div class="flex justify-center py-6">
				<LoadingSpinner />
			</div>
		{:else if currentItems.length}
			<div class="space-y-3 max-h-[420px] overflow-y-auto pr-1">
				{#each currentItems as item}
					<TrendCard
						kind={item.kind}
						itemKey={item.key}
						score={item.score}
						zscore={item.zscore}
						details={item.details}
						relativeMax={maxScore}
						on:select={(e) => dispatch('trendSelect', e.detail as { kind: TrendingKind; key: string })}
					/>
				{/each}
			</div>
		{:else}
			<p class="text-sm text-slate-500 dark:text-slate-400">No signals yet for this window.</p>
		{/if}
	</div>

	<div class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
		<div class="flex items-center gap-2 mb-4">
			<BarChart3 class="w-4 h-4 text-green-500" />
			<h3 class="text-lg font-semibold">30-Day Momentum</h3>
		</div>
		{#if isTimelineLoading}
			<div class="flex justify-center py-6">
				<LoadingSpinner />
			</div>
		{:else if timelineData.length && timelineLabel}
			<p class="text-xs text-slate-500 dark:text-slate-400 mb-2">
				{timelineLabel} {timelineKind ? `(${timelineKind})` : ''}
			</p>
			<TimelineChart data={timelineData} height={220} color="rgb(99, 102, 241)" yAxisLabel="Articles" />
			{#if timelineDelta}
				<p class="text-xs text-slate-500 dark:text-slate-400 mt-3">
					{#if timelineDelta.percent !== null}
						{timelineDelta.diff >= 0 ? '+' : ''}{timelineDelta.percent}% vs. 30-day start
					{:else}
						Change: {timelineDelta.diff}
					{/if}
				</p>
			{/if}
		{:else}
			<p class="text-sm text-slate-500 dark:text-slate-400">Select a trending item to view the trajectory.</p>
		{/if}
	</div>

	{#if highlightItems.length}
		<div class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
			<div class="flex items-center gap-2 mb-3">
				<Sparkles class="w-4 h-4 text-amber-500" />
				<h3 class="text-lg font-semibold">Daily Highlights</h3>
			</div>
			<ul class="space-y-3 text-sm">
				{#each highlightItems as highlight}
					<li class="flex items-center justify-between gap-3">
						<div>
							<p class="text-slate-500 dark:text-slate-400 text-xs uppercase tracking-wide">{highlight.label}</p>
							<p class="font-semibold text-slate-800 dark:text-slate-100">{highlight.value}</p>
						</div>
						{#if highlight.helper}
							<Badge size="sm" variant="default">{highlight.helper}</Badge>
						{/if}
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if networkNodes.length > 0}
		<div class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
			<div class="flex items-center gap-2 mb-3">
				<Share2 class="w-4 h-4 text-purple-500" />
				<h3 class="text-lg font-semibold">Topics & Entities</h3>
			</div>
			<div class="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 mb-3">
				<span class="px-2 py-1 rounded-full bg-orange-50 dark:bg-orange-900/30 text-orange-700 dark:text-orange-200 font-medium">
					Entities {networkCounts.entity}
				</span>
				<span class="px-2 py-1 rounded-full bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-200 font-medium">
					Topics {networkCounts.topic}
				</span>
				<span class="px-2 py-1 rounded-full bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-200 font-medium">
					Tags {networkCounts.tag}
				</span>
			</div>
			<div class="h-[260px]">
				<NetworkGraph nodes={networkNodes} links={networkLinks} width={320} height={240} />
			</div>
		</div>
	{/if}
</div>
