<script lang="ts">
	import { onMount } from 'svelte';
	import { tweened } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';

	export let value: number;
	export let duration: number = 1000;
	export let decimals: number = 0;

	const displayValue = tweened(0, {
		duration,
		easing: cubicOut
	});

	$: displayValue.set(value);
</script>

<span>
	{$displayValue.toFixed(decimals)}
</span>
