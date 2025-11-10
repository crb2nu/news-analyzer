<script lang="ts">
	export let label: string;
	export let value: string | number;
	export let helper: string | null = null;
	export let accent: 'blue' | 'green' | 'purple' | 'orange' = 'blue';
</script>

<div
	class="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm"
>
	<p class="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
	<p
		class="mt-2 text-2xl font-semibold"
		class:text-blue-600={accent === 'blue'}
		class:text-green-600={accent === 'green'}
		class:text-purple-600={accent === 'purple'}
		class:text-orange-500={accent === 'orange'}
	>
		{value}
	</p>
	{#if helper}
		<p class="text-xs text-slate-500 dark:text-slate-400 mt-1">{helper}</p>
	{/if}
</div>
