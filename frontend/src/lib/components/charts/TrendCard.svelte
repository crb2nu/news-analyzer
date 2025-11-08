<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { getTimeline } from '$lib/api/endpoints';
	import Card from '../common/Card.svelte';
	import Badge from '../common/Badge.svelte';
	import HeatIndicator from './HeatIndicator.svelte';
	import Sparkline from './Sparkline.svelte';
	import { TrendingUp, TrendingDown, Minus } from 'lucide-svelte';

	export let kind: string;
	export let itemKey: string;
	export let score: number;
	export let zscore: number | null = null;
	export let details: any = null;
	export let clickable: boolean = true;

	$: timelineQuery = createQuery({
		queryKey: ['timeline', kind, itemKey],
		queryFn: () => getTimeline(kind, itemKey, 14),
		staleTime: 10 * 60 * 1000 // 10 minutes
	});

	$: trendDirection = zscore !== null && zscore > 1 ? 'up' : zscore !== null && zscore < -1 ? 'down' : 'neutral';

	function handleClick() {
		if (clickable) {
			// Could navigate to detailed view or filter by this item
			console.log('Clicked:', kind, itemKey);
		}
	}
</script>

<Card
	class={clickable ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}
	on:click={handleClick}
>
	<div class="flex items-start justify-between gap-3">
		<div class="flex-1 min-w-0">
			<div class="flex items-center gap-2 mb-1">
				<h3 class="font-semibold text-sm truncate">{itemKey}</h3>
				<Badge size="sm" variant="default">{kind}</Badge>
			</div>

			<div class="flex items-center gap-3 text-xs text-slate-600 dark:text-slate-400">
				<span class="flex items-center gap-1">
					<span class="font-medium">Score:</span>
					{score.toFixed(2)}
				</span>

				<HeatIndicator {zscore} size="sm" />

				{#if trendDirection === 'up'}
					<span class="flex items-center gap-1 text-green-600 dark:text-green-400">
						<TrendingUp class="w-3 h-3" />
						Trending
					</span>
				{:else if trendDirection === 'down'}
					<span class="flex items-center gap-1 text-blue-600 dark:text-blue-400">
						<TrendingDown class="w-3 h-3" />
						Declining
					</span>
				{:else}
					<span class="flex items-center gap-1 text-slate-500">
						<Minus class="w-3 h-3" />
						Stable
					</span>
				{/if}
			</div>

			{#if details && details.description}
				<p class="text-xs text-slate-600 dark:text-slate-400 mt-2 line-clamp-2">
					{details.description}
				</p>
			{/if}
		</div>

		<div class="flex-shrink-0">
			{#if $timelineQuery.data && $timelineQuery.data.length > 0}
				<Sparkline
					data={$timelineQuery.data}
					width={80}
					height={32}
					color={trendDirection === 'up' ? 'rgb(34, 197, 94)' : trendDirection === 'down' ? 'rgb(59, 130, 246)' : 'rgb(148, 163, 184)'}
				/>
			{/if}
		</div>
	</div>
</Card>
