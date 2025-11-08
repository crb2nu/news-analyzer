<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { Search, X } from 'lucide-svelte';
	import Select from '../common/Select.svelte';
	import Input from '../common/Input.svelte';
	import Button from '../common/Button.svelte';
	import { formatDateOption } from '$lib/utils/date';
	import type { FeedDate } from '$lib/types/api';

	export let selectedDate: string;
	export let dates: FeedDate[] = [];
	export let selectedSection: string = '';
	export let sections: Array<{ name: string; count: number }> = [];
	export let searchQuery: string = '';
	export let eventsOnly: boolean = false;
	export let hideRead: boolean = false;

	const dispatch = createEventDispatcher<{
		dateChange: string;
		sectionChange: string;
		searchChange: string;
		eventsOnlyChange: boolean;
		hideReadChange: boolean;
		refresh: void;
		clearSearch: void;
	}>();
</script>

<div
	class="flex flex-wrap items-end gap-4 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 mb-6"
>
	<!-- Date Selection -->
	<div class="flex flex-col gap-1 min-w-[200px]">
		<label for="date-select" class="text-sm font-medium text-slate-700 dark:text-slate-300">
			Date
		</label>
		<Select
			id="date-select"
			value={selectedDate}
			on:change={(e) => {
				const target = e.target;
				if (target instanceof HTMLSelectElement) {
					dispatch('dateChange', target.value);
				}
			}}
			aria-label="Select date"
		>
			{#each dates as { date, total, summarized }}
				<option value={date}>
					{formatDateOption(date, total, summarized)}
				</option>
			{/each}
		</Select>
	</div>

	<!-- Section Filter -->
	<div class="flex flex-col gap-1 min-w-[200px]">
		<label for="section-select" class="text-sm font-medium text-slate-700 dark:text-slate-300">
			Section
		</label>
		<Select
			id="section-select"
			value={selectedSection}
			on:change={(e) => {
				const target = e.target;
				if (target instanceof HTMLSelectElement) {
					dispatch('sectionChange', target.value);
				}
			}}
			aria-label="Filter by section"
		>
			<option value="">All sections ({sections.reduce((sum, s) => sum + s.count, 0)})</option
			>
			{#each sections as { name, count }}
				<option value={name}>{name} ({count})</option>
			{/each}
		</Select>
	</div>

	<!-- Search -->
	<div class="flex flex-col gap-1 flex-1 min-w-[250px]">
		<label for="search-input" class="text-sm font-medium text-slate-700 dark:text-slate-300">
			Search
		</label>
		<div class="relative">
			<Input
				id="search-input"
				type="search"
				placeholder="Search title or summary..."
				value={searchQuery}
				on:input={(e) => {
					const target = e.target;
					if (target instanceof HTMLInputElement) {
						dispatch('searchChange', target.value);
					}
				}}
				class="pr-10"
			/>
			{#if searchQuery}
				<button
					class="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-slate-100 dark:hover:bg-slate-700 rounded"
					on:click={() => dispatch('clearSearch')}
					aria-label="Clear search"
				>
					<X class="w-4 h-4" />
				</button>
			{:else}
				<Search
					class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none"
				/>
			{/if}
		</div>
	</div>

	<!-- Toggles -->
	<div class="flex items-center gap-2">
		<label class="flex items-center gap-2 cursor-pointer">
			<input
				type="checkbox"
				checked={eventsOnly}
				on:change={(e) => dispatch('eventsOnlyChange', e.currentTarget.checked)}
				class="w-4 h-4 rounded border-slate-300 dark:border-slate-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-2"
			/>
			<span class="text-sm text-slate-700 dark:text-slate-300">Events only</span>
		</label>
	</div>

	<div class="flex items-center gap-2">
		<label class="flex items-center gap-2 cursor-pointer">
			<input
				type="checkbox"
				checked={hideRead}
				on:change={(e) => dispatch('hideReadChange', e.currentTarget.checked)}
				class="w-4 h-4 rounded border-slate-300 dark:border-slate-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-2"
			/>
			<span class="text-sm text-slate-700 dark:text-slate-300">Hide read</span>
		</label>
	</div>

	<!-- Refresh Button -->
	<div class="ml-auto">
		<Button variant="secondary" size="sm" on:click={() => dispatch('refresh')}>
			🔄 Refresh
		</Button>
	</div>
</div>
