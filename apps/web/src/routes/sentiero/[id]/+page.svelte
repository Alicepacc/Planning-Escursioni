<script lang="ts">
	// Scheda di un sentiero del catasto CAI (OSM2CAI): valori ufficiali, valori calcolati come
	// confronto, profilo interattivo sincronizzato con la mappa.
	import MapView from '#lib/map/MapView.svelte';
	import ElevationProfile from '#lib/components/ElevationProfile.svelte';
	import MetricsHeader from '#lib/components/MetricsHeader.svelte';
	import SafetyNote from '#lib/components/SafetyNote.svelte';
	import { formatDate, formatDuration, formatKm, formatMeters } from '#lib/hiking/format.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const trail = $derived(data.trail);
	let index = $state<number | null>(null);
	const cursor = $derived<[number, number] | null>(
		index != null && trail.profile.points[index]
			? [trail.profile.points[index][2], trail.profile.points[index][3]]
			: null
	);
	const off = $derived(trail.official);
	const comp = $derived(trail.computed);
	const title = $derived.by(() => {
		const name = trail.name || (trail.from && trail.to ? `${trail.from} – ${trail.to}` : '');
		if (!trail.ref) return name;
		if (name.startsWith(trail.ref)) return name;
		return [trail.ref, name].filter(Boolean).join(' · ');
	});
	const ISSUE_LABELS: Record<string, string> = {
		percorribile: 'Percorribile',
		'parzialmente percorribile': 'Parzialmente percorribile',
		'non percorribile': 'Non percorribile',
		sconosciuto: 'Non rilevato'
	};
	const SDA: Record<number, string> = {
		3: 'rilevato, in attesa di validazione',
		4: 'validato e importato nel catasto (INFOMONT)'
	};
	const NETWORKS: Record<string, string> = {
		lwn: 'rete locale',
		rwn: 'rete regionale',
		nwn: 'rete nazionale',
		iwn: 'rete internazionale'
	};
</script>

<svelte:head>
	<title>Sentiero {title} – Cordata</title>
	<meta
		name="description"
		content="Sentiero {title}: tempi, difficoltà, dislivello e profilo dal catasto CAI."
	/>
</svelte:head>

<div class="mappa">
	<MapView bbox={trail.bbox} line={trail.line} {cursor} label="Mappa del sentiero {trail.ref}" />
</div>

<article class="pagina">
	<p class="tipo">Sentiero del catasto CAI</p>
	<h1>{title}</h1>
	{#if trail.from || trail.to}
		<p class="estremi">{trail.from || '?'} → {trail.to || '?'}</p>
	{/if}

	<MetricsHeader
		minutes={off.duration_forward_min ?? comp.cai_forward_min}
		minutesNote={off.duration_forward_min
			? `ufficiale; ritorno ${formatDuration(off.duration_backward_min)}`
			: 'calcolato, senza soste'}
		difficulty={trail.difficulty.cai}
		km={off.distance_km ?? comp.distance_km}
		up={off.ascent_m ?? comp.ascent_m}
		down={off.descent_m ?? comp.descent_m}
		source={off.duration_forward_min
			? 'Valori ufficiali del catasto CAI (OSM2CAI). Tempi netti, senza soste.'
			: 'Valori calcolati da Cordata: il catasto non riporta dati ufficiali per questo sentiero.'}
	/>

	<section>
		<h2>Profilo altimetrico</h2>
		<ElevationProfile points={trail.profile.points} bind:index />
	</section>

	<section class="percorribilita stato-{trail.issues.status.replaceAll(' ', '-')}">
		<h2>Stato di percorribilità</h2>
		<p>
			<strong>{ISSUE_LABELS[trail.issues.status] ?? trail.issues.status}</strong>
			{#if trail.issues.updated}· aggiornato il {formatDate(trail.issues.updated)}{/if}
		</p>
		{#if trail.issues.description}<p>{trail.issues.description}</p>{/if}
		<p class="nota">
			Segnalazione delle sezioni CAI e degli enti locali: non è capillare né in tempo reale. Prima
			di partire verifica eventuali ordinanze e chiusure.
		</p>
	</section>

	<section>
		<h2>Valori ufficiali e calcolati</h2>
		<table>
			<thead><tr><th></th><th>Catasto CAI</th><th>Calcolato</th></tr></thead>
			<tbody>
				<tr
					><th>Lunghezza</th><td>{formatKm(off.distance_km)}</td><td
						>{formatKm(comp.distance_km)}</td
					></tr
				>
				<tr
					><th>Salita</th><td>{formatMeters(off.ascent_m)}</td><td>{formatMeters(comp.ascent_m)}</td
					></tr
				>
				<tr
					><th>Discesa</th><td>{formatMeters(off.descent_m)}</td><td
						>{formatMeters(comp.descent_m)}</td
					></tr
				>
				<tr>
					<th>Tempo andata</th><td>{formatDuration(off.duration_forward_min)}</td>
					<td
						>{formatDuration(comp.cai_forward_min)}
						<span class="nota">(DIN {formatDuration(comp.din_forward_min)})</span></td
					>
				</tr>
				<tr>
					<th>Tempo ritorno</th><td>{formatDuration(off.duration_backward_min)}</td>
					<td
						>{formatDuration(comp.cai_backward_min)}
						<span class="nota">(DIN {formatDuration(comp.din_backward_min)})</span></td
					>
				</tr>
				<tr><th>Quota max</th><td>–</td><td>{formatMeters(comp.max_ele_m)}</td></tr>
			</tbody>
		</table>
		<p class="nota">
			Calcolo: quote {comp.method.dem}, un punto ogni {comp.method.step_m} m, media mobile su
			{comp.method.smoothing_m} m, soglia {comp.method.hysteresis_m} m; tempi con il modello
			{comp.method.time_model} (DIN 33466 come confronto). In caso di differenze prevalgono i valori del
			catasto.
		</p>
	</section>

	<section>
		<h2>Informazioni</h2>
		<ul class="info">
			{#if trail.network}<li>Rete: {NETWORKS[trail.network] ?? trail.network}</li>{/if}
			{#if trail.operator}<li>Gestore: {trail.operator}</li>{/if}
			{#if trail.sda}<li>
					Stato nel catasto: {SDA[trail.sda] ?? `sda ${trail.sda}`}{#if trail.validation_date},
						validato il {formatDate(trail.validation_date)}{/if}
				</li>{/if}
			{#if trail.osmc_symbol}<li>Segnavia: <code>{trail.osmc_symbol}</code></li>{/if}
		</ul>
		<p class="link">
			{#if trail.links.osm2cai}<a href={trail.links.osm2cai} rel="external noopener"
					>Scheda OSM2CAI</a
				>{/if}
			{#if trail.links.osm}<a href={trail.links.osm} rel="external noopener"
					>Relazione su OpenStreetMap</a
				>{/if}
		</p>
	</section>

	<SafetyNote />

	<footer class="attribuzione">
		{#each trail.attribution as a (a)}<span>{a}</span>{/each}
		<span>Dati aggiornati al {formatDate(trail.generated_at)}</span>
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
		margin: 0.1rem 0 0.2rem;
		font-size: 1.45rem;
		line-height: 1.25;
	}
	h2 {
		font-size: 1.1rem;
		margin: 1.25rem 0 0.4rem;
	}
	.estremi {
		margin: 0 0 0.75rem;
		color: var(--muted);
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
	.nota {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.percorribilita {
		border-left: 4px solid #8a8f94;
		padding-left: 0.75rem;
	}
	.stato-percorribile {
		border-color: #2f7a4f;
	}
	.stato-parzialmente-percorribile {
		border-color: #d9a21b;
	}
	.stato-non-percorribile {
		border-color: #b3261e;
	}
	.percorribilita p {
		margin: 0.2rem 0;
	}
	.info {
		padding-left: 1.1rem;
		margin: 0;
	}
	.link {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
	}
	.link a {
		min-height: 44px;
		display: inline-flex;
		align-items: center;
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
