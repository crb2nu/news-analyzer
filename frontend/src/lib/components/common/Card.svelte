<script lang="ts">
	import { cn } from '$lib/utils/cn';

	export let padding: boolean = true;
	export let hoverable: boolean = false;
	export let elevated: boolean = false;

	let className: string = '';
	export { className as class };
</script>

<div
	class={cn(
		'bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 transition-all duration-200',
		padding && 'p-6',
		elevated ? 'shadow-md hover:shadow-lg' : 'shadow-sm',
		hoverable && 'hover:shadow-md hover:-translate-y-0.5 hover:border-slate-300 dark:hover:border-slate-600 cursor-pointer',
		className
	)}
	on:click
>
	<slot />
</div>
