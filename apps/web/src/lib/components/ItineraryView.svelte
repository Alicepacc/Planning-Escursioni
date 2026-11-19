<script lang="ts">
	// Scheda di un itinerario o di un'attività CAI (SPEC §5.2), ispirata alla locandina: valori
	// dichiarati dalla sezione (prevalgono) e valori calcolati sulla traccia ricostruita, con
	// l'esito della verifica. Funziona anche quando la locandina non dichiara tutto.
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import MapView from '../map/MapView.svelte';
	import ElevationProfile from './ElevationProfile.svelte';
	import { planFromLine, planToParams } from '../planner/plan';
	import MetricsHeader from './MetricsHeader.svelte';
	import DifficultyBadge from './DifficultyBadge.svelte';
	import SafetyNote from './SafetyNote.svelte';
	import { formatDate, formatDuration, formatKm, formatMeters } from '../hiking/format';
	import { seasonMonths, seasonText } from '../hiking/season';
	import { download, fileName, toGpx, toKml, type TrackPoint } from '../export/gpx';
	import type { ItineraryDoc, TrailWayProps } from '../data/types';
	import TrailInfo from './TrailInfo.svelte';

	interface Props {
		doc: ItineraryDoc;
	}
	let { doc }: Props = $props();

	const TYPE_LABEL: Record<string, string> = {
		anello: 'anello',
		traversata: 'traversata',
		andata_ritorno: 'andata e ritorno'
	};

	let index = $state<number | null>(null);
	const cursor = $derived<[number, number] | null>(
		index != null && doc.profile.points[index]
			? [doc.profile.points[index][2], doc.profile.points[index][3]]
			: null
	);

	function hmToMinutes(hm: string | null): number | null {
		if (!hm) return null;
		const [h, m] = hm.split(':').map(Number);
		return h * 60 + (m || 0);
	}

	const isActivity = $derived(doc.kind === 'attivita');
	const verified = $derived(!doc.verification || doc.verification.status === 'auto_ok');
	// percorso non ricostruito (ADR 0013): solo i dati della locandina e i punti trovati
	const hasLine = $derived(doc.line.length >= 2);
	const d = $derived(doc.declared);
	const c = $derived(doc.computed);

	// metriche: dichiarate se ci sono, altrimenti calcolate (e lo si dice)
	// con una traccia non verificata i valori calcolati potrebbero essere falsi: solo i dichiarati
	const fromTrack = <T,>(value: T): T | null => (verified ? value : null);
	const minutes = $derived(hmToMinutes(d.duration) ?? fromTrack(Math.round(c.cai_forward_min)));
	const km = $derived(d.distance_km ?? fromTrack(c.distance_km));
	const up = $derived(d.ascent_m ?? fromTrack(c.ascent_m));
	const down = $derived(d.descent_m ?? fromTrack(c.descent_m));
	const maxEle = $derived(d.max_ele_m ?? fromTrack(c.max_ele_m));
	const computedFields = $derived(
		[
			d.duration == null && 'tempo',
			d.distance_km == null && 'lunghezza',
			d.ascent_m == null && 'salita',
			d.descent_m == null && 'discesa'
		].filter(Boolean) as string[]
	);

	const stageMarkers = $derived(
		hasLine
			? doc.stages.map((s, i) => {
					const target = s.dist_km * 1000;
					const p = doc.profile.points.reduce((best, q) =>
						Math.abs(q[0] - target) < Math.abs(best[0] - target) ? q : best
					);
					return { n: i + 1, name: s.name, lon: p[2], lat: p[3], dist_km: s.dist_km };
				})
			: (doc.places ?? []).map((p, i) => ({ n: i + 1, ...p, dist_km: 0 }))
	);
	// l'ultimo punto coincide con la partenza negli anelli e nelle andate e ritorno
	const visibleMarkers = $derived(
		!hasLine
			? stageMarkers.filter(
					(m, i) => i === 0 || i < stageMarkers.length - 1 || m.name !== stageMarkers[0].name
				)
			: doc.type === 'anello' || doc.type === 'andata_ritorno'
				? stageMarkers.slice(0, -1)
				: stageMarkers
	);

	const checks = $derived.by(() => {
		const pct = (a: number, b: number) => ((a - b) / b) * 100;
		const rows: {
			label: string;
			declared: string;
			computed: string;
			delta: string;
			ok: boolean;
			rule: string;
		}[] = [];
		if (d.distance_km != null)
			rows.push({
				label: 'Lunghezza',
				declared: formatKm(d.distance_km),
				computed: formatKm(c.distance_km),
				delta: `${pct(c.distance_km, d.distance_km).toFixed(1)}%`,
				ok: Math.abs(pct(c.distance_km, d.distance_km)) <= 10,
				rule: '±10%'
			});
		if (d.ascent_m != null)
			rows.push({
				label: 'Salita',
				declared: formatMeters(d.ascent_m),
				computed: formatMeters(c.ascent_m),
				delta: `${pct(c.ascent_m, d.ascent_m).toFixed(1)}%`,
				ok: Math.abs(pct(c.ascent_m, d.ascent_m)) <= 15,
				rule: '±15%'
			});
		if (d.max_ele_m != null)
			rows.push({
				label: 'Quota massima',
				declared: formatMeters(d.max_ele_m),
				computed: formatMeters(c.max_ele_m),
				delta: `${Math.round(c.max_ele_m - d.max_ele_m)} m`,
				ok: Math.abs(c.max_ele_m - d.max_ele_m) <= 50,
				rule: '±50 m'
			});
		return rows;
	});

	const trailScales = $derived(
		[...new Set(doc.trails.map((t) => t.cai).filter(Boolean))].join(', ')
	);
	const season = $derived(
		seasonText(seasonMonths(maxEle ?? c.max_ele_m, doc.difficulty.cai ?? doc.difficulty.raw))
	);

	// come arrivare: coordinate della partenza
	const startLon = $derived(doc.start.lon ?? doc.line[0]?.[0] ?? 0);
	const startLat = $derived(doc.start.lat ?? doc.line[0]?.[1] ?? 0);
	const coordText = $derived(`${startLat.toFixed(5)}, ${startLon.toFixed(5)}`);

	// sentiero toccato sulla mappa (catasto come livello della mappa, ADR 0012)
	let trailWays = $state<TrailWayProps[] | null>(null);

	// azioni
	let saved = $state(false);
	let shareNote = $state('');
	const KEY = 'cordata:salvati';
	const savedKey = $derived(`${doc.kind}:${doc.id}`);

	function readSaved(): { key: string; title: string; href: string }[] {
		try {
			return JSON.parse(localStorage.getItem(KEY) ?? '[]');
		} catch {
			return [];
		}
	}
	onMount(() => {
		saved = readSaved().some((s) => s.key === savedKey);
	});
	function toggleSave() {
		try {
			const list = readSaved().filter((s) => s.key !== savedKey);
			if (!saved) list.unshift({ key: savedKey, title: doc.title, href: location.pathname });
			localStorage.setItem(KEY, JSON.stringify(list.slice(0, 100)));
			saved = !saved;
		} catch {
			shareNote = 'Impossibile salvare in questo browser.';
		}
	}
	// planner: la traccia campionata ogni 800 m, agganciata ai sentieri, con la difficoltà della
	// scheda (EE ammessa se la gita è EE)
	const plannerHref = $derived.by(() => {
		const grade = (doc.difficulty.cai ?? doc.difficulty.raw ?? '').toUpperCase();
		const maxDiff = grade.startsWith('EEA')
			? 3
			: grade.startsWith('EE')
				? 2
				: grade.startsWith('T')
					? 0
					: 1;
		const plan = planFromLine(
			doc.line.map(([lon, lat]) => ({ lon, lat })),
			{ maxDiff, name: doc.title }
		);
		return `${resolve('/pianifica')}?${planToParams(plan)}`;
	});
	// «Organizza un'uscita» precompilata con titolo, scheda e difficoltà
	const outingHref = $derived.by(() => {
		const params: [string, string][] = [['titolo', doc.title]];
		if (typeof location !== 'undefined') {
			params.push(['da', location.pathname.replace(resolve('/'), '/')]);
		}
		const grade = doc.difficulty.cai ?? doc.difficulty.raw;
		if (grade) params.push(['difficolta', grade]);
		const query = params.map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
		return `${resolve('/uscite/nuova')}?${query}`;
	});
	const trackPoints = $derived<TrackPoint[]>(doc.profile.points.map((p) => [p[2], p[3], p[1]]));
	const sourceText = $derived(`${doc.attribution.join(' · ')} · generato da Cordata`);
	function exportGpx() {
		const wpts = stageMarkers.map((s, i) => ({
			name: `${s.n}. ${s.name}`,
			lon: s.lon,
			lat: s.lat,
			ele: doc.stages[i]?.ele_m
		}));
		download(
			toGpx(doc.title, trackPoints, wpts, sourceText),
			fileName(doc.title, 'gpx'),
			'application/gpx+xml'
		);
	}
	function exportKml() {
		download(
			toKml(doc.title, trackPoints, sourceText),
			fileName(doc.title, 'kml'),
			'application/vnd.google-earth.kml+xml'
		);
	}
	async function share() {
		const data = { title: doc.title, text: doc.summary ?? doc.title, url: location.href };
		try {
			if (navigator.share) {
				await navigator.share(data);
				return;
			}
			await navigator.clipboard.writeText(location.href);
			shareNote = 'Link copiato.';
		} catch {
			shareNote = '';
		}
	}
</script>

<svelte:head>
	<title>{doc.title} – Cordata</title>
	<meta
		name="description"
		content={doc.summary ?? `${doc.title}: ${formatKm(km)}, ${formatMeters(up)} di dislivello.`}
	/>
</svelte:head>

<div class="mappa">
	<MapView
		bbox={doc.bbox}
		line={doc.line}
		lineColor="#174ea6"
		lineDashed={!verified}
		{cursor}
		stages={visibleMarkers}
		label="Mappa dell'itinerario"
		legend={['percorso']}
		onTrailClick={(ways) => (trailWays = ways)}
	/>
	{#if trailWays}
		<div class="info-sentiero">
			<TrailInfo ways={trailWays} onclose={() => (trailWays = null)} />
		</div>
	{/if}
</div>

<article class="pagina">
	<p class="tipo">
		{isActivity ? 'Attività CAI' : 'Itinerario'} · {TYPE_LABEL[doc.type] ?? doc.type}{#if doc.group}
			· {doc.group}{/if}
	</p>
	<h1>{doc.title}</h1>
	{#if doc.summary}<p class="sintesi">{doc.summary}</p>{/if}

	{#if !hasLine}
		<details class="avviso" open>
			<summary>Percorso non disponibile sulla mappa</summary>
			<p>
				Non è stato possibile ricostruire il percorso dai dati della locandina: sulla mappa ci sono
				solo la partenza e i punti trovati. Per l'itinerario fa fede la locandina originale.
			</p>
			{#if doc.verification?.reasons.length}
				<ul>
					{#each doc.verification.reasons as r (r)}<li>{r}</li>{/each}
				</ul>
			{/if}
		</details>
	{:else if !verified}
		<details class="avviso" open>
			<summary>Traccia ricostruita automaticamente, non ancora verificata</summary>
			<p>
				La linea tratteggiata può non coincidere con il percorso della sezione: per i dettagli fa
				fede la locandina originale.
			</p>
			{#if doc.verification?.reasons.length}
				<ul>
					{#each doc.verification.reasons as r (r)}<li>{r}</li>{/each}
				</ul>
			{/if}
		</details>
	{/if}

	<MetricsHeader
		{minutes}
		minutesNote={d.duration
			? 'dichiarato dalla sezione'
			: verified
				? 'calcolato, senza soste'
				: 'non dichiarato'}
		difficulty={doc.difficulty.cai ?? doc.difficulty.raw}
		{km}
		{up}
		{down}
		source={verified
			? `${isActivity ? 'Valori della locandina' : 'Valori dichiarati'}${
					computedFields.length ? `; calcolati sulla traccia: ${computedFields.join(', ')}` : ''
				}. Tempo netto sulla traccia (modello CAI): ${formatDuration(c.cai_forward_min)}; con soste (+20%) ${formatDuration(c.cai_forward_min * 1.2)}.`
			: `Valori della locandina${computedFields.length ? `; non dichiarati: ${computedFields.join(', ')}` : ''}. Nessun valore calcolato: ${hasLine ? 'la traccia non è ancora verificata' : 'manca la traccia'}.`}
	/>

	<section class="attivita">
		<h2>
			{isActivity
				? doc.activity.future
					? 'Gita in programma'
					: 'Gita della sezione'
				: 'Gita in calendario'}
		</h2>
		<p>
			<strong>{formatDate(doc.activity.date)}</strong> · {doc.activity.organizers.join(', ')}
		</p>
		<p>
			Partenza: {doc.start.nome || '–'}{#if doc.start.quota_m}
				({formatMeters(doc.start.quota_m)}){/if}{#if doc.start.comune},
				{doc.start.comune}{/if}{#if doc.start.ora}, ritrovo ore {doc.start
					.ora}{/if}{#if doc.activity.transport}
				· {doc.activity.transport}{/if}
		</p>
		<p class="nota">{doc.activity.signup_note}</p>
		<p class="link">
			{#if doc.activity.source_url}
				<a href={doc.activity.source_url} rel="external noopener" target="_blank"
					>{!/\.pdf(?:$|[?#])/i.test(doc.activity.source_url)
						? 'Pagina originale della sezione'
						: doc.activity.source_page
							? `Locandina originale (pagina ${doc.activity.source_page})`
							: 'Locandina originale'}</a
				>
				{#if doc.activity.future}
					· <a href={doc.activity.source_url} rel="external noopener" target="_blank"
						>Iscriviti sul sito della sezione</a
					>
				{/if}
			{:else}
				<span class="nota"
					>Locandina non pubblica: questa è la fixture di prova fornita dall'utente.</span
				>
			{/if}
		</p>
	</section>

	{#if doc.proposals?.length || doc.related?.length || (doc.canonical && doc.canonical !== doc.id)}
		<section>
			<h2>Stesso itinerario e varianti</h2>
			{#if doc.canonical && doc.canonical !== doc.id}
				<p>
					Questa gita ripete un itinerario già in archivio:
					<a href={resolve('/attivita/[id]', { id: doc.canonical })}>scheda dell'itinerario</a>.
				</p>
			{/if}
			{#if doc.proposals?.length}
				<ul>
					{#each doc.proposals as p (p.id)}
						<li>
							<a href={resolve('/attivita/[id]', { id: p.id })}>Proposta da {p.section}</a>, {formatDate(
								p.date
							)}
						</li>
					{/each}
				</ul>
			{/if}
			{#if doc.related?.length}
				<p class="nota">Varianti: percorsi che ne ripercorrono buona parte.</p>
				<ul>
					{#each doc.related as r (r.id)}
						<li><a href={resolve('/attivita/[id]', { id: r.id })}>{r.title}</a></li>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}

	{#if hasLine}
		<section>
			<h2>Profilo altimetrico</h2>
			<ElevationProfile
				points={doc.profile.points}
				stages={stageMarkers.map((s) => ({ n: s.n, name: s.name, dist_km: s.dist_km }))}
				bind:index
			/>
		</section>
	{/if}

	{#if doc.stages.length}
		<section>
			<h2>Tappe</h2>
			<ol class="tappe">
				{#each doc.stages as s, i (i)}
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
	{/if}

	<section>
		<h2>Sentieri percorsi</h2>
		{#if doc.trails.some((t) => t.km_on_route >= 0.3)}
			<ul class="sentieri">
				{#each doc.trails.filter((t) => t.km_on_route >= 0.3) as t (t.relation_id)}
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
		{:else}
			<p class="nota">Nessun sentiero numerato del catasto lungo la traccia.</p>
		{/if}
		<p class="nota">
			{#if doc.networks.length}Itinerari citati: {doc.networks.join(', ')}.
			{/if}{#if doc.off_trail.length}Fuori sentiero: {doc.off_trail.join('; ')}.
			{/if}Difficoltà dichiarata: {doc.declared.difficulty ?? 'non indicata'}{#if trailScales};
				sentieri percorsi classificati {trailScales}{/if}.
		</p>
	</section>

	<section>
		<h2>Attrezzatura e periodo</h2>
		<ul>
			{#each doc.equipment as e (e)}<li>{e}</li>{/each}
			{#each doc.notes as n (n)}<li>{n}</li>{/each}
			{#if doc.map_reference}<li>Cartografia: {doc.map_reference}</li>{/if}
		</ul>
		<p class="nota">
			Periodo consigliato {season} (indicativo{#if maxEle}, dalla quota massima di {formatMeters(
					maxEle
				)}{/if}). Attrezzatura indicativa: verifica sempre la locandina e le condizioni.
		</p>
	</section>

	<section>
		<h2>Condizioni</h2>
		<p class="nota">
			Meteo alla partenza e in quota, zero termico, vento e bollettino valanghe per la data scelta
			arriveranno con la Fase 6. Prima di partire consulta le previsioni e, d'inverno, il bollettino
			<a href="https://avalanche.report" rel="external noopener" target="_blank">avalanche.report</a
			>.
		</p>
	</section>

	{#if hasLine || doc.start.lon != null}
		<section>
			<h2>Come arrivare</h2>
			<p>
				Partenza: <strong>{doc.start.nome || 'inizio della traccia'}</strong> · coordinate {coordText}
			</p>
			<p class="link">
				<a href="geo:{startLat},{startLon}?q={startLat},{startLon}">App di navigazione</a> ·
				<a
					href="https://www.google.com/maps/dir/?api=1&destination={startLat},{startLon}"
					rel="external noopener"
					target="_blank">Google Maps</a
				>
				·
				<a
					href="https://maps.apple.com/?daddr={startLat},{startLon}"
					rel="external noopener"
					target="_blank">Apple Mappe</a
				>
				·
				<a
					href="https://www.openstreetmap.org/?mlat={startLat}&mlon={startLon}#map=15/{startLat}/{startLon}"
					rel="external noopener"
					target="_blank">OpenStreetMap</a
				>
			</p>
			<p class="nota">Mezzi pubblici: in una fase successiva.</p>
		</section>
	{/if}

	{#if hasLine && checks.length}
		<section class="confronto">
			<h2>
				Traccia ricostruita: confronto con {isActivity ? 'la locandina' : 'i dati dichiarati'}
			</h2>
			<p class="esito {verified ? 'ok' : 'rivedere'}">
				{verified ? 'Entro le tolleranze (auto_ok)' : 'Da rivedere'}
			</p>
			<table>
				<thead><tr><th></th><th>Locandina</th><th>Calcolato</th><th>Scarto</th></tr></thead>
				<tbody>
					{#each checks as row (row.label)}
						<tr>
							<th>{row.label}</th><td>{row.declared}</td><td>{row.computed}</td>
							<td class={row.ok ? 'ok' : 'ko'}
								>{row.delta} <span class="nota">({row.ok ? 'entro' : 'oltre'} {row.rule})</span></td
							>
						</tr>
					{/each}
				</tbody>
			</table>
			<p class="nota">
				{doc.reconstruction} Tempo DIN 33466 sui valori calcolati: {formatDuration(
					c.din_forward_min
				)}.
			</p>
		</section>
	{/if}

	<section class="azioni" aria-label="Azioni">
		<button type="button" onclick={toggleSave} aria-pressed={saved}
			>{saved ? '★ Salvato' : '☆ Salva'}</button
		>
		{#if hasLine}
			<button type="button" onclick={exportGpx}>Esporta GPX</button>
			<button type="button" onclick={exportKml}>Esporta KML</button>
		{/if}
		<button type="button" onclick={share}>Condividi</button>
		{#if hasLine}
			<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- il percorso viene da resolve() -->
			<a class="bottone" href={plannerHref}>Modifica nel planner</a>
		{/if}
		<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso da resolve() con parametri -->
		<a class="bottone" href={outingHref}>Organizza uscita</a>
		{#if shareNote}<span class="nota" role="status">{shareNote}</span>{/if}
	</section>

	<SafetyNote />

	<footer class="attribuzione">
		{#each doc.attribution as a (a)}<span>{a}</span>{/each}
	</footer>
</article>

<style>
	.mappa {
		position: relative;
		height: 42dvh;
		min-height: 260px;
	}
	.info-sentiero {
		position: absolute;
		left: 0.6rem;
		right: 3.4rem;
		bottom: 2rem;
		max-height: calc(100% - 3rem);
		display: flex;
		z-index: 3;
	}
	@media (min-width: 900px) {
		.info-sentiero {
			right: auto;
			width: 360px;
		}
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
		margin: 0.1rem 0 0.4rem;
		font-size: 1.45rem;
		line-height: 1.25;
	}
	.sintesi {
		margin: 0 0 0.75rem;
	}
	h2 {
		font-size: 1.1rem;
		margin: 1.25rem 0 0.4rem;
	}
	.avviso {
		border: 1px solid #e0b54a;
		background: color-mix(in srgb, #e0b54a 14%, var(--surface));
		border-radius: 10px;
		padding: 0.6rem 0.8rem;
		margin: 0 0 0.75rem;
	}
	.avviso summary {
		font-weight: 700;
		cursor: pointer;
	}
	.avviso p,
	.avviso ul {
		margin: 0.4rem 0 0;
		font-size: 0.9rem;
	}
	.attivita p {
		margin: 0.2rem 0;
	}
	.nota {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.link a {
		font-weight: 600;
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
	.esito.rivedere {
		color: #9a6700;
	}
	.azioni {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin: 1.25rem 0 0.5rem;
		align-items: center;
	}
	.azioni button,
	.azioni .bottone {
		min-height: 44px;
		padding: 0 0.9rem;
		border-radius: 10px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: inherit;
		font: inherit;
		font-weight: 600;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		text-decoration: none;
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
