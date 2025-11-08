<script lang="ts">
	import { QueryClientProvider } from '@tanstack/svelte-query';
	import { queryClient } from '$lib/api/query-client';
	import Header from '$lib/components/layout/Header.svelte';
	import Footer from '$lib/components/layout/Footer.svelte';
	import '../app.css';
</script>

<QueryClientProvider client={queryClient}>
	<div class="flex flex-col min-h-screen">
		<Header />
		<main class="flex-1">
			<slot />
		</main>
		<Footer />
	</div>
</QueryClientProvider>
