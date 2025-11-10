import type { Article } from '$lib/types/api';

export interface ArticleStats {
	total: number;
	unread: number;
	unreadPercent: number;
	withEvents: number;
	withEventsPercent: number;
	sectionCount: number;
	topSection: { name: string; count: number } | null;
	averageWordCount: number | null;
}

function roundPercent(value: number, total: number): number {
	if (!total) return 0;
	return Math.round((value / total) * 1000) / 10; // one decimal place
}

export function computeArticleStats(
	articles: Article[],
	readIds: Set<number>
): ArticleStats {
	const total = articles.length;
	const sectionCounts: Record<string, number> = {};
	let unread = 0;
	let withEvents = 0;
	let wordCountSum = 0;
	let wordCountSamples = 0;

	for (const article of articles) {
		if (!readIds.has(article.id)) unread += 1;
		if (article.events?.length) withEvents += 1;
		if (article.word_count) {
			wordCountSum += article.word_count;
			wordCountSamples += 1;
		}

		const section = article.section || 'General';
		sectionCounts[section] = (sectionCounts[section] || 0) + 1;
	}

	const topSectionEntry = Object.entries(sectionCounts)
		.sort((a, b) => b[1] - a[1])
		.at(0);

	return {
		total,
		unread,
		unreadPercent: roundPercent(unread, total),
		withEvents,
		withEventsPercent: roundPercent(withEvents, total),
		sectionCount: Object.keys(sectionCounts).length,
		topSection: topSectionEntry ? { name: topSectionEntry[0], count: topSectionEntry[1] } : null,
		averageWordCount:
			wordCountSamples > 0 ? Math.round(wordCountSum / wordCountSamples) : null
	};
}
