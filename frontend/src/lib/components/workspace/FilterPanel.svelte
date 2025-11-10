<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { FeedDate } from '$lib/types/api';
	import StatCard from './StatCard.svelte';
	import Input from '../common/Input.svelte';
	import Button from '../common/Button.svelte';

	export let dates: FeedDate[] = [];
	export let selectedDate = '';
	export let sections: Array<{ name: string; count: number }> = [];
	export let selectedSection = '';
	export let searchText = '';
	export let eventsOnly = false;
	export let hideRead = false;
	export let stats: Array<{ label: string; value: string | number; helper?: string; accent?: 'blue' | 'green' | 'purple' | 'orange' }> = [];

	const dispatch = createEventDispatcher({
		dateChange: (value: string) => value,
		sectionChange: (value: string) => value,
		searchChange: (value: string) => value,
		eventsOnlyChange: (value: boolean) => value,
		hideReadChange: (value: boolean) => value,
		refresh: () => undefined
	});

	function handleSectionToggle(section: string) {
		if (selectedSection === section) {
			dispatch('sectionChange', '');
		} else {
			dispatch('sectionChange', section);
		}
	}
</script>

<section class="space-y-6">
	<div class="space-y-2">
		<label class="text-sm font-semibold text-slate-700 dark:text-slate-200">Edition Date</label>
		<select
			class="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
			bind:value={selectedDate}
			on:change={(e) => dispatch('dateChange', (e.target as HTMLSelectElement).value)}
		>
			{#each dates as { date, total, summarized }}
				<option value={date}>
					{date} ({summarized}/{total})
				</option>
			{/each}
		</select>
	</div>

	<div class="space-y-2">
		<div class="flex items-center justify-between">
			<label class="text-sm font-semibold text-slate-700 dark:text-slate-200">Sections</label>
			{#if selectedSection}
				<button
					type="button"
					class="text-xs text-blue-600 dark:text-blue-400"
					on:click={() => dispatch('sectionChange', '')}
				>
					Clear
				</button>
			{/if}
		</div>
		<div class="flex flex-wrap gap-2">
			{#each sections as section}
				<button
					type="button"
					class="text-xs px-3 py-1 rounded-full border transition-colors"
					class:bg-blue-600={selectedSection === section.name}
					class:text-white={selectedSection === section.name}
					class:border-blue-600={selectedSection === section.name}
					class:bg-slate-100={selectedSection !== section.name}
					class:text-slate-700={selectedSection !== section.name}
					class:dark:bg-slate-800={selectedSection !== section.name}
					class:dark:text-slate-200={selectedSection !== section.name}
					class:dark:border-slate-700={selectedSection !== section.name}
					on:click={() => handleSectionToggle(section.name)}
				>
					{section.name}
					<span class="ml-1 text-[10px] opacity-70">{section.count}</span>
				</button>
			{/each}
		</div>
	</div>

	<div class="space-y-2">
		<label class="text-sm font-semibold text-slate-700 dark:text-slate-200">Keyword Filter</label>
		<Input
			placeholder="Search within summaries..."
			value={searchText}
			on:input={(e) => dispatch('searchChange', (e.target as HTMLInputElement).value)}
		/>
	</div>

	<div class="space-y-3">
		<label class="text-sm font-semibold text-slate-700 dark:text-slate-200">Options</label>
		<label class="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
			<input
				type="checkbox"
				checked={eventsOnly}
				on:change={(e) => dispatch('eventsOnlyChange', (e.target as HTMLInputElement).checked)}
				class="rounded border-slate-300"
			/>
			Events only
		</label>
		<label class="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
			<input
				type="checkbox"
				checked={hideRead}
				on:change={(e) => dispatch('hideReadChange', (e.target as HTMLInputElement).checked)}
				class="rounded border-slate-300"
			/>
			Hide read articles
		</label>
	</div>

	{#if stats.length}
		<div class="grid grid-cols-1 gap-3">
			{#each stats as stat}
				<StatCard
					label={stat.label}
					value={stat.value}
					helper={stat.helper ?? null}
					accent={stat.accent ?? 'blue'}
				/>
			{/each}
		</div>
	{/if}

	<Button variant="secondary" on:click={() => dispatch('refresh')} class="w-full">
		Refresh
	</Button>
</section>
