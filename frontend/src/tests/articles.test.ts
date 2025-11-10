import { describe, expect, it } from 'vitest';
import type { Article } from '$lib/types/api';
import { computeArticleStats } from '$lib/utils/articles';

describe('computeArticleStats', () => {
	const baseArticles: Article[] = [
		{
			id: 1,
			title: 'A',
			summary: '...',
			section: 'Local',
			location_name: null,
			date_published: null,
			word_count: 500,
			events: []
		},
		{
			id: 2,
			title: 'B',
			summary: '...',
			section: 'Local',
			location_name: null,
			date_published: null,
			word_count: 250,
			events: [{ title: 'Hearing', start_time: null, location_name: null, description: null }]
		},
		{
			id: 3,
			title: 'C',
			summary: '...',
			section: 'Sports',
			location_name: null,
			date_published: null,
			word_count: null,
			events: []
		}
	];

	it('calculates totals, unread, and section info', () => {
		const stats = computeArticleStats(baseArticles, new Set([2]));

		expect(stats.total).toBe(3);
		expect(stats.unread).toBe(2);
		expect(stats.unreadPercent).toBeCloseTo(66.7, 1);
		expect(stats.withEvents).toBe(1);
		expect(stats.withEventsPercent).toBeCloseTo(33.3, 1);
		expect(stats.sectionCount).toBe(2);
		expect(stats.topSection).toEqual({ name: 'Local', count: 2 });
		expect(stats.averageWordCount).toBe(375);
	});

	it('handles empty lists', () => {
		const stats = computeArticleStats([], new Set());
		expect(stats).toEqual({
			total: 0,
			unread: 0,
			unreadPercent: 0,
			withEvents: 0,
			withEventsPercent: 0,
			sectionCount: 0,
			topSection: null,
			averageWordCount: null
		});
	});
});
