<script lang="ts">
	// Card di Esplora (SPEC §5.1), dati in ordine fisso:
	// durata · km · D+ · badge difficoltà · mini-profilo · icona anello/traversata · fonte.
	import DifficultyBadge from './DifficultyBadge.svelte';
	import MiniProfile from './MiniProfile.svelte';
	import { formatDuration, formatKm, formatMeters } from '../hiking/format';
	import type { ExploreItem } from '../search/explore';

	interface Props {
		item: ExploreItem;
		href: string;
		selected?: boolean;
		distanceKm?: number | null;
		onfocusitem?: (id: string) => void;
	}
	let { item, href, selected = false, distanceKm = null, onfocusitem }: Props = $props();

	const ICON: Record<string, { glyph: string; label: string }> = {
		anello: { glyph: '↻', label: 'anello' },
		traversata: { glyph: '→', label: 'traversata' },
		andata_ritorno: { glyph: '⇄', label: 'andata e ritorno' }
	};
	const icon = $derived(ICON[item.ty] ?? ICON.traversata);
	const kind = $derived(
		item.k === 'a' ? 'Attività CAI' : item.k === 'i' ? 'Itinerario' : 'Sentiero'
	);
</script>

<!-- href già risolto con resolve() dalla pagina che usa la card -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<a
	class="card"
	class:sel={selected}
	{href}
	data-id={item.id}
	onmouseenter={() => onfocusitem?.(item.id)}
	onfocus={() => onfocusitem?.(item.id)}
>
	<!-- eslint-enable svelte/no-navigation-without-resolve -->
	<span class="riga1">
		<span class="tipo">{kind}</span>
		{#if item.k === 'a' && item.ok === false}<span
				class="verifica"
				title="Traccia ricostruita non ancora verificata">da verificare</span
			>{/if}
		{#if distanceKm != null}<span class="dist"
				>{distanceKm < 10 ? distanceKm.toFixed(1).replace('.', ',') : Math.round(distanceKm)} km da qui</span
			>{/if}
	</span>
	<strong class="titolo">{item.t}</strong>
	{#if item.sub}<span class="sub">{item.sub}</span>{/if}
	<span class="metriche">
		<span>{formatDuration(item.min)}</span>
		<span>{formatKm(item.km)}</span>
		<span>↗ {formatMeters(item.up)}</span>
		<DifficultyBadge code={item.d} />
		<MiniProfile values={item.p} />
		<span class="icona" title={icon.label} aria-label={icon.label}>{icon.glyph}</span>
	</span>
	<span class="fonte">{item.src}</span>
</a>

<style>
	.card {
		display: grid;
		gap: 0.2rem;
		padding: 0.7rem 0.85rem;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--surface);
		color: inherit;
		text-decoration: none;
	}
	.card:hover,
	.card.sel {
		border-color: var(--accent);
		box-shadow: 0 0 0 1px var(--accent);
	}
	.riga1 {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
	}
	.verifica {
		color: #9a6700;
		font-weight: 700;
	}
	.dist {
		margin-left: auto;
		text-transform: none;
		letter-spacing: 0;
	}
	.titolo {
		font-size: 1rem;
		line-height: 1.3;
	}
	.sub {
		font-size: 0.85rem;
		color: var(--muted);
	}
	.metriche {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem 0.7rem;
		align-items: center;
		font-variant-numeric: tabular-nums;
		font-size: 0.92rem;
	}
	.icona {
		font-size: 1.05rem;
		font-weight: 700;
	}
	.fonte {
		font-size: 0.8rem;
		color: var(--muted);
	}
</style>
