<script lang="ts">
	import { theme } from '$lib/stores/theme';
	import { Sun, Moon, Monitor } from 'lucide-svelte';

	function cycleTheme() {
		theme.update((current) => {
			if (current === 'light') return 'dark';
			if (current === 'dark') return 'system';
			return 'light';
		});
	}

	$: Icon = $theme === 'light' ? Sun : $theme === 'dark' ? Moon : Monitor;
</script>

<button
	on:click={cycleTheme}
	class="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
	aria-label="Toggle theme: {$theme}"
	title="Theme: {$theme}"
>
	<svelte:component this={Icon} class="w-5 h-5" />
</button>
