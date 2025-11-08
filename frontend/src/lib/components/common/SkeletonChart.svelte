<script lang="ts">
	export let type: 'bar' | 'line' | 'trend' = 'bar';
	export let height: number = 200;
</script>

<div class="w-full animate-pulse" style="height: {height}px;">
	{#if type === 'bar'}
		<div class="flex items-end justify-around h-full gap-2 pb-8">
			{#each [80, 60, 90, 45, 70, 85, 55, 65] as barHeight}
				<div 
					class="flex-1 bg-slate-200 dark:bg-slate-700 rounded-t transition-all"
					style="height: {barHeight}%;"
				></div>
			{/each}
		</div>
	{:else if type === 'line'}
		<div class="w-full h-full flex items-end px-4">
			<svg class="w-full h-full" viewBox="0 0 400 {height}">
				<path 
					d="M 0 {height * 0.6} Q 50 {height * 0.4}, 100 {height * 0.5} T 200 {height * 0.3} T 300 {height * 0.6} T 400 {height * 0.4}" 
					fill="none" 
					stroke="currentColor" 
					stroke-width="2"
					class="text-slate-300 dark:text-slate-600"
				/>
			</svg>
		</div>
	{:else if type === 'trend'}
		<div class="flex items-center gap-3 p-4">
			<div class="flex-1 space-y-2">
				<div class="h-4 bg-slate-200 dark:bg-slate-700 rounded w-3/4"></div>
				<div class="h-3 bg-slate-200 dark:bg-slate-700 rounded w-1/2"></div>
			</div>
			<div class="w-20 h-8 bg-slate-200 dark:bg-slate-700 rounded"></div>
		</div>
	{/if}
</div>
