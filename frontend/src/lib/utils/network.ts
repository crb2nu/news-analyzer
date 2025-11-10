export type InsightNodeType = 'entity' | 'topic' | 'tag';

export interface InsightNode {
	id: string;
	label: string;
	type: InsightNodeType;
	score: number;
}

export interface InsightLink {
	source: string;
	target: string;
	value: number;
}

function averageScore(a?: InsightNode, b?: InsightNode) {
	if (!a || !b) return 1;
	return Math.max(1, Math.round((a.score + b.score) / 2));
}

function connectGroups(
	links: InsightLink[],
	primary: InsightNode[],
	secondary: InsightNode[],
	weightAdjust = 1
) {
	if (!primary.length || !secondary.length) return;
	for (let i = 0; i < primary.length; i += 1) {
		const from = primary[i];
		const to = secondary[i % secondary.length];
		const value = Math.max(1, Math.round(averageScore(from, to) / weightAdjust));
		links.push({ source: from.id, target: to.id, value });
	}
}

export function buildInsightLinks(nodes: InsightNode[]): InsightLink[] {
	if (nodes.length < 2) return [];

	const entities = nodes.filter((n) => n.type === 'entity');
	const topics = nodes.filter((n) => n.type === 'topic');
	const tags = nodes.filter((n) => n.type === 'tag');

	const links: InsightLink[] = [];

	connectGroups(links, topics, entities, 2);
	connectGroups(links, tags, entities, 3);
	connectGroups(links, tags, topics, 3);

	if (!links.length) {
		// fallback chain to keep graph connected
		for (let i = 0; i < nodes.length - 1; i += 1) {
			links.push({
				source: nodes[i].id,
				target: nodes[i + 1].id,
				value: Math.max(1, Math.round(nodes[i].score))
			});
		}
	}

	const dedup = new Map<string, InsightLink>();
	for (const link of links) {
		const key = `${link.source}->${link.target}`;
		if (!dedup.has(key)) {
			dedup.set(key, link);
		}
	}

	return Array.from(dedup.values());
}

export function countNodesByType(nodes: InsightNode[]) {
	return nodes.reduce(
		(acc, node) => {
			acc[node.type] = (acc[node.type] || 0) + 1;
			return acc;
		},
		{ entity: 0, topic: 0, tag: 0 } as Record<InsightNodeType, number>
	);
}
