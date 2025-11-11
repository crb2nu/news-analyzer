<script lang="ts">
	import { page } from '$app/stores';
	import { Menu, X } from 'lucide-svelte';
	import ThemeToggle from './ThemeToggle.svelte';

	const navItems = [
		{ href: '/', label: 'Workspace', icon: '⚡️' },
		{ href: '/browse', label: 'Browse', icon: '🧭' },
		{ href: '/events', label: 'Events', icon: '📅' },
		{ href: '/discover', label: 'Discover', icon: '🔍' },
		{ href: '/analytics', label: 'Analytics', icon: '📊' }
	];

	let mobileNavOpen = false;
	let lastPath = '';

	$: currentPath = $page.url.pathname;
	$: if (lastPath !== currentPath) {
		lastPath = currentPath;
		mobileNavOpen = false;
	}

	function toggleMobileNav() {
		mobileNavOpen = !mobileNavOpen;
	}

	function handleNavClick() {
		mobileNavOpen = false;
	}
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
						data-sveltekit-preload-data="hover"
					>
						<span class="mr-2">{item.icon}</span>
						{item.label}
					</a>
				{/each}
			</nav>

			<!-- Theme Toggle + Mobile Menu Button -->
			<div class="flex items-center gap-2">
				<ThemeToggle />
				<button
					type="button"
					class="md:hidden p-2 rounded-lg border border-slate-200 dark:border-slate-700"
					on:click={toggleMobileNav}
					aria-label={mobileNavOpen ? 'Close menu' : 'Open menu'}
					aria-expanded={mobileNavOpen}
					aria-controls="mobile-nav"
				>
					{#if mobileNavOpen}
						<X class="w-5 h-5" />
					{:else}
						<Menu class="w-5 h-5" />
					{/if}
				</button>
			</div>
		</div>
	</div>

	<!-- Mobile Navigation -->
	<div
		id="mobile-nav"
		class="md:hidden border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-lg"
		class:hidden={!mobileNavOpen}
		aria-hidden={!mobileNavOpen}
	>
		<nav class="container mx-auto px-4 py-4 space-y-1" aria-label="Mobile navigation">
			{#each navItems as item}
				<a
					href={item.href}
					class="flex items-center justify-between px-3 py-3 rounded-lg text-base font-medium transition-colors"
					class:bg-slate-100={currentPath === item.href}
					class:dark:bg-slate-800={currentPath === item.href}
					class:text-blue-600={currentPath === item.href}
					class:dark:text-blue-300={currentPath === item.href}
					class:hover:bg-slate-100={currentPath !== item.href}
					class:dark:hover:bg-slate-800={currentPath !== item.href}
					aria-current={currentPath === item.href ? 'page' : undefined}
					data-sveltekit-preload-data="hover"
					on:click={handleNavClick}
				>
					<div class="flex items-center gap-2">
						<span>{item.icon}</span>
						{item.label}
					</div>
					<span class="text-sm text-slate-500 dark:text-slate-400">Tap to open</span>
				</a>
			{/each}
		</nav>
	</div>
</header>
