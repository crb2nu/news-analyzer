<script lang="ts">
	/**
	 * Visual indicator for z-score (statistical significance)
	 * Z-score > 2 = hot/trending up
	 * Z-score < -2 = cold/trending down
	 */
	export let zscore: number | null;
	export let size: 'sm' | 'md' | 'lg' = 'md';

	$: sizeClasses = {
		sm: 'w-2 h-2',
		md: 'w-3 h-3',
		lg: 'w-4 h-4'
	};

	$: getColor = (z: number | null) => {
		if (z === null || z === undefined) return 'bg-slate-300 dark:bg-slate-600';
		if (z >= 3) return 'bg-red-600 dark:bg-red-500'; // Very hot
		if (z >= 2) return 'bg-orange-500 dark:bg-orange-400'; // Hot
		if (z >= 1) return 'bg-yellow-500 dark:bg-yellow-400'; // Warm
		if (z >= -1) return 'bg-slate-300 dark:bg-slate-500'; // Neutral
		if (z >= -2) return 'bg-blue-400 dark:bg-blue-500'; // Cool
		return 'bg-blue-600 dark:bg-blue-700'; // Cold
	};

	$: getLabel = (z: number | null) => {
		if (z === null || z === undefined) return 'No data';
		if (z >= 3) return 'Very Hot (Z ≥ 3)';
		if (z >= 2) return 'Hot (Z ≥ 2)';
		if (z >= 1) return 'Warm (Z ≥ 1)';
		if (z >= -1) return 'Neutral';
		if (z >= -2) return 'Cool (Z ≤ -1)';
		return 'Cold (Z ≤ -2)';
	};

	$: pulseClass = (z: number | null) => {
		if (z !== null && Math.abs(z) >= 2) return 'animate-pulse';
		return '';
	};
</script>

<div
	class="inline-flex items-center gap-1.5"
	title={getLabel(zscore)}
>
	<div class={`${sizeClasses[size]} ${getColor(zscore)} ${pulseClass(zscore)} rounded-full`}></div>
	{#if zscore !== null && zscore !== undefined}
		<span class="text-xs text-slate-600 dark:text-slate-400">
			Z: {zscore.toFixed(2)}
		</span>
	{/if}
</div>
