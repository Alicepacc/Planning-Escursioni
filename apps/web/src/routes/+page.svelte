<script lang="ts">
	// Esplora (Fase 1): mappa dei sentieri dell'area pilota. Toccando un sentiero si apre
	// l'anteprima con le metriche ufficiali e il link alla scheda.
	import { resolve } from '$app/paths';
	import { generatedAsset } from '#lib/data/paths.ts';
	import MapView from '#lib/map/MapView.svelte';
	import DifficultyBadge from '#lib/components/DifficultyBadge.svelte';
	import { CAI_SCALES } from '#lib/hiking/difficulty.ts';
	import { formatDuration, formatKm, formatMeters } from '#lib/hiking/format.ts';
	import type { TrailDoc, TrailWayProps } from '#lib/data/types.ts';

	// vista iniziale: Lagorai centrale (proposta d'esempio); i sentieri locali compaiono da z11
	const START_BBOX: [number, number, number, number] = [11.46, 46.1, 11.64, 46.2];

	let selection = $state<{
		refs: string;
		scale: string;
		derived: boolean;
		docs: TrailDoc[];
	} | null>(null);
	let loading = $state(false);

	async function onTrailClick(ways: TrailWayProps[]) {
		const way = ways[0];
		const ids = [...new Set(ways.flatMap((w) => (w.cai ? w.cai.split(',') : [])))].slice(0, 4);
		selection = { refs: way.refs, scale: way.scale, derived: way.scale_derived, docs: [] };
		if (!ids.length) return;
		loading = true;
		const docs = await Promise.all(
			ids.map((id) =>
				fetch(generatedAsset(`data/sentieri/${id}.json`))
					.then((r) => (r.ok ? (r.json() as Promise<TrailDoc>) : null))
					.catch(() => null)
			)
		);
		loading = false;
		if (selection) selection.docs = docs.filter((d): d is TrailDoc => d !== null);
	}
</script>

<svelte:head>
	<title>Esplora – Cordata</title>
</svelte:head>

<div class="esplora">
	<div class="mappa">
		<MapView bbox={START_BBOX} label="Mappa dei sentieri dell'area pilota" {onTrailClick} />
	</div>

	<section class="foglio" aria-live="polite">
		{#if selection}
			<header>
				<h2>
					{#if selection.refs}Sentiero {selection.refs}{:else}Tratto di sentiero{/if}
				</h2>
				<button type="button" class="chiudi" onclick={() => (selection = null)} aria-label="Chiudi"
					>✕</button
				>
			</header>
			{#if loading}
				<p>Carico i dati del catasto…</p>
			{:else if selection.docs.length}
				<ul class="schede">
					{#each selection.docs as doc (doc.id)}
						<li>
							<a href={resolve('/sentiero/[id]', { id: doc.id })}>
								<span class="titolo">
									<DifficultyBadge code={doc.difficulty.cai} />
									<strong>{doc.ref}</strong>
									{doc.name || `${doc.from} – ${doc.to}`}
								</span>
								<span class="dati">
									{formatDuration(
										doc.official.duration_forward_min ?? doc.computed.cai_forward_min
									)} ·
									{formatKm(doc.official.distance_km ?? doc.computed.distance_km)} · ↗
									{formatMeters(doc.official.ascent_m ?? doc.computed.ascent_m)}
								</span>
							</a>
						</li>
					{/each}
				</ul>
			{:else}
				<p>
					Questo tratto non ha una scheda nel catasto CAI.
					{#if selection.scale}
						Difficoltà {selection.derived ? 'stimata dai dati OSM' : 'indicata'}:
						<DifficultyBadge code={selection.scale} />
					{/if}
				</p>
			{/if}
		{:else}
			<a class="evidenza" href={resolve('/itinerario/[slug]', { slug: 'val-d-inferno' })}>
				<span class="etichetta">Proposta d'esempio · CAI</span>
				<strong>Anello in Val d'Inferno e Cima Nassere (2253 m)</strong>
				<span>Catena del Lagorai · 7:00 h · <DifficultyBadge code="EE" /> · 15,5 km · ↗ 950 m</span>
			</a>
			<p class="aiuto">Tocca un sentiero sulla mappa per vederne i dati del catasto CAI.</p>
		{/if}
		<details class="legenda">
			<summary>Legenda</summary>
			<ul>
				{#each Object.values(CAI_SCALES) as s (s.code)}
					<li><i style="background:{s.color}"></i><DifficultyBadge code={s.code} /> {s.label}</li>
				{/each}
				<li><i class="tratteggio"></i>Difficoltà stimata dai dati OSM (non dichiarata dal CAI)</li>
			</ul>
		</details>
	</section>
</div>

<style>
	.esplora {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-height: 0;
		position: relative;
	}
	.mappa {
		position: relative;
		flex: 1;
		min-height: 55dvh;
	}
	.foglio {
		background: var(--surface);
		border-top: 1px solid var(--border);
		border-radius: 16px 16px 0 0;
		margin-top: -14px;
		position: relative;
		z-index: 2;
		padding: 0.75rem 1rem 0.5rem;
		box-shadow: 0 -4px 14px rgba(0, 0, 0, 0.12);
	}
	.foglio header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	h2 {
		margin: 0;
		font-size: 1.1rem;
	}
	.chiudi {
		min-width: 48px;
		min-height: 48px;
		border: 0;
		background: transparent;
		font-size: 1.2rem;
		color: var(--text);
	}
	.schede {
		list-style: none;
		padding: 0;
		margin: 0.25rem 0;
		display: grid;
		gap: 0.4rem;
	}
	.schede a,
	.evidenza {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 0.6rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: 12px;
		color: var(--text);
		text-decoration: none;
		min-height: 48px;
	}
	.titolo {
		display: flex;
		gap: 0.4rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.dati,
	.aiuto {
		color: var(--muted);
		font-size: 0.95rem;
	}
	.etichetta {
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--accent);
		font-weight: 700;
	}
	.aiuto {
		margin: 0.5rem 0 0;
	}
	.legenda {
		margin-top: 0.4rem;
		font-size: 0.9rem;
	}
	.legenda summary {
		min-height: 40px;
		display: flex;
		align-items: center;
		cursor: pointer;
	}
	.legenda ul {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.3rem;
	}
	.legenda i {
		display: inline-block;
		width: 22px;
		height: 4px;
		margin-right: 0.4rem;
		vertical-align: middle;
		border-radius: 2px;
	}
	.legenda .tratteggio {
		background: repeating-linear-gradient(90deg, #c0392b 0 6px, transparent 6px 10px);
	}
</style>
