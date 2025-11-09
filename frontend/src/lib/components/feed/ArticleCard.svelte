<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { ExternalLink, Copy, Eye, EyeOff } from 'lucide-svelte';
	import type { Article } from '$lib/types/api';
	import Badge from '../common/Badge.svelte';
	import Button from '../common/Button.svelte';
	import { formatDateTime } from '$lib/utils/date';

	export let article: Article;
	export let read = false;

	const dispatch = createEventDispatcher<{
		toggleRead: number;
		copyLink: number;
	}>();

	function getSummaryParagraphs(summary: string): string[] {
		return summary
			.split(/\n{2,}/)
			.map((p) => p.trim())
			.filter(Boolean);
	}

	$: paragraphs = article.summary ? getSummaryParagraphs(article.summary) : [];
</script>

<article
    class="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6 transition-all duration-200 hover:shadow-md hover:border-slate-300 dark:hover:border-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
    class:opacity-60={read}
    class:hover:opacity-80={read}
    data-article-id={article.id}
    aria-labelledby="article-title-{article.id}"
>
	<!-- Header -->
	<div class="flex items-start justify-between gap-4 mb-3">
		<h2
			id="article-title-{article.id}"
			class="text-xl font-semibold leading-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors"
		>
			{article.title}
		</h2>

		{#if read}
			<Badge variant="secondary" size="sm">Read</Badge>
		{/if}
	</div>

	<!-- Metadata -->
	<div
		class="flex flex-wrap items-center gap-2 mb-4 text-sm text-slate-600 dark:text-slate-400"
	>
		{#if article.section}
			<Badge>{article.section}</Badge>
		{/if}

		{#if article.location_name}
			<span>📍 {article.location_name}</span>
		{/if}

		{#if article.date_published}
			<span>{formatDateTime(article.date_published)}</span>
		{/if}

		{#if article.word_count}
			<span>{article.word_count} words</span>
		{/if}

		{#if article.events?.length}
			<Badge variant="accent">
				📅 {article.events.length}
				{article.events.length === 1 ? 'event' : 'events'}
			</Badge>
		{/if}
	</div>

	<!-- Summary -->
	{#if paragraphs.length > 0}
		<div class="prose dark:prose-invert max-w-none mb-4">
			{#each paragraphs as paragraph}
				<p class="text-slate-700 dark:text-slate-300 mb-3 last:mb-0">
					{paragraph}
				</p>
			{/each}
		</div>
	{:else}
		<p class="text-slate-500 dark:text-slate-500 italic mb-4">Summary pending...</p>
	{/if}

	<!-- Events (inline preview) -->
	{#if article.events && article.events.length > 0}
		<div
			class="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-4"
		>
			<strong class="block mb-2">Upcoming Events:</strong>
			<ul class="space-y-1 text-sm">
				{#each article.events.slice(0, 3) as event}
					<li>
						{#if event.start_time}
							<time datetime={event.start_time}>
								{formatDateTime(event.start_time)}
							</time>
							{#if event.location_name}
								• {event.location_name}
							{/if}
						{:else}
							{event.title || 'Event'}
						{/if}
					</li>
				{/each}
			</ul>
			{#if article.events.length > 3}
				<p class="text-xs text-slate-600 dark:text-slate-400 mt-2">
					+{article.events.length - 3} more
				</p>
			{/if}
		</div>
	{/if}

	<!-- Actions -->
	<div
		class="flex items-center gap-2 pt-4 border-t border-slate-200 dark:border-slate-700"
	>
		<Button
			href="/articles/{article.id}/source"
			target="_blank"
			rel="noopener noreferrer"
			variant="primary"
			size="sm"
		>
			<ExternalLink class="w-4 h-4 mr-1" />
			Read Full Article
		</Button>

		<Button
			variant="ghost"
			size="sm"
			on:click={() => dispatch('toggleRead', article.id)}
			aria-label={read ? 'Mark as unread' : 'Mark as read'}
		>
			{#if read}
				<EyeOff class="w-4 h-4 mr-1" />
				Mark Unread
			{:else}
				<Eye class="w-4 h-4 mr-1" />
				Mark Read
			{/if}
		</Button>

		<Button
			variant="ghost"
			size="sm"
			on:click={() => dispatch('copyLink', article.id)}
			aria-label="Copy link"
		>
			<Copy class="w-4 h-4 mr-1" />
			Copy Link
		</Button>
	</div>
</article>
