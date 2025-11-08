<script lang="ts">
	import { scaleTime, scaleLinear } from 'd3-scale';
	import { extent } from 'd3-array';
	import type { Event } from '$lib/types/api';

	export let events: Event[] = [];
	export let height: number = 400;

	$: eventsWithDates = events
		.filter((e) => e.start_time)
		.map((e) => ({
			...e,
			date: new Date(e.start_time!)
		}))
		.sort((a, b) => a.date.getTime() - b.date.getTime());

	$: dateExtent = extent(eventsWithDates, (d) => d.date) as [Date, Date];

	$: xScale = scaleTime()
		.domain(dateExtent.length === 2 ? dateExtent : [new Date(), new Date()])
		.range([50, 100]);

	$: yPositions = eventsWithDates.reduce((acc, event, i) => {
		acc[event.event_id] = (i % 3) * 30 + 20;
		return acc;
	}, {} as Record<number, number>);

	let hoveredEvent: Event | null = null;

	function handleMouseEnter(event: Event) {
		hoveredEvent = event;
	}

	function handleMouseLeave() {
		hoveredEvent = null;
	}

	function formatDateTime(dateStr: string): string {
		const date = new Date(dateStr);
		return date.toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			hour: 'numeric',
			minute: '2-digit'
		});
	}
</script>

<div class="event-timeline relative" style="height: {height}px;">
	{#if eventsWithDates.length > 0}
		<svg class="w-full h-full">
			<!-- Timeline axis -->
			<line
				x1="50"
				y1={height - 50}
				x2="100%"
				y2={height - 50}
				stroke="currentColor"
				stroke-width="2"
				class="text-slate-300 dark:text-slate-600"
			/>

			<!-- Date markers -->
			{#each xScale.ticks(6) as tick}
				<g transform="translate({xScale(tick)}, 0)">
					<line
						x1="0"
						y1={height - 55}
						x2="0"
						y2={height - 45}
						stroke="currentColor"
						class="text-slate-400 dark:text-slate-500"
					/>
					<text
						y={height - 30}
						text-anchor="middle"
						font-size="11"
						class="fill-slate-600 dark:fill-slate-400"
					>
						{tick.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
					</text>
				</g>
			{/each}

			<!-- Event markers -->
			{#each eventsWithDates as event}
				{@const x = xScale(event.date)}
				{@const y = yPositions[event.event_id]}

				<!-- Connector line -->
				<line
					x1={x}
					y1={y + 12}
					x2={x}
					y2={height - 50}
					stroke="currentColor"
					stroke-width="1"
					stroke-dasharray="2,2"
					class="text-slate-300 dark:text-slate-600"
				/>

				<!-- Event circle -->
				<circle
					cx={x}
					cy={y + 12}
					r={hoveredEvent?.event_id === event.event_id ? 8 : 6}
					fill="rgb(59, 130, 246)"
					class="cursor-pointer transition-all hover:fill-blue-600"
					on:mouseenter={() => handleMouseEnter(event)}
					on:mouseleave={handleMouseLeave}
				>
					<title>{event.title}</title>
				</circle>

				<!-- Event label (show only if not crowded) -->
				<text
					x={x}
					y={y}
					text-anchor="middle"
					font-size="10"
					class="fill-slate-700 dark:fill-slate-300 pointer-events-none"
				>
					{event.title.slice(0, 20)}{event.title.length > 20 ? '...' : ''}
				</text>
			{/each}
		</svg>

		<!-- Hover tooltip -->
		{#if hoveredEvent}
			<div
				class="absolute bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-3 shadow-lg max-w-xs z-10"
				style="top: 10px; right: 10px;"
			>
				<h4 class="font-semibold mb-1 text-sm">{hoveredEvent.title}</h4>
				{#if hoveredEvent.start_time}
					<p class="text-xs text-slate-600 dark:text-slate-400 mb-1">
						📅 {formatDateTime(hoveredEvent.start_time)}
					</p>
				{/if}
				{#if hoveredEvent.location_name}
					<p class="text-xs text-slate-600 dark:text-slate-400 mb-1">
						📍 {hoveredEvent.location_name}
					</p>
				{/if}
				{#if hoveredEvent.description}
					<p class="text-xs text-slate-700 dark:text-slate-300 mt-2">
						{hoveredEvent.description.slice(0, 150)}...
					</p>
				{/if}
			</div>
		{/if}
	{:else}
		<div class="flex items-center justify-center h-full text-slate-400 dark:text-slate-600">
			No scheduled events
		</div>
	{/if}
</div>

<style>
	.event-timeline {
		width: 100%;
		overflow-x: auto;
	}
</style>
