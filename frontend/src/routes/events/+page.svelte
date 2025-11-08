<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { getEvents } from '$lib/api/endpoints';
	import { formatDate, formatDateTime } from '$lib/utils/date';
	import Card from '$lib/components/common/Card.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import Button from '$lib/components/common/Button.svelte';
	import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';
	import EventTimeline from '$lib/components/events/EventTimeline.svelte';
	import { Calendar, List, Clock, MapPin } from 'lucide-svelte';

	type ViewMode = 'timeline' | 'list' | 'calendar';
	let viewMode: ViewMode = 'timeline';

	$: eventsQuery = createQuery({
		queryKey: ['events', 30],
		queryFn: () => getEvents(30),
		staleTime: 15 * 60 * 1000 // 15 minutes
	});

	$: eventsByDate = $eventsQuery.data?.events || {};
	$: allEvents = Object.values(eventsByDate).flat();
	$: sortedDates = Object.keys(eventsByDate).sort();
	$: totalEvents = sortedDates.reduce(
		(sum, date) => sum + (eventsByDate[date]?.length || 0),
		0
	);

	function setViewMode(mode: ViewMode) {
		viewMode = mode;
	}
</script>

<svelte:head>
	<title>Events - SW VA News Hub</title>
</svelte:head>

<div class="container mx-auto p-4 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-3xl font-bold mb-1">Community Events</h1>
			{#if totalEvents > 0}
				<p class="text-slate-600 dark:text-slate-400">
					{totalEvents} upcoming {totalEvents === 1 ? 'event' : 'events'}
				</p>
			{/if}
		</div>

		<!-- View mode toggle -->
		<div class="flex gap-2 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
			<button
				class="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded transition-colors"
				class:bg-white={viewMode === 'timeline'}
				class:shadow-sm={viewMode === 'timeline'}
				class:dark:bg-slate-700={viewMode === 'timeline'}
				class:text-blue-600={viewMode === 'timeline'}
				class:dark:text-blue-400={viewMode === 'timeline'}
				on:click={() => setViewMode('timeline')}
			>
				<Clock class="w-4 h-4" />
				Timeline
			</button>
			<button
				class="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded transition-colors"
				class:bg-white={viewMode === 'list'}
				class:shadow-sm={viewMode === 'list'}
				class:dark:bg-slate-700={viewMode === 'list'}
				class:text-blue-600={viewMode === 'list'}
				class:dark:text-blue-400={viewMode === 'list'}
				on:click={() => setViewMode('list')}
			>
				<List class="w-4 h-4" />
				List
			</button>
			<button
				class="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded transition-colors"
				class:bg-white={viewMode === 'calendar'}
				class:shadow-sm={viewMode === 'calendar'}
				class:dark:bg-slate-700={viewMode === 'calendar'}
				class:text-blue-600={viewMode === 'calendar'}
				class:dark:text-blue-400={viewMode === 'calendar'}
				on:click={() => setViewMode('calendar')}
			>
				<Calendar class="w-4 h-4" />
				Calendar
			</button>
		</div>
	</div>

	{#if $eventsQuery.isLoading}
		<div class="flex justify-center py-12">
			<LoadingSpinner size="lg" />
		</div>
	{:else if $eventsQuery.error}
		<div
			class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-6 text-center"
		>
			<p class="text-red-800 dark:text-red-200">
				Failed to load events: {$eventsQuery.error.message}
			</p>
			<button
				class="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
				on:click={() => $eventsQuery.refetch()}
			>
				Try Again
			</button>
		</div>
	{:else if totalEvents === 0}
		<div class="text-center py-12 text-slate-600 dark:text-slate-400">
			<Calendar class="w-16 h-16 mx-auto mb-4 opacity-50" />
			<p class="text-lg">No events detected yet</p>
			<p class="text-sm mt-2">Check back soon!</p>
		</div>
	{:else}
		<!-- Timeline View -->
		{#if viewMode === 'timeline'}
			<Card>
				<h2 class="text-xl font-semibold mb-4">Event Timeline</h2>
				<EventTimeline events={allEvents} height={400} />
			</Card>

			<!-- Upcoming events list below timeline -->
			<div class="mt-6">
				<h2 class="text-xl font-semibold mb-4">Upcoming Events</h2>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					{#each allEvents.slice(0, 6) as event}
						<Card>
							<h3 class="font-semibold mb-2">{event.title}</h3>

							<div class="space-y-1 text-sm text-slate-600 dark:text-slate-400 mb-3">
								{#if event.start_time}
									<div class="flex items-center gap-2">
										<Clock class="w-4 h-4" />
										<time datetime={event.start_time}>
											{formatDateTime(event.start_time)}
										</time>
									</div>
								{/if}

								{#if event.location_name}
									<div class="flex items-center gap-2">
										<MapPin class="w-4 h-4" />
										<span>{event.location_name}</span>
									</div>
								{/if}
							</div>

							{#if event.description}
								<p class="text-sm text-slate-700 dark:text-slate-300 mb-3">
									{event.description}
								</p>
							{/if}

							{#if event.article_id}
								<Button
									href="/articles/{event.article_id}/source"
									target="_blank"
									rel="noopener"
									size="sm"
									variant="ghost"
								>
									View source article ↗
								</Button>
							{/if}
						</Card>
					{/each}
				</div>
			</div>
		{/if}

		<!-- List View -->
		{#if viewMode === 'list'}
			<div class="space-y-6">
				{#each sortedDates as dateKey}
					<section>
						<h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
							<Calendar class="w-5 h-5" />
							{dateKey === 'unscheduled' ? 'Date to be announced' : formatDate(dateKey)}
							<Badge variant="default" size="sm">{eventsByDate[dateKey].length}</Badge>
						</h2>

						<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
							{#each eventsByDate[dateKey] as event}
								<Card>
									<h3 class="font-semibold mb-2">{event.title}</h3>

									<div class="space-y-1 text-sm text-slate-600 dark:text-slate-400 mb-3">
										{#if event.start_time}
											<div class="flex items-center gap-2">
												<Clock class="w-4 h-4" />
												<time datetime={event.start_time}>
													{formatDateTime(event.start_time)}
												</time>
											</div>
										{/if}

										{#if event.location_name}
											<div class="flex items-center gap-2">
												<MapPin class="w-4 h-4" />
												<span>{event.location_name}</span>
											</div>
										{/if}
									</div>

									{#if event.description}
										<p class="text-sm text-slate-700 dark:text-slate-300 mb-3">
											{event.description}
										</p>
									{/if}

									{#if event.article_id}
										<Button
											href="/articles/{event.article_id}/source"
											target="_blank"
											rel="noopener"
											size="sm"
											variant="ghost"
										>
											View source article ↗
										</Button>
									{/if}
								</Card>
							{/each}
						</div>
					</section>
				{/each}
			</div>
		{/if}

		<!-- Calendar View -->
		{#if viewMode === 'calendar'}
			<Card>
				<div class="text-center py-8 text-slate-600 dark:text-slate-400">
					<Calendar class="w-12 h-12 mx-auto mb-3 opacity-50" />
					<p class="text-sm">Calendar view coming soon</p>
					<p class="text-xs mt-2">Use Timeline or List view for now</p>
				</div>
			</Card>
		{/if}
	{/if}
</div>
