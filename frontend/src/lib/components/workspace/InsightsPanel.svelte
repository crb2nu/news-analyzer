<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { TrendingItem, TrendingKind, TimelineData } from '$lib/types/api';
	import TrendCard from '../charts/TrendCard.svelte';
	import TimelineChart from '../charts/TimelineChart.svelte';
	import NetworkGraph from '../charts/NetworkGraph.svelte';
	import LoadingSpinner from '../common/LoadingSpinner.svelte';
	import { BarChart3, Share2 } from 'lucide-svelte';

	export type NetworkNode = { id: string; label: string; type: string; score: number };
	export type NetworkLink = { source: string; target: string; value: number };

	export let sectionTrends: TrendingItem[] = [];
	export let tagTrends: TrendingItem[] = [];
	export let entityTrends: TrendingItem[] = [];
	export let timelineData: TimelineData[] = [];
	export let timelineLabel: string | null = null;
	export let timelineKind: TrendingKind | null = null;
	export let isTrendingLoading = false;
	export let isTimelineLoading = false;
	export let networkNodes: NetworkNode[] = [];
	export let networkLinks: NetworkLink[] = [];

	const dispatch = createEventDispatcher<{ trendSelect: { kind: TrendingKind; key: string } }>();

	let activeTab: TrendingKind = 'section';

	$: currentItems =
		activeTab === 'section'
			? sectionTrends
			: activeTab === 'tag'
				? tagTrends
				: entityTrends;
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
		{:else}
			<p class="text-sm text-slate-500 dark:text-slate-400">Select a trending item to view the trajectory.</p>
		{/if}
	</div>

	{#if networkNodes.length > 0}
		<div class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
			<div class="flex items-center gap-2 mb-3">
				<Share2 class="w-4 h-4 text-purple-500" />
				<h3 class="text-lg font-semibold">Topics & Entities</h3>
			</div>
			<div class="h-[260px]">
				<NetworkGraph nodes={networkNodes} links={networkLinks} width={320} height={240} />
			</div>
		</div>
	{/if}
</div>
