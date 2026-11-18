<script lang="ts">
	// Informazioni su un sentiero toccato sulla mappa (ADR 0012): il catasto CAI è un livello della
	// mappa, non un elenco di escursioni.
	import { resolve } from '$app/paths';
	import { issueWarning, loadTrailIndex, trailIds } from '../data/trails';
	import type { TrailIndexEntry, TrailWayProps } from '../data/types';
	import { scaleInfo } from '../hiking/difficulty';
	import { formatDuration, formatKm, formatMeters } from '../hiking/format';
	import DifficultyBadge from './DifficultyBadge.svelte';

	interface Props {
		ways: TrailWayProps[];
		onclose: () => void;
	}
	let { ways, onclose }: Props = $props();

	let entries = $state<TrailIndexEntry[] | null>(null);
	const way = $derived(ways[0]);
	const refs = $derived(
		[...new Set(ways.flatMap((w) => (w.refs ?? '').split(/[;,]/).map((r) => r.trim())))].filter(
			Boolean
		)
	);

	$effect(() => {
		const ids = trailIds(ways);
		entries = null;
		void loadTrailIndex().then((idx) => {
			entries = ids.flatMap((id) => (idx.has(id) ? [idx.get(id)!] : [])).slice(0, 3);
		});
	});
</script>

<aside class="sentiero" aria-label="Informazioni sul sentiero" aria-live="polite">
	<div class="testa">
		<h2>
			{refs.length ? `Sentiero ${refs.join(', ')}` : 'Tratto di sentiero'}
		</h2>
		<button type="button" class="chiudi" onclick={onclose} aria-label="Chiudi">✕</button>
	</div>
	<p class="difficolta">
		<DifficultyBadge code={way?.scale || null} showLabel />
		{#if way?.scale_derived}
			<span class="nota">difficoltà stimata da OpenStreetMap, non dichiarata nel catasto</span>
		{:else if scaleInfo(way?.scale)}
			<span class="nota">{scaleInfo(way?.scale)?.description}</span>
		{/if}
	</p>
	{#if entries === null}
		<p class="nota">Carico i dati del catasto…</p>
	{:else if entries.length}
		{#each entries as t (t.id)}
			<div class="voce">
				<p>
					<strong
						>{t.ref ? `${t.ref} ` : ''}{t.name ||
							(t.from && t.to ? `${t.from} – ${t.to}` : '')}</strong
					>
				</p>
				<p class="numeri">
					{formatKm(t.km)} · ↗ {formatMeters(t.up)} · {formatDuration(t.min)}
					{#if t.sda === 4}· <span class="validato">validato nel catasto CAI</span>{/if}
				</p>
				{#if issueWarning(t.issues)}<p class="avviso">{issueWarning(t.issues)}</p>{/if}
				<a href={resolve('/sentiero/[id]', { id: t.id })}>Scheda del sentiero</a>
			</div>
		{/each}
	{:else}
		<p class="nota">
			Tratto della rete di OpenStreetMap senza scheda nel catasto CAI{way?.vis
				? ` (visibilità della traccia: ${way.vis})`
				: ''}.
		</p>
	{/if}
	<p class="piccolo">
		Rete dei sentieri: catasto CAI (OSM2CAI) e OpenStreetMap. Le escursioni proposte sono quelle
		delle sezioni CAI, nell'elenco.
	</p>
</aside>

<style>
	.sentiero {
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		border-radius: 12px;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
		padding: 0.5rem 0.8rem 0.6rem;
		max-height: 100%;
		overflow-y: auto;
		box-sizing: border-box;
	}
	.testa {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	h2 {
		margin: 0;
		font-size: 1.02rem;
	}
	.chiudi {
		min-width: 44px;
		min-height: 44px;
		border: 0;
		background: none;
		color: var(--text);
		font-size: 1.1rem;
		cursor: pointer;
	}
	p {
		margin: 0.2rem 0;
		font-size: 0.92rem;
	}
	.difficolta {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.nota,
	.piccolo {
		color: var(--muted);
	}
	.piccolo {
		font-size: 0.8rem;
		margin-top: 0.4rem;
	}
	.voce {
		border-top: 1px solid var(--border);
		padding-top: 0.3rem;
		margin-top: 0.3rem;
	}
	.voce a {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
	}
	.validato {
		color: var(--accent);
	}
	.avviso {
		border-left: 4px solid #b3261e;
		padding-left: 0.5rem;
	}
</style>
