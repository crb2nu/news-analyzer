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
	let container: HTMLDivElement;
	let simulation: any;
	let transformedNodes: Node[] = [];
	let transformedLinks: Link[] = [];
	let hoveredNode: Node | null = null;
	let tooltipX = 0;
	let tooltipY = 0;
	let isDragging = false;
	let selectedNode: Node | null = null;
	let visibleTypes = new Set(['entity', 'topic', 'tag']);

	$: if (nodes.length > 0 && links.length > 0) {
		initializeGraph();
	}

	$: filteredNodes = transformedNodes.filter(n => visibleTypes.has(n.type));
	$: filteredLinks = transformedLinks.filter(l => {
		const source = typeof l.source === 'object' ? l.source : transformedNodes.find(n => n.id === l.source);
		const target = typeof l.target === 'object' ? l.target : transformedNodes.find(n => n.id === l.target);
		return source && target && visibleTypes.has(source.type) && visibleTypes.has(target.type);
	});

	function initializeGraph() {
		transformedNodes = nodes.map(n => ({ ...n }));
		transformedLinks = links.map(l => ({ ...l }));

		simulation = forceSimulation(transformedNodes)
			.force('link', forceLink(transformedLinks)
				.id((d: any) => d.id)
				.distance(120)
			)
			.force('charge', forceManyBody().strength(-400))
			.force('center', forceCenter(width / 2, height / 2))
			.force('collide', forceCollide(35))
			.on('tick', () => {
				transformedNodes = [...transformedNodes];
				transformedLinks = [...transformedLinks];
			});
	}

	function getNodeColor(type: string, isHovered: boolean = false, isSelected: boolean = false): string {
		const opacity = isHovered || isSelected ? '1' : '0.9';
		switch (type) {
			case 'entity': return isHovered || isSelected ? 'rgb(251, 146, 60)' : `rgba(251, 146, 60, ${opacity})`;
			case 'topic': return isHovered || isSelected ? 'rgb(139, 92, 246)' : `rgba(139, 92, 246, ${opacity})`;
			case 'tag': return isHovered || isSelected ? 'rgb(34, 197, 94)' : `rgba(34, 197, 94, ${opacity})`;
			default: return `rgba(148, 163, 184, ${opacity})`;
		}
	}

	function getNodeRadius(score: number): number {
		return Math.max(10, Math.min(30, score * 3.5));
	}

	function handleDragStart(event: MouseEvent, node: Node) {
		if (!simulation) return;
		isDragging = true;
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
		isDragging = false;
		if (!selectedNode || selectedNode.id !== node.id) {
			node.fx = null;
			node.fy = null;
		}
	}

	function handleNodeMouseEnter(event: MouseEvent, node: Node) {
		if (isDragging) return;
		hoveredNode = node;
		const svgRect = svg.getBoundingClientRect();
		tooltipX = event.clientX - svgRect.left;
		tooltipY = event.clientY - svgRect.top;
	}

	function handleNodeMouseMove(event: MouseEvent) {
		if (isDragging || !hoveredNode) return;
		const svgRect = svg.getBoundingClientRect();
		tooltipX = event.clientX - svgRect.left;
		tooltipY = event.clientY - svgRect.top;
	}

	function handleNodeMouseLeave() {
		if (!isDragging) {
			hoveredNode = null;
		}
	}

	function handleNodeClick(node: Node) {
		if (isDragging) return;
		selectedNode = selectedNode?.id === node.id ? null : node;
		if (selectedNode) {
			node.fx = node.x;
			node.fy = node.y;
		} else {
			node.fx = null;
			node.fy = null;
		}
	}

	function toggleType(type: string) {
		if (visibleTypes.has(type)) {
			visibleTypes.delete(type);
		} else {
			visibleTypes.add(type);
		}
		visibleTypes = new Set(visibleTypes);
	}

	onMount(() => {
		return () => {
			if (simulation) {
				simulation.stop();
			}
		};
	});
</script>

<div class="network-graph" bind:this={container}>
	<svg bind:this={svg} {width} {height} class="bg-slate-50 dark:bg-slate-900 rounded-lg">
		<g class="links">
			{#each filteredLinks as link}
				{@const source = typeof link.source === 'object' ? link.source : filteredNodes.find(n => n.id === link.source)}
				{@const target = typeof link.target === 'object' ? link.target : filteredNodes.find(n => n.id === link.target)}
				{#if source && target && source.x !== undefined && source.y !== undefined && target.x !== undefined && target.y !== undefined}
					<line
						x1={source.x}
						y1={source.y}
						x2={target.x}
						y2={target.y}
						stroke="currentColor"
						stroke-opacity="0.15"
						stroke-width={Math.sqrt(link.value)}
						class="text-slate-400 dark:text-slate-600 transition-all duration-300"
					/>
				{/if}
			{/each}
		</g>

		<g class="nodes">
			{#each filteredNodes as node}
				{#if node.x !== undefined && node.y !== undefined}
					{@const isHovered = hoveredNode?.id === node.id}
					{@const isSelected = selectedNode?.id === node.id}
					<g
						transform="translate({node.x}, {node.y})"
						class="cursor-pointer hover:opacity-100 transition-all duration-200"
						on:mousedown={(e) => handleDragStart(e, node)}
						on:mousemove={(e) => handleDrag(e, node)}
						on:mouseup={(e) => handleDragEnd(e, node)}
						on:mouseenter={(e) => handleNodeMouseEnter(e, node)}
						on:mousemove={handleNodeMouseMove}
						on:mouseleave={handleNodeMouseLeave}
						on:click={() => handleNodeClick(node)}
						role="button"
						tabindex={0}
						on:keydown={(e) => {
							if (e.key === 'Enter' || e.key === ' ') {
								handleNodeClick(node);
								e.preventDefault();
							}
						}}
					>
						{#if isHovered || isSelected}
							<circle
								r={getNodeRadius(node.score) + 6}
								fill={getNodeColor(node.type, true, false)}
								opacity="0.25"
								class="animate-pulse"
							/>
						{/if}

						<circle
							r={getNodeRadius(node.score)}
							fill={getNodeColor(node.type, isHovered, isSelected)}
							stroke="white"
							stroke-width={isSelected ? "3" : "2"}
							class="transition-all duration-200"
							style="filter: drop-shadow(0 4px 6px rgba(0, 0, 0, 0.1));"
						/>
						<text
							text-anchor="middle"
							dy=".3em"
							font-size={getNodeRadius(node.score) > 15 ? "11" : "9"}
							font-weight="600"
							fill="white"
			class="pointer-events-none select-none"
							style="text-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);"
						>
							{node.label.slice(0, getNodeRadius(node.score) > 15 ? 10 : 6)}
						</text>
					</g>
				{/if}
			{/each}
		</g>
	</svg>

	{#if hoveredNode && !isDragging}
		<div
			class="absolute bg-slate-900 dark:bg-slate-800 text-white px-3 py-2 rounded-lg shadow-xl text-sm z-10 pointer-events-none border border-slate-700"
			style="left: {tooltipX + 10}px; top: {tooltipY + 10}px; max-width: 200px;"
		>
			<div class="font-semibold mb-1">{hoveredNode.label}</div>
			<div class="text-xs text-slate-300 space-y-0.5">
				<div class="flex items-center justify-between">
					<span>Type:</span>
					<span class="capitalize font-medium">{hoveredNode.type}</span>
				</div>
				<div class="flex items-center justify-between">
					<span>Score:</span>
					<span class="font-medium">{hoveredNode.score.toFixed(2)}</span>
				</div>
			</div>
			<div class="text-xs text-slate-400 mt-1.5 pt-1.5 border-t border-slate-700">
				{selectedNode?.id === hoveredNode.id ? 'Click to unpin' : 'Click to pin'}
			</div>
		</div>
	{/if}

	<div class="mt-4 flex flex-wrap items-center justify-center gap-3 text-sm">
		{#each [{type: 'entity', color: 'orange', label: 'Entities'}, {type: 'topic', color: 'purple', label: 'Topics'}, {type: 'tag', color: 'green', label: 'Tags'}] as item}
			{@const isActive = visibleTypes.has(item.type)}
			<button
				class="flex items-center gap-2 px-3 py-2 rounded-lg transition-all duration-200 border-2"
				class:border-orange-400={item.color === 'orange' && isActive}
				class:bg-orange-50={item.color === 'orange' && isActive}
				class:border-purple-400={item.color === 'purple' && isActive}
				class:bg-purple-50={item.color === 'purple' && isActive}
				class:border-green-400={item.color === 'green' && isActive}
				class:bg-green-50={item.color === 'green' && isActive}
				class:border-transparent={!isActive}
				class:bg-slate-100={!isActive}
				class:dark:bg-slate-800={!isActive}
				class:opacity-60={!isActive}
				class:hover:opacity-100={true}
				on:click={() => toggleType(item.type)}
			>
				<div class="w-3 h-3 rounded-full shadow-sm" class:bg-orange-400={item.color === 'orange'} class:bg-purple-500={item.color === 'purple'} class:bg-green-500={item.color === 'green'}></div>
				<span class="text-slate-700 dark:text-slate-300 font-medium">{item.label}</span>
				<span class="text-xs bg-white dark:bg-slate-700 px-2 py-0.5 rounded-full font-semibold">
					{filteredNodes.filter(n => n.type === item.type).length}
				</span>
			</button>
		{/each}
	</div>

	<div class="mt-3 text-xs text-center text-slate-500">
		Drag nodes to rearrange • Click to pin/unpin • Click legend to filter types
	</div>
</div>

<style>
	.network-graph {
		width: 100%;
		position: relative;
	}
</style>
