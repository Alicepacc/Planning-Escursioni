<script lang="ts">
	// Scheda grande per i caroselli di «Scopri»: forma del giro con la data della gita CAI.
	import Icon from './Icon.svelte';
	import DiffPill from './DiffPill.svelte';
	import RouteShape from './RouteShape.svelte';
	import { formatKm, formatMeters } from '../hiking/format';
	import type { ExploreItem } from '../search/explore';

	let { item, href }: { item: ExploreItem; href: string } = $props();
	const day = $derived(item.date ? new Date(item.date + 'T12:00:00') : null);
	const source = $derived(item.src.split(',')[0]);
</script>

<!-- href già risolto con resolve() da chi usa la scheda -->
<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
<a class="card" {href}>
	<span class="art">
		<RouteShape
			line={item.ln ?? []}
			width={252}
			height={118}
			stroke={3}
			dashed={!item.ok && (item.r ?? 0) < 80}
		/>
		{#if day}
			<span class="date">
				{day.toLocaleDateString('it-IT', { weekday: 'short' })}
				<b>{day.getDate()}</b>
				{day.toLocaleDateString('it-IT', { month: 'short' })}
			</span>
		{/if}
	</span>
	<span class="body">
		<span class="title">{item.t}</span>
		<span class="meta">{source}{item.sub ? ` · ${item.sub}` : ''}</span>
		<span class="stats">
			<DiffPill code={item.d} />
			{#if item.km}<span><Icon name="distanza" size={14} />{formatKm(item.km)}</span>{/if}
			{#if item.up}<span><Icon name="salita" size={14} />{formatMeters(item.up)}</span>{/if}
		</span>
	</span>
</a>

<style>
	.card {
		width: 15.75rem;
		flex: none;
		display: flex;
		flex-direction: column;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--r-lg);
		overflow: hidden;
		color: var(--text);
		text-decoration: none;
		scroll-snap-align: start;
	}
	.art {
		position: relative;
		height: 118px;
	}
	.date {
		position: absolute;
		top: 10px;
		left: 10px;
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 4px 8px;
		border-radius: 10px;
		background: var(--surface);
		box-shadow: var(--shadow);
		font: 700 0.72rem/1.1 var(--font-body);
	}
	.date b {
		font: 700 1.15rem/1 var(--font-display);
	}
	.body {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 0.65rem 0.8rem 0.8rem;
	}
	.title {
		font: 600 1rem/1.25 var(--font-body);
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.meta {
		color: var(--muted);
		font-size: 0.8rem;
	}
	.stats {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin-top: 0.35rem;
		font: 500 0.82rem var(--font-body);
	}
	.stats span {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
	}
	.stats :global(svg) {
		color: var(--muted);
	}
</style>
