// API Response Types

export interface Article {
	id: number;
	title: string;
	summary: string;
	section: string | null;
	location_name: string | null;
	date_published: string | null;
	word_count: number | null;
	events: Event[];
	url?: string;
	source_url?: string;
}

export interface Event {
	id?: number;
	title: string;
	start_time: string | null;
	location_name: string | null;
	description: string | null;
	article_id?: number;
}

export interface FeedDate {
	date: string;
	total: number;
	summarized: number;
}

export interface FeedResponse {
	date: string;
	count: number;
	items: Article[];
}

export interface FeedDatesResponse {
	dates: FeedDate[];
}

export interface SearchResult {
	article_id: number;
	title: string;
	section: string | null;
	summary: string | null;
	score: number;
}

export interface SimilarArticle {
	article_id: number;
	title: string;
	section: string | null;
	summary: string | null;
	distance?: number;
	score?: number;
}

export interface TrendingItem {
	kind: string;
	key: string;
	score: number;
	zscore: number | null;
	details: Record<string, any>;
}

export interface TimelineData {
	date: string;
	count: number;
	sum_score: number;
}

export interface EventsResponse {
	days: number;
	events: Record<string, Event[]>;
}

export interface FeedFilters {
	section?: string;
	search?: string;
}

export type TrendingKind = 'section' | 'publication' | 'tag' | 'entity' | 'topic';
