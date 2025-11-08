<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { getEvents } from '$lib/api/endpoints';
	import { formatDate, formatDateTime } from '$lib/utils/date';
	import Card from '$lib/components/common/Card.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import Button from '$lib/components/common/Button.svelte';
	import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';

	$: eventsQuery = createQuery({
		queryKey: ['events', 30],
		queryFn: () => getEvents(30),
		staleTime: 15 * 60 * 1000 // 15 minutes
	});

	$: eventsByDate = $eventsQuery.data?.events || {};
	$: sortedDates = Object.keys(eventsByDate).sort();
	$: totalEvents = sortedDates.reduce(
		(sum, date) => sum + (eventsByDate[date]?.length || 0),
		0
	);
</script>

<svelte:head>
	<title>Events - SW VA News Hub</title>
</svelte:head>

<div class="container mx-auto p-4 max-w-4xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-3xl font-bold">Community Events</h1>
		{#if totalEvents > 0}
			<Badge variant="primary">{totalEvents} events</Badge>
		{/if}
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
	{:else if sortedDates.length === 0}
		<div class="text-center py-12 text-slate-600 dark:text-slate-400">
			<p class="text-lg">No events detected yet</p>
			<p class="text-sm mt-2">Check back soon!</p>
		</div>
	{:else}
		<div class="space-y-6">
			{#each sortedDates as dateKey}
				<section>
					<h2 class="text-xl font-semibold mb-4">
						{dateKey === 'unscheduled' ? 'Date to be announced' : formatDate(dateKey)}
					</h2>

					<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
						{#each eventsByDate[dateKey] as event}
							<Card>
								<h3 class="font-semibold mb-2">{event.title}</h3>

								<div class="space-y-1 text-sm text-slate-600 dark:text-slate-400 mb-3">
									{#if event.start_time}
										<div class="flex items-center gap-2">
											<span>🕒</span>
											<time datetime={event.start_time}>
												{formatDateTime(event.start_time)}
											</time>
										</div>
									{/if}

									{#if event.location_name}
										<div class="flex items-center gap-2">
											<span>📍</span>
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
</div>
