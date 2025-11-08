<script lang="ts">
	import { cn } from '$lib/utils/cn';

	export let padding: boolean = true;

	let className: string = '';
	export { className as class };
</script>

<div
	class={cn(
		'bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700',
		padding && 'p-6',
		className
	)}
>
	<slot />
</div>
