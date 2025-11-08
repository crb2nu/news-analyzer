import { fetchAPI } from './client';
import type {
	FeedDatesResponse,
	FeedResponse,
	FeedFilters,
	SearchResult,
	SimilarArticle,
	TrendingItem,
	TrendingKind,
	TimelineData,
	EventsResponse
} from '$lib/types/api';

// Feed endpoints
export async function getFeedDates(limit = 14): Promise<FeedDatesResponse> {
	return fetchAPI<FeedDatesResponse>(`/feed/dates?limit=${limit}`);
}

export async function getFeedArticles(
	date: string,
	filters: FeedFilters = {},
	limit = 50
): Promise<FeedResponse> {
	const params = new URLSearchParams({
		date_str: date,
		limit: String(limit)
	});

	if (filters.section) params.set('section', filters.section);
	if (filters.search) params.set('q', filters.search);

	return fetchAPI<FeedResponse>(`/feed?${params}`);
}

// Search endpoints
export async function searchArticles(query: string, limit = 20): Promise<SearchResult[]> {
	const params = new URLSearchParams({
		q: query,
		limit: String(Math.min(limit, 50))
	});
	return fetchAPI<SearchResult[]>(`/search?${params}`);
}

export async function getSimilarArticles(
	articleId: number,
	limit = 10
): Promise<SimilarArticle[]> {
	const params = new URLSearchParams({
		id: String(articleId),
		limit: String(Math.min(limit, 50))
	});
	return fetchAPI<SimilarArticle[]>(`/similar?${params}`);
}

// Analytics endpoints
export async function getTrending(
	kind: TrendingKind,
	date?: string,
	limit = 20
): Promise<TrendingItem[]> {
	const params = new URLSearchParams({
		kind,
		limit: String(limit)
	});
	if (date) params.set('date_str', date);

	return fetchAPI<TrendingItem[]>(`/analytics/trending?${params}`);
}

export async function getTimeline(
	kind: TrendingKind,
	key: string,
	days = 30
): Promise<TimelineData[]> {
	const params = new URLSearchParams({
		kind,
		key,
		days: String(days)
	});
	return fetchAPI<TimelineData[]>(`/analytics/timeline?${params}`);
}

// Events endpoints
export async function getEvents(days = 30): Promise<EventsResponse> {
	const params = new URLSearchParams({ days: String(days) });
	return fetchAPI<EventsResponse>(`/events?${params}`);
}
