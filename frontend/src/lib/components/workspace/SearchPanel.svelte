<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Input from '../common/Input.svelte';
	import Button from '../common/Button.svelte';
	import Badge from '../common/Badge.svelte';
	import LoadingSpinner from '../common/LoadingSpinner.svelte';
	import type { SearchResult } from '$lib/types/api';
	import { Search } from 'lucide-svelte';

	export let query = '';
	export let debouncedQuery = '';
	export let isLoading = false;
	export let results: SearchResult[] = [];

	const dispatch = createEventDispatcher({
		queryChange: (value: string) => value,
		focusArticle: (id: number) => id,
		showSimilar: (id: number) => id
	});
</script>

<div class="space-y-4">
	<div class="relative">
		<Input
			type="search"
			placeholder="Global search (BM25)"
			value={query}
			on:input={(e) => dispatch('queryChange', (e.target as HTMLInputElement).value)}
			class="pl-10"
		/>
		<Search class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
	</div>

	{#if isLoading}
		<div class="flex justify-center py-6">
			<LoadingSpinner />
		</div>
	{:else if debouncedQuery.length < 3}
		<p class="text-sm text-slate-500 dark:text-slate-400">
			Type at least 3 characters to search all editions.
		</p>
	{:else if results.length === 0}
		<p class="text-sm text-slate-500 dark:text-slate-400">
			No matches for “{debouncedQuery}”. Try another keyword.
		</p>
	{:else}
		<div class="space-y-3 max-h-[420px] overflow-y-auto pr-1">
			{#each results as result}
				<div
					class="p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 transition-colors"
				>
					<div class="flex items-start justify-between gap-2">
						<h3 class="font-semibold text-sm">{result.title}</h3>
						{#if result.section}
							<Badge size="sm">{result.section}</Badge>
						{/if}
					</div>
					{#if result.summary}
						<p class="text-xs text-slate-600 dark:text-slate-400 mt-2 line-clamp-2">
							{result.summary}
						</p>
					{/if}
					<div class="flex flex-wrap items-center gap-2 mt-3 text-xs text-slate-500">
						<span>Score {result.score.toFixed(2)}</span>
						<Button
							size="xs"
							variant="ghost"
							on:click={() => dispatch('focusArticle', result.article_id)}
						>
							Focus
						</Button>
						<Button
							size="xs"
							variant="ghost"
							on:click={() => dispatch('showSimilar', result.article_id)}
						>
							Similar
						</Button>
						<Button
							size="xs"
							variant="primary"
							href={`/articles/${result.article_id}/source`}
							target="_blank"
						>
							Open Source
						</Button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
