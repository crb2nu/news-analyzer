<script lang="ts">
	import { scaleLinear, scaleBand } from 'd3-scale';
	import { max } from 'd3-array';

	interface BarData {
		label: string;
		value: number;
		color?: string;
	}

	export let data: BarData[] = [];
	export let height: number = 300;
	export let showValues: boolean = true;
	export let title: string = '';
	export let horizontal: boolean = false;

	const defaultColor = 'rgb(59, 130, 246)'; // blue-500

	$: maxValue = max(data, (d) => d.value) || 1;

	$: xScale = horizontal
		? scaleLinear().domain([0, maxValue]).range([0, 100])
		: scaleBand().domain(data.map((d) => d.label)).range([0, 100]).padding(0.2);

	$: yScale = horizontal
		? scaleBand().domain(data.map((d) => d.label)).range([0, 100]).padding(0.2)
		: scaleLinear().domain([0, maxValue]).range([100, 0]);

	$: barWidth = horizontal ? 0 : xScale.bandwidth ? xScale.bandwidth() : 20;
	$: barHeight = horizontal ? (yScale.bandwidth ? yScale.bandwidth() : 20) : 0;
</script>

<div class="bar-chart">
	{#if title}
		<h3 class="text-sm font-semibold mb-3 text-slate-700 dark:text-slate-300">{title}</h3>
	{/if}

	{#if data.length > 0}
		{#if horizontal}
			<!-- Horizontal bars - auto height -->
			<div class="flex flex-col gap-2 py-2">
				{#each data as item, i}
					<div class="flex items-center gap-3">
						<div class="w-24 text-xs text-right text-slate-600 dark:text-slate-400 truncate">
							{item.label}
						</div>
						<div class="flex-1 relative">
							<div
								class="h-8 rounded transition-all duration-500 ease-out"
								style="width: {xScale(item.value)}%; background-color: {item.color || defaultColor}; min-width: 2px;"
							>
								{#if showValues && xScale(item.value) > 15}
									<span class="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-medium text-white">
										{Math.round(item.value)}
									</span>
								{/if}
							</div>
						</div>
					</div>
				{/each}
			</div>
		{:else}
			<!-- Vertical bars - fixed height -->
			<div class="relative" style="height: {height}px;">
				<div class="flex items-end justify-around h-full gap-2 pb-8">
					{#each data as item, i}
						{@const barHeightPx = ((item.value / maxValue) * (height - 60))}
						<div class="flex flex-col items-center" style="flex: 1; max-width: {100 / data.length}%;">
							<div class="w-full flex flex-col items-center justify-end" style="height: {height - 40}px;">
								<div
									class="w-full max-w-[80%] rounded-t transition-all duration-500 ease-out relative"
									style="height: {barHeightPx}px; background-color: {item.color || defaultColor}; min-height: 4px;"
								>
									{#if showValues && barHeightPx > 25}
										<span class="absolute top-2 left-1/2 -translate-x-1/2 text-xs font-medium text-white whitespace-nowrap">
											{Math.round(item.value)}
										</span>
									{/if}
								</div>
							</div>
							<div class="mt-2 text-xs text-slate-600 dark:text-slate-400 truncate w-full text-center px-1">
								{item.label}
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	{:else}
		<div class="flex items-center justify-center h-[{height}px] text-slate-400 dark:text-slate-600 text-sm">
			No data available
		</div>
	{/if}
</div>

<style>
	.bar-chart {
		width: 100%;
	}
</style>
