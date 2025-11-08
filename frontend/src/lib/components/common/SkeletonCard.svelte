<script lang="ts">
	export let rows: number = 3;
	export let showImage: boolean = false;
</script>

<div class="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6 animate-pulse">
	{#if showImage}
		<div class="w-full h-32 bg-slate-200 dark:bg-slate-700 rounded-lg mb-4"></div>
	{/if}
	
	<div class="space-y-3">
		<div class="h-5 bg-slate-200 dark:bg-slate-700 rounded w-3/4"></div>
		
		{#each Array(rows) as _, i}
			<div class="h-4 bg-slate-200 dark:bg-slate-700 rounded" style="width: {90 - i * 10}%"></div>
		{/each}
		
		<div class="flex gap-2 mt-4">
			<div class="h-6 w-16 bg-slate-200 dark:bg-slate-700 rounded-full"></div>
			<div class="h-6 w-20 bg-slate-200 dark:bg-slate-700 rounded-full"></div>
		</div>
	</div>
</div>
