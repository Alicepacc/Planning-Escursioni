<script lang="ts">
	// Riga dell'elenco (Scopri e Mappa): forma del giro, titolo, gruppo e tipo, numeri chiave,
	// difficoltà, affidabilità, fonte e data. Sostituisce la vecchia ResultCard (ADR 0015).
	import Icon from './Icon.svelte';
	import DiffPill from './DiffPill.svelte';
	import RouteShape from './RouteShape.svelte';
	import Trust from './Trust.svelte';
	import { formatDuration, formatKm, formatMeters } from '../hiking/format';
	import type { ExploreItem } from '../search/explore';

	let {
		item,
		href,
		selected = false,
		distanceKm = null,
		onfocusitem
	}: {
		item: ExploreItem;
		href: string;
		selected?: boolean;
		distanceKm?: number | null;
		onfocusitem?: (id: string) => void;
	} = $props();

	const TYPE: Record<string, string> = {
		anello: 'anello',
		traversata: 'traversata',
		andata_ritorno: 'andata e ritorno'
	};
	const source = $derived(item.src.split(',')[0]);
	const when = $derived(
		item.date
			? new Date(item.date + 'T12:00:00').toLocaleDateString('it-IT', {
					weekday: item.fut ? 'short' : undefined,
					day: 'numeric',
					month: 'short',
					year: item.fut ? undefined : 'numeric'
				})
			: ''
	);
</script>

<!-- href già risolto con resolve() da chi usa la riga -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<a
	class="row"
	class:sel={selected}
	{href}
	data-id={item.id}
	onmouseenter={() => onfocusitem?.(item.id)}
	onfocus={() => onfocusitem?.(item.id)}
>
	<!-- eslint-enable svelte/no-navigation-without-resolve -->
	<span class="thumb"><RouteShape line={item.ln ?? []} dashed={!item.ok} /></span>
	<span class="body">
		<span class="title">{item.t}</span>
		<span class="meta"
			>{item.sub}{item.sub ? ' · ' : ''}{TYPE[item.ty] ?? item.ty}{distanceKm != null
				? ` · a ${formatKm(distanceKm)}`
				: ''}</span
		>
		<span class="stats">
			<DiffPill code={item.d} />
			{#if item.km}<span><Icon name="distanza" size={14} />{formatKm(item.km)}</span>{/if}
			{#if item.up}<span><Icon name="salita" size={14} />{formatMeters(item.up)}</span>{/if}
			{#if item.min}<span><Icon name="tempo" size={14} />{formatDuration(item.min)}</span>{/if}
		</span>
		<span class="stats foot">
			<Trust ok={item.ok} noTrack={item.nt} />
			<span class="src">{source}{when ? ` · ${when}` : ''}</span>
		</span>
	</span>
</a>

<style>
	.row {
		display: flex;
		gap: 0.8rem;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--border);
		color: var(--text);
		text-decoration: none;
		align-items: flex-start;
	}
	.row.sel .thumb {
		box-shadow: 0 0 0 2.5px var(--rust);
	}
	.thumb {
		width: 74px;
		height: 74px;
		border-radius: var(--r-md);
		overflow: hidden;
		flex: none;
	}
	.body {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-width: 0;
		flex: 1;
	}
	.title {
		font: 600 1rem/1.25 var(--font-body);
	}
	.meta,
	.src {
		color: var(--muted);
		font-size: 0.82rem;
	}
	.stats {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.25rem 0.65rem;
		margin-top: 0.3rem;
		font: 500 0.82rem var(--font-body);
	}
	.stats span:not(.src) {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
	}
	.stats :global(svg) {
		color: var(--muted);
	}
	.foot {
		margin-top: 0.35rem;
	}
</style>
