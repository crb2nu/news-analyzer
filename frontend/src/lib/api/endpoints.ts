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
	EventsResponse,
	BrowseResponse,
	FacetsResponse
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

// Browse endpoints
export interface BrowseFilters {
	date_from?: string;
	date_to?: string;
	publications?: string[];
	sections?: string[];
	tags?: string[];
	q?: string;
	sort?: 'date_desc' | 'date_asc' | 'title';
}

export async function browseArticles(filters: BrowseFilters, limit = 50, offset = 0): Promise<BrowseResponse> {
	const params = new URLSearchParams({
		limit: String(limit),
		offset: String(offset),
		sort: filters.sort || 'date_desc'
	});
	if (filters.date_from) params.set('date_from', filters.date_from);
	if (filters.date_to) params.set('date_to', filters.date_to);
	if (filters.q) params.set('q', filters.q);
	if (filters.publications?.length) params.set('publication', filters.publications.join(','));
	if (filters.sections?.length) params.set('section', filters.sections.join(','));
	if (filters.tags?.length) params.set('tag', filters.tags.join(','));
	return fetchAPI<BrowseResponse>(`/articles/browse?${params}`);
}

export async function getFacets(date_from?: string, date_to?: string, q?: string): Promise<FacetsResponse> {
	const params = new URLSearchParams();
	if (date_from) params.set('date_from', date_from);
	if (date_to) params.set('date_to', date_to);
	if (q) params.set('q', q);
	return fetchAPI<FacetsResponse>(`/analytics/facets?${params}`);
}
