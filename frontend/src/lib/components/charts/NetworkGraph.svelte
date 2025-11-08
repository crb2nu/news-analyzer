<script lang="ts">
	import { onMount } from 'svelte';
	import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force';

	interface Node {
		id: string;
		label: string;
		type: 'entity' | 'topic' | 'tag';
		score: number;
		x?: number;
		y?: number;
		fx?: number | null;
		fy?: number | null;
	}

	interface Link {
		source: string | Node;
		target: string | Node;
		value: number;
	}

	export let nodes: Node[] = [];
	export let links: Link[] = [];
	export let width: number = 800;
	export let height: number = 600;

	let svg: SVGSVGElement;
	let simulation: any;
	let transformedNodes: Node[] = [];
	let transformedLinks: Link[] = [];

	$: if (nodes.length > 0 && links.length > 0) {
		initializeGraph();
	}

	function initializeGraph() {
		// Clone nodes and links to avoid mutating props
		transformedNodes = nodes.map(n => ({ ...n }));
		transformedLinks = links.map(l => ({ ...l }));

		// Create force simulation
		simulation = forceSimulation(transformedNodes)
			.force('link', forceLink(transformedLinks)
				.id((d: any) => d.id)
				.distance(100)
			)
			.force('charge', forceManyBody().strength(-300))
			.force('center', forceCenter(width / 2, height / 2))
			.force('collide', forceCollide(30))
			.on('tick', () => {
				transformedNodes = [...transformedNodes];
				transformedLinks = [...transformedLinks];
			});
	}

	function getNodeColor(type: string): string {
		switch (type) {
			case 'entity': return 'rgb(251, 146, 60)'; // orange
			case 'topic': return 'rgb(139, 92, 246)'; // purple
			case 'tag': return 'rgb(34, 197, 94)'; // green
			default: return 'rgb(148, 163, 184)'; // slate
		}
	}

	function getNodeRadius(score: number): number {
		return Math.max(8, Math.min(25, score * 3));
	}

	function handleDragStart(event: MouseEvent, node: Node) {
		if (!simulation) return;
		simulation.alphaTarget(0.3).restart();
		node.fx = node.x;
		node.fy = node.y;
	}

	function handleDrag(event: MouseEvent, node: Node) {
		if (node.fx === undefined || node.fy === undefined) return;
		const svgRect = svg.getBoundingClientRect();
		node.fx = event.clientX - svgRect.left;
		node.fy = event.clientY - svgRect.top;
	}

	function handleDragEnd(event: MouseEvent, node: Node) {
		if (!simulation) return;
		simulation.alphaTarget(0);
		node.fx = null;
		node.fy = null;
	}

	onMount(() => {
		return () => {
			if (simulation) {
				simulation.stop();
			}
		};
	});
</script>

<div class="network-graph">
	<svg bind:this={svg} {width} {height} class="bg-slate-50 dark:bg-slate-900 rounded-lg">
		<!-- Links -->
		<g class="links">
			{#each transformedLinks as link}
				{@const source = typeof link.source === 'object' ? link.source : transformedNodes.find(n => n.id === link.source)}
				{@const target = typeof link.target === 'object' ? link.target : transformedNodes.find(n => n.id === link.target)}
				{#if source && target && source.x !== undefined && source.y !== undefined && target.x !== undefined && target.y !== undefined}
					<line
						x1={source.x}
						y1={source.y}
						x2={target.x}
						y2={target.y}
						stroke="currentColor"
						stroke-opacity="0.2"
						stroke-width={Math.sqrt(link.value)}
						class="text-slate-400 dark:text-slate-600"
					/>
				{/if}
			{/each}
		</g>

		<!-- Nodes -->
		<g class="nodes">
			{#each transformedNodes as node}
				{#if node.x !== undefined && node.y !== undefined}
					<g
						transform="translate({node.x}, {node.y})"
						class="cursor-move hover:opacity-80 transition-opacity"
						on:mousedown={(e) => handleDragStart(e, node)}
						on:mousemove={(e) => handleDrag(e, node)}
						on:mouseup={(e) => handleDragEnd(e, node)}
						role="button"
						tabindex="0"
					>
						<circle
							r={getNodeRadius(node.score)}
							fill={getNodeColor(node.type)}
							stroke="white"
							stroke-width="2"
						/>
						<text
							text-anchor="middle"
							dy=".3em"
							font-size="10"
							fill="white"
							class="pointer-events-none font-medium"
						>
							{node.label.slice(0, 8)}
						</text>
						<title>{node.label} ({node.type}) - Score: {node.score.toFixed(2)}</title>
					</g>
				{/if}
			{/each}
		</g>
	</svg>

	<!-- Legend -->
	<div class="mt-4 flex items-center justify-center gap-6 text-sm">
		<div class="flex items-center gap-2">
			<div class="w-4 h-4 rounded-full bg-orange-400"></div>
			<span class="text-slate-600 dark:text-slate-400">Entities</span>
		</div>
		<div class="flex items-center gap-2">
			<div class="w-4 h-4 rounded-full bg-purple-500"></div>
			<span class="text-slate-600 dark:text-slate-400">Topics</span>
		</div>
		<div class="flex items-center gap-2">
			<div class="w-4 h-4 rounded-full bg-green-500"></div>
			<span class="text-slate-600 dark:text-slate-400">Tags</span>
		</div>
	</div>
</div>

<style>
	.network-graph {
		width: 100%;
	}
</style>
