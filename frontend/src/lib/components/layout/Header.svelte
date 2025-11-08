<script lang="ts">
	import { page } from '$app/stores';
	import ThemeToggle from './ThemeToggle.svelte';

	const navItems = [
		{ href: '/', label: 'Feed', icon: '📰' },
		{ href: '/events', label: 'Events', icon: '📅' },
		{ href: '/discover', label: 'Discover', icon: '🔍' },
		{ href: '/analytics', label: 'Analytics', icon: '📊' }
	];

	$: currentPath = $page.url.pathname;
</script>

<header
	class="sticky top-0 z-50 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800"
>
	<div class="container mx-auto px-4">
		<div class="flex items-center justify-between h-16">
			<!-- Logo -->
			<div class="flex items-center gap-4">
				<a href="/" class="flex items-center gap-2">
					<span class="text-2xl">📰</span>
					<span class="text-xl font-bold hidden sm:inline">SW VA News Hub</span>
				</a>
			</div>

			<!-- Desktop Navigation -->
			<nav class="hidden md:flex items-center gap-1" aria-label="Main navigation">
				{#each navItems as item}
					<a
						href={item.href}
						class="px-4 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
						class:bg-slate-100={currentPath === item.href}
						class:dark:bg-slate-800={currentPath === item.href}
						aria-current={currentPath === item.href ? 'page' : undefined}
					>
						<span class="mr-2">{item.icon}</span>
						{item.label}
					</a>
				{/each}
			</nav>

			<!-- Theme Toggle -->
			<div class="flex items-center gap-2">
				<ThemeToggle />
			</div>
		</div>
	</div>
</header>
