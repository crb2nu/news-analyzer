<script lang="ts">
	import { scaleLinear, scaleTime } from 'd3-scale';
	import { area, line, curveMonotoneX } from 'd3-shape';
	import { extent, max } from 'd3-array';

	interface TimelineData {
		date: string;
		count: number;
		sum_score?: number;
	}

	export let data: TimelineData[] = [];
	export let height: number = 200;
	export let showArea: boolean = true;
	export let showLine: boolean = true;
	export let color: string = 'rgb(59, 130, 246)'; // blue-500
	export let title: string = '';
	export let yAxisLabel: string = 'Count';

	const margin = { top: 20, right: 20, bottom: 40, left: 50 };

	$: width = 800; // Will be responsive via CSS
	$: innerWidth = width - margin.left - margin.right;
	$: innerHeight = height - margin.top - margin.bottom;

	$: formattedData = data.map((d) => ({
		date: new Date(d.date),
		value: d.count
	})).sort((a, b) => a.date.getTime() - b.date.getTime());

	$: xScale = scaleTime()
		.domain(extent(formattedData, (d) => d.date) as [Date, Date] || [new Date(), new Date()])
		.range([0, innerWidth]);

	$: yScale = scaleLinear()
		.domain([0, max(formattedData, (d) => d.value) || 1])
		.range([innerHeight, 0])
		.nice();

	$: areaPath = area<{ date: Date; value: number }>()
		.x((d) => xScale(d.date))
		.y0(innerHeight)
		.y1((d) => yScale(d.value))
		.curve(curveMonotoneX);

	$: linePath = line<{ date: Date; value: number }>()
		.x((d) => xScale(d.date))
		.y((d) => yScale(d.value))
		.curve(curveMonotoneX);

	$: yTicks = yScale.ticks(5);
	$: xTicks = xScale.ticks(6);
</script>

<div class="timeline-chart">
	{#if title}
		<h3 class="text-sm font-semibold mb-2 text-slate-700 dark:text-slate-300">{title}</h3>
	{/if}

	{#if formattedData.length > 0}
		<svg class="w-full" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet">
			<g transform="translate({margin.left}, {margin.top})">
				<!-- Y-axis grid lines and labels -->
				{#each yTicks as tick}
					<g transform="translate(0, {yScale(tick)})">
						<line
							x1="0"
							x2={innerWidth}
							stroke="currentColor"
							stroke-opacity="0.1"
							class="text-slate-300 dark:text-slate-600"
						/>
						<text
							x="-10"
							y="0"
							dy="0.32em"
							text-anchor="end"
							font-size="11"
							class="fill-slate-600 dark:fill-slate-400"
						>
							{tick}
						</text>
					</g>
				{/each}

				<!-- Y-axis label -->
				<text
					x="-35"
					y={innerHeight / 2}
					text-anchor="middle"
					font-size="11"
					class="fill-slate-600 dark:fill-slate-400"
					transform="rotate(-90, -35, {innerHeight / 2})"
				>
					{yAxisLabel}
				</text>

				<!-- X-axis labels -->
				{#each xTicks as tick}
					<text
						x={xScale(tick)}
						y={innerHeight + 25}
						text-anchor="middle"
						font-size="10"
						class="fill-slate-600 dark:fill-slate-400"
					>
						{tick.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
					</text>
				{/each}

				<!-- Area fill -->
				{#if showArea && formattedData.length > 0}
					<path
						d={areaPath(formattedData) || ''}
						fill={color}
						fill-opacity="0.2"
					/>
				{/if}

				<!-- Line -->
				{#if showLine && formattedData.length > 0}
					<path
						d={linePath(formattedData) || ''}
						fill="none"
						stroke={color}
						stroke-width="2"
						stroke-linejoin="round"
						stroke-linecap="round"
					/>
				{/if}

				<!-- Data points -->
				{#each formattedData as d}
					<circle
						cx={xScale(d.date)}
						cy={yScale(d.value)}
						r="3"
						fill={color}
						class="cursor-pointer hover:opacity-80 transition-opacity"
					>
						<title>{d.date.toLocaleDateString()}: {d.value}</title>
					</circle>
				{/each}
			</g>
		</svg>
	{:else}
		<div class="flex items-center justify-center text-slate-400 dark:text-slate-600 text-sm" style="height: {height}px;">
			No data available
		</div>
	{/if}
</div>

<style>
	.timeline-chart {
		width: 100%;
	}
</style>
