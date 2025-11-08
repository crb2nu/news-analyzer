import { QueryClient } from '@tanstack/svelte-query';

export const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			staleTime: 5 * 60 * 1000, // 5 minutes
			gcTime: 30 * 60 * 1000, // 30 minutes (was cacheTime in v4)
			retry: 2,
			refetchOnWindowFocus: false,
			refetchOnReconnect: true
		}
	}
});
