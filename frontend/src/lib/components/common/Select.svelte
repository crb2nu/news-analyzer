<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import type { HTMLSelectAttributes } from 'svelte/elements';

	interface $$Props extends HTMLSelectAttributes {
		value?: string;
		error?: string;
	}

	export let value: string = '';
	export let error: string | undefined = undefined;

	let className: string = '';
	export { className as class };

	$: classes = cn(
		'px-3 py-2 border rounded-lg w-full',
		'bg-white dark:bg-slate-800',
		'text-slate-900 dark:text-slate-100',
		'focus:outline-none focus:ring-2 focus:ring-offset-2',
		error
			? 'border-red-500 focus:ring-red-500'
			: 'border-slate-300 dark:border-slate-700 focus:ring-blue-500',
		'disabled:opacity-50 disabled:cursor-not-allowed',
		className
	);
</script>

<div class="w-full">
	<select {...$$restProps} bind:value class={classes} on:change on:focus on:blur>
		<slot />
	</select>

	{#if error}
		<p class="mt-1 text-sm text-red-600 dark:text-red-400" role="alert">
			{error}
		</p>
	{/if}
</div>
