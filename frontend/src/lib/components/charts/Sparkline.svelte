<script lang="ts">
	import { scaleLinear } from 'd3-scale';
	import { line, curveMonotoneX } from 'd3-shape';

	interface DataPoint {
		date: string;
		count: number;
		sum_score?: number;
	}

	export let data: DataPoint[] = [];
	export let width: number = 100;
	export let height: number = 24;
	export let color: string = 'currentColor';
	export let showDots: boolean = false;

	$: formattedData = data.map((d) => ({
		x: new Date(d.date).getTime(),
		y: d.count
	}));

	$: xDomain = formattedData.length > 0
		? [Math.min(...formattedData.map(d => d.x)), Math.max(...formattedData.map(d => d.x))]
		: [0, 1];

	$: yDomain = formattedData.length > 0
		? [0, Math.max(...formattedData.map(d => d.y))]
		: [0, 1];

	$: xScale = scaleLinear().domain(xDomain).range([2, width - 2]);
	$: yScale = scaleLinear().domain(yDomain).range([height - 2, 2]);

	$: linePath = line<{ x: number; y: number }>()
		.x((d) => xScale(d.x))
		.y((d) => yScale(d.y))
		.curve(curveMonotoneX);
</script>

<div class="sparkline" style="width: {width}px; height: {height}px;">
	{#if formattedData.length > 0}
		<svg width={width} height={height}>
			<path
				d={linePath(formattedData) || ''}
				fill="none"
				stroke={color}
				stroke-width="1.5"
				stroke-linejoin="round"
				stroke-linecap="round"
			/>
			{#if showDots}
				{#each formattedData as d}
					<circle
						cx={xScale(d.x)}
						cy={yScale(d.y)}
						r="2"
						fill={color}
					/>
				{/each}
			{/if}
		</svg>
	{:else}
		<svg width={width} height={height}>
			<line
				x1="0"
				y1={height / 2}
				x2={width}
				y2={height / 2}
				stroke={color}
				stroke-width="1"
				opacity="0.3"
				stroke-dasharray="2,2"
			/>
		</svg>
	{/if}
</div>

<style>
	.sparkline {
		display: inline-block;
		vertical-align: middle;
	}
</style>
