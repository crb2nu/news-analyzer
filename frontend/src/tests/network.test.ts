import { describe, expect, it } from 'vitest';
import { buildInsightLinks, countNodesByType, type InsightNode } from '$lib/utils/network';

describe('buildInsightLinks', () => {
	const nodes: InsightNode[] = [
		{ id: 'entity-1', label: 'Town Council', type: 'entity', score: 4 },
		{ id: 'entity-2', label: 'School Board', type: 'entity', score: 3 },
		{ id: 'topic-1', label: 'Budget', type: 'topic', score: 5 },
		{ id: 'topic-2', label: 'Elections', type: 'topic', score: 2 },
		{ id: 'tag-1', label: 'education', type: 'tag', score: 3 }
	];

	it('connects topics -> entities and tags -> topics/entities', () => {
		const links = buildInsightLinks(nodes);
		expect(links.length).toBeGreaterThan(0);
		const hasTopicToEntity = links.some((link) => link.source === 'topic-1' && link.target === 'entity-1');
		const hasTagToTopic = links.some((link) => link.source === 'tag-1' && link.target?.startsWith('topic'));
		expect(hasTopicToEntity).toBe(true);
		expect(hasTagToTopic).toBe(true);
	});

	it('falls back to chaining when only one type exists', () => {
		const simpleNodes: InsightNode[] = [
			{ id: 'entity-1', label: 'Fire Dept', type: 'entity', score: 2 },
			{ id: 'entity-2', label: 'Police', type: 'entity', score: 3 }
		];
		const links = buildInsightLinks(simpleNodes);
		expect(links).toHaveLength(1);
		expect(links[0]).toEqual(expect.objectContaining({ source: 'entity-1', target: 'entity-2' }));
	});
});

describe('countNodesByType', () => {
	it('counts node types', () => {
		const nodes: InsightNode[] = [
			{ id: '1', label: 'A', type: 'entity', score: 1 },
			{ id: '2', label: 'B', type: 'entity', score: 1 },
			{ id: '3', label: 'C', type: 'topic', score: 1 }
		];
		const counts = countNodesByType(nodes);
		expect(counts).toEqual({ entity: 2, topic: 1, tag: 0 });
	});
});
