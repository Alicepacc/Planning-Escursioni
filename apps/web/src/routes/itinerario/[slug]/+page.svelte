<script lang="ts">
	// Scheda di un itinerario (attività CAI ricostruita): valori dichiarati dalla sezione, che
	// prevalgono, e valori calcolati sulla traccia ricostruita come confronto (SPEC §8).
	import { resolve } from '$app/paths';
	import MapView from '#lib/map/MapView.svelte';
	import ElevationProfile from '#lib/components/ElevationProfile.svelte';
	import MetricsHeader from '#lib/components/MetricsHeader.svelte';
	import DifficultyBadge from '#lib/components/DifficultyBadge.svelte';
	import SafetyNote from '#lib/components/SafetyNote.svelte';
	import { formatDate, formatDuration, formatKm, formatMeters } from '#lib/hiking/format.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const it = $derived(data.itinerary);
	let index = $state<number | null>(null);
	const cursor = $derived<[number, number] | null>(
		index != null && it.profile.points[index]
			? [it.profile.points[index][2], it.profile.points[index][3]]
			: null
	);

	function hmToMinutes(hm: string): number {
		const [h, m] = hm.split(':').map(Number);
		return h * 60 + (m || 0);
	}

	// posizione dei punti chiave sulla traccia (dal profilo) per i marker numerati
	const stageMarkers = $derived(
		it.stages.map((s, i) => {
			const target = s.dist_km * 1000;
			const p = it.profile.points.reduce((best, q) =>
				Math.abs(q[0] - target) < Math.abs(best[0] - target) ? q : best
			);
			return { n: i + 1, name: s.name, lon: p[2], lat: p[3], dist_km: s.dist_km };
		})
	);
	// l'ultimo punto coincide con la partenza negli anelli: niente doppio marker
	const visibleMarkers = $derived(it.type === 'anello' ? stageMarkers.slice(0, -1) : stageMarkers);

	const checks = $derived.by(() => {
		const d = it.declared;
		const c = it.computed;
		const pct = (a: number, b: number) => ((a - b) / b) * 100;
		return [
			{
				label: 'Lunghezza',
				declared: formatKm(d.distance_km),
				computed: formatKm(c.distance_km),
				delta: `${pct(c.distance_km, d.distance_km).toFixed(1)}%`,
				ok: Math.abs(pct(c.distance_km, d.distance_km)) <= 10,
				rule: '±10%'
			},
			{
				label: 'Salita',
				declared: formatMeters(d.ascent_m),
				computed: formatMeters(c.ascent_m),
				delta: `${pct(c.ascent_m, d.ascent_m).toFixed(1)}%`,
				ok: Math.abs(pct(c.ascent_m, d.ascent_m)) <= 15,
				rule: '±15%'
			},
			{
				label: 'Discesa',
				declared: formatMeters(d.descent_m),
				computed: formatMeters(c.descent_m),
				delta: `${pct(c.descent_m, d.descent_m).toFixed(1)}%`,
				ok: Math.abs(pct(c.descent_m, d.descent_m)) <= 15,
				rule: '±15%'
			},
			{
				label: 'Quota massima',
				declared: formatMeters(d.max_ele_m),
				computed: formatMeters(c.max_ele_m),
				delta: `${c.max_ele_m - d.max_ele_m} m`,
				ok: Math.abs(c.max_ele_m - d.max_ele_m) <= 50,
				rule: '±50 m'
			}
		];
	});
	const allOk = $derived(checks.every((c) => c.ok));
	const loopClosed = $derived.by(() => {
		const a = it.line[0];
		const b = it.line[it.line.length - 1];
		return Math.hypot((a[0] - b[0]) * 77000, (a[1] - b[1]) * 111000) < 100;
	});
</script>

<svelte:head>
	<title>{it.title} – Cordata</title>
	<meta
		name="description"
		content="{it.title}: {it.declared.duration} h, {it.declared.difficulty}, {it.declared
			.distance_km} km, {it.declared.ascent_m} m di dislivello."
	/>
</svelte:head>

<div class="mappa">
	<MapView
		bbox={it.bbox}
		line={it.line}
		{cursor}
		stages={visibleMarkers}
		label="Mappa dell'itinerario"
	/>
</div>

<article class="pagina">
	<p class="tipo">Attività CAI · {it.type} · {it.group}</p>
	<h1>{it.title}</h1>

	<MetricsHeader
		minutes={hmToMinutes(it.declared.duration)}
		minutesNote="dichiarato dalla sezione"
		difficulty={it.difficulty.cai}
		km={it.declared.distance_km}
		up={it.declared.ascent_m}
		down={it.declared.descent_m}
		source="Valori dichiarati nella locandina. Tempo netto calcolato sulla traccia (modello CAI): {formatDuration(
			it.computed.cai_forward_min
		)}; con soste (+20%) {formatDuration(it.computed.cai_forward_min * 1.2)}."
	/>

	<section class="attivita">
		<h2>Gita in calendario</h2>
		<p>
			<strong>{formatDate(it.activity.date)}</strong> · partenza {it.start.nome} ({formatMeters(
				it.start.quota_m
			)}), {it.start.comune}{#if it.start.ora}, ore {it.start.ora}{/if}
		</p>
		<p>Organizzano: {it.activity.organizers.join(', ')}.</p>
		<p class="nota">
			{it.activity.signup_note}
			{#if it.activity.source_url}<a href={it.activity.source_url} rel="external noopener"
					>Locandina e iscrizione</a
				>{:else}Link alla locandina non disponibile: questa è la fixture di prova fornita
				dall'utente.{/if}
		</p>
	</section>

	<section>
		<h2>Profilo altimetrico</h2>
		<ElevationProfile
			points={it.profile.points}
			stages={stageMarkers.map((s) => ({ n: s.n, name: s.name, dist_km: s.dist_km }))}
			bind:index
		/>
	</section>

	<section>
		<h2>Tappe</h2>
		<ol class="tappe">
			{#each it.stages as s, i (i)}
				<li>
					<span class="n">{i + 1}</span>
					<span class="nome">{s.name}</span>
					<span class="dati"
						>{formatMeters(s.ele_m)} · km {s.dist_km.toFixed(1).replace('.', ',')} · {formatDuration(
							s.cai_min
						)}</span
					>
				</li>
			{/each}
		</ol>
		<p class="nota">Tempi cumulati netti con il modello CAI, senza soste.</p>
	</section>

	<section>
		<h2>Sentieri percorsi</h2>
		<ul class="sentieri">
			{#each it.trails.filter((t) => t.km_on_route >= 0.5) as t (t.relation_id)}
				<li>
					<DifficultyBadge code={t.cai} />
					{#if t.osm2cai_id}
						<a href={resolve('/sentiero/[id]', { id: t.osm2cai_id })}
							><strong>{t.ref}</strong> {t.name}</a
						>
					{:else}
						<span><strong>{t.ref}</strong> {t.name}</span>
					{/if}
					<span class="dati">{formatKm(t.km_on_route)}</span>
				</li>
			{/each}
		</ul>
		<p class="nota">
			Reti citate: {it.networks.join(', ')}. Fuori sentiero: {it.off_trail.join('; ')}.
		</p>
	</section>

	<section>
		<h2>Attrezzatura e note</h2>
		<ul>
			{#each it.equipment as e (e)}<li>{e}</li>{/each}
			{#each it.notes as n (n)}<li>{n}</li>{/each}
			<li>Cartografia: {it.map_reference}</li>
		</ul>
	</section>

	<section class="confronto">
		<h2>Traccia ricostruita: confronto con la locandina</h2>
		<p class="esito {allOk && loopClosed ? 'ok' : 'rivedere'}">
			{allOk && loopClosed
				? 'Entro le tolleranze (auto_ok)'
				: 'Da rivedere'}{#if it.type === 'anello'}
				· anello {loopClosed ? 'chiuso' : 'non chiuso'}{/if}
		</p>
		<table>
			<thead><tr><th></th><th>Locandina</th><th>Calcolato</th><th>Scarto</th></tr></thead>
			<tbody>
				{#each checks as c (c.label)}
					<tr>
						<th>{c.label}</th><td>{c.declared}</td><td>{c.computed}</td>
						<td class={c.ok ? 'ok' : 'ko'}
							>{c.delta} <span class="nota">({c.ok ? 'entro' : 'oltre'} {c.rule})</span></td
						>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="nota">
			{it.reconstruction} Tempo DIN 33466 sui valori calcolati: {formatDuration(
				it.computed.din_forward_min
			)}. Difficoltà: dichiarata {it.declared.difficulty}; i tag dei sentieri indicano E, il
			passaggio più impegnativo è il tratto fuori sentiero verso la cima.
		</p>
	</section>

	<SafetyNote />

	<footer class="attribuzione">
		{#each it.attribution as a (a)}<span>{a}</span>{/each}
	</footer>
</article>

<style>
	.mappa {
		position: relative;
		height: 42dvh;
		min-height: 260px;
	}
	.tipo {
		margin: 0.5rem 0 0;
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--accent);
		font-weight: 700;
	}
	h1 {
		margin: 0.1rem 0 0.75rem;
		font-size: 1.45rem;
		line-height: 1.25;
	}
	h2 {
		font-size: 1.1rem;
		margin: 1.25rem 0 0.4rem;
	}
	.attivita p {
		margin: 0.2rem 0;
	}
	.nota {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.tappe {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.3rem;
	}
	.tappe li {
		display: grid;
		grid-template-columns: 1.8rem 1fr;
		column-gap: 0.5rem;
		align-items: baseline;
	}
	.tappe .n {
		grid-row: span 2;
		background: #1f2933;
		color: #fff;
		border-radius: 50%;
		width: 1.6rem;
		height: 1.6rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
		font-size: 0.85rem;
	}
	.dati {
		color: var(--muted);
		font-size: 0.9rem;
	}
	.sentieri {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.35rem;
	}
	.sentieri li {
		display: grid;
		grid-template-columns: 3rem 1fr auto;
		gap: 0.5rem;
		align-items: center;
		min-height: 44px;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.95rem;
	}
	th,
	td {
		text-align: left;
		padding: 0.35rem 0.4rem;
		border-bottom: 1px solid var(--border);
	}
	thead th {
		font-size: 0.8rem;
		color: var(--muted);
	}
	.ok {
		color: #2f7a4f;
	}
	.ko {
		color: #b3261e;
	}
	.esito {
		font-weight: 700;
		margin: 0.2rem 0 0.5rem;
	}
	.attribuzione {
		margin-top: 1rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 0.75rem;
		font-size: 0.8rem;
		color: var(--muted);
	}
</style>
