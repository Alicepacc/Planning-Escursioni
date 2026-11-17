<script lang="ts">
	// «Proponi un giro» (SPEC §5.7 a): vincoli → proposte in formato locandina, con anteprima sulla
	// mappa e apertura nel planner. Le proposte sono generate dai dati e non verificate sul terreno.
	import { tick } from 'svelte';
	import DifficultyBadge from '../components/DifficultyBadge.svelte';
	import { formatDuration, formatKm, formatMeters } from '../hiking/format';
	import { bboxOf, type PlannerEngine } from '../planner/engine';
	import type { Plan } from '../planner/plan';
	import { DIFF_LABELS } from '../routing/graph';
	import { sunShare } from './exposure';
	import {
		generate,
		searchRadiusKm,
		withExposure,
		type GenOptions,
		type Proposal,
		type ProposalType,
		type Wish
	} from './generator';
	import { fitLine } from '../planner/fit';
	import {
		GENERATED_LABEL,
		makePoster,
		proposalAnchors,
		proposalLine,
		type Poster
	} from './poster';

	type LonLat = { lon: number; lat: number };

	interface Props {
		engine: PlannerEngine;
		start: LonLat | null;
		end: LonLat | null;
		/** cosa imposta il prossimo tocco sulla mappa */
		picking: 'start' | 'end' | null;
		maxDiff: number;
		placeName: (p: LonLat) => string | null;
		onPreview: (
			line: [number, number][] | null,
			bbox: [number, number, number, number] | null
		) => void;
		onOpen: (plan: Plan) => void;
		onClose: () => void;
	}

	let {
		engine,
		start,
		end,
		picking = $bindable(),
		maxDiff,
		placeName,
		onPreview,
		onOpen,
		onClose
	}: Props = $props();

	const DURATIONS: [number, number, string][] = [
		[90, 150, '1:30–2:30 h'],
		[150, 240, '2:30–4 h'],
		[240, 330, '4–5:30 h'],
		[330, 420, '5:30–7 h'],
		[420, 540, '7–9 h']
	];
	const CLIMBS: [number | null, string][] = [
		[null, 'qualsiasi'],
		[500, 'fino a 500 m'],
		[800, 'fino a 800 m'],
		[1100, 'fino a 1100 m'],
		[1500, 'fino a 1500 m']
	];
	const WISHES: [Wish, string][] = [
		['cima', 'Una cima'],
		['lago', 'Un lago'],
		['rifugio', 'Un rifugio'],
		['panorama', 'Panorama']
	];
	const TYPES: [ProposalType, string][] = [
		['anello', 'Anello'],
		['andata_ritorno', 'Andata e ritorno'],
		['traversata', 'Traversata']
	];
	const MONTHS = [
		'gennaio',
		'febbraio',
		'marzo',
		'aprile',
		'maggio',
		'giugno',
		'luglio',
		'agosto',
		'settembre',
		'ottobre',
		'novembre',
		'dicembre'
	];

	let type = $state<ProposalType>('anello');
	let duration = $state(2);
	let climb = $state(0);
	let wishes = $state<Wish[]>([]);
	let month = $state(new Date().getMonth() + 1);
	let snowshoes = $state(false);
	let busy = $state(false);
	let status = $state('');
	let results = $state.raw<{ p: Proposal; poster: Poster }[]>([]);
	let shown = $state<number | null>(null);
	let panel = $state<HTMLElement>();
	const winter = $derived([12, 1, 2, 3].includes(month));

	function toggleWish(w: Wish) {
		wishes = wishes.includes(w) ? wishes.filter((x) => x !== w) : [...wishes, w];
	}

	function show(i: number | null) {
		shown = i;
		if (i == null) return onPreview(null, null);
		const line = results[i].p.points.map(([lon, lat]) => [lon, lat] as [number, number]);
		onPreview(line, bboxOf(line.map(([lon, lat]) => ({ lon, lat }))));
	}

	async function run() {
		if (!start) {
			status = 'Tocca la mappa per scegliere la partenza.';
			picking = 'start';
			return;
		}
		if (type === 'traversata' && !end) {
			status = 'Per una traversata tocca la mappa anche per l’arrivo.';
			picking = 'end';
			return;
		}
		busy = true;
		results = [];
		show(null);
		const [minMinutes, maxMinutes] = DURATIONS[duration];
		const opts: GenOptions = {
			start,
			end: type === 'traversata' ? end : null,
			type,
			minMinutes,
			maxMinutes,
			maxUp: CLIMBS[climb][0],
			maxDiff,
			wishes: [...wishes],
			month,
			snowshoes: winter && snowshoes,
			limit: 3
		};
		try {
			status = 'Carico i sentieri della zona…';
			await engine.area(bboxOf([start, ...(opts.end ? [opts.end] : [])]), searchRadiusKm(opts) + 1);
			const g = engine.graph;
			if (!g) {
				status = 'Dati dei sentieri non disponibili.';
				return;
			}
			status = 'Compongo le proposte…';
			await new Promise((r) => setTimeout(r, 30)); // lascia disegnare il messaggio
			const r = generate(g, opts);
			const ranked = r.proposals.length ? await withExposure(r.proposals, month, sunShare) : [];
			const startName = placeName(start);
			const endName = opts.end ? placeName(opts.end) : null;
			results = ranked.map((p) => ({ p, poster: makePoster(p, opts, startName, endName) }));
			status = results.length ? '' : (r.reason ?? 'Nessuna proposta con questi vincoli.');
			if (results.length) {
				show(0);
				await tick();
				panel?.querySelector('.locandina')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
			}
		} catch (err) {
			status = err instanceof Error ? err.message : 'Errore nella composizione delle proposte.';
		} finally {
			busy = false;
		}
	}

	let opening = $state(false);
	async function open(i: number) {
		const { p, poster } = results[i];
		opening = true;
		try {
			const plan = await fitLine(engine, proposalLine(p), proposalAnchors(p), {
				maxDiff,
				name: poster.title,
				ar: p.type === 'andata_ritorno'
			});
			onPreview(null, null);
			onOpen(plan);
		} finally {
			opening = false;
		}
	}
</script>

<section class="generatore" aria-labelledby="gen-titolo" bind:this={panel}>
	<div class="testa">
		<h2 id="gen-titolo">Proponi un giro</h2>
		<button type="button" class="link" onclick={onClose}>Chiudi</button>
	</div>

	<div class="riga">
		<span class="etichetta">Partenza</span>
		{#if start}
			<span>{placeName(start) ?? `${start.lat.toFixed(4)}, ${start.lon.toFixed(4)}`}</span>
		{:else}
			<span class="muto">non scelta</span>
		{/if}
		<button type="button" aria-pressed={picking === 'start'} onclick={() => (picking = 'start')}
			>{picking === 'start' ? 'Tocca la mappa…' : 'Scegli sulla mappa'}</button
		>
	</div>

	<fieldset>
		<legend>Tipo</legend>
		{#each TYPES as [value, label] (value)}
			<button type="button" aria-pressed={type === value} onclick={() => (type = value)}
				>{label}</button
			>
		{/each}
	</fieldset>

	{#if type === 'traversata'}
		<div class="riga">
			<span class="etichetta">Arrivo</span>
			{#if end}
				<span>{placeName(end) ?? `${end.lat.toFixed(4)}, ${end.lon.toFixed(4)}`}</span>
			{:else}
				<span class="muto">non scelto</span>
			{/if}
			<button type="button" aria-pressed={picking === 'end'} onclick={() => (picking = 'end')}
				>{picking === 'end' ? 'Tocca la mappa…' : 'Scegli sulla mappa'}</button
			>
		</div>
	{/if}

	<div class="campi">
		<label
			>Tempo netto
			<select bind:value={duration}>
				{#each DURATIONS as d, i (d[2])}<option value={i}>{d[2]}</option>{/each}
			</select>
		</label>
		<label
			>Dislivello
			<select bind:value={climb}>
				{#each CLIMBS as c, i (c[1])}<option value={i}>{c[1]}</option>{/each}
			</select>
		</label>
		<label
			>Mese
			<select bind:value={month}>
				{#each MONTHS as m, i (m)}<option value={i + 1}>{m}</option>{/each}
			</select>
		</label>
	</div>

	<fieldset>
		<legend>Desideri</legend>
		{#each WISHES as [w, label] (w)}
			<button type="button" aria-pressed={wishes.includes(w)} onclick={() => toggleWish(w)}
				>{label}</button
			>
		{/each}
		{#if winter}
			<button type="button" aria-pressed={snowshoes} onclick={() => (snowshoes = !snowshoes)}
				>Con le ciaspole</button
			>
		{/if}
	</fieldset>
	<p class="piccolo">
		Difficoltà fino a <strong>{DIFF_LABELS[maxDiff]}</strong> (si cambia in alto, «difficoltà ammessa»).
	</p>

	<button type="button" class="primario" onclick={run} disabled={busy}
		>{busy ? 'Sto componendo…' : 'Proponi'}</button
	>
	{#if status}<p class="stato" role="status">{status}</p>{/if}

	{#each results as { p, poster }, i (i)}
		<article class="locandina" class:attiva={shown === i}>
			<p class="etichetta-gen">{GENERATED_LABEL}</p>
			<h3>{poster.title}</h3>
			<p class="metriche">
				<strong>{formatDuration(p.stats.minutes)}</strong> · {formatKm(p.stats.km)} · ↗ {formatMeters(
					p.stats.up
				)} · max {formatMeters(p.stats.maxEle)} ·
				<DifficultyBadge code={p.stats.maxDiff} />
			</p>
			{#each poster.description as line (line)}<p>{line}</p>{/each}
			<details>
				<summary>Tappe, attrezzatura e perché te la propongo</summary>
				<ol class="tappe">
					{#each poster.stages as s, k (k)}
						<li>
							<span class="t">{formatDuration(s.minutes)}</span>
							<span>{s.name}{s.ele != null ? ` · ${formatMeters(s.ele)}` : ''}</span>
							<span class="muto">km {s.km.toFixed(1).replace('.', ',')}</span>
						</li>
					{/each}
				</ol>
				<p><strong>Attrezzatura consigliata:</strong> {poster.equipment.join(', ')}.</p>
				<p><strong>Perché:</strong> {poster.why.join(' · ')}.</p>
			</details>
			<div class="azioni">
				<button
					type="button"
					aria-pressed={shown === i}
					onclick={() => show(shown === i ? null : i)}
					>{shown === i ? 'Sulla mappa' : 'Vedi sulla mappa'}</button
				>
				<button type="button" class="primario" onclick={() => open(i)} disabled={opening}
					>{opening ? 'Apro…' : 'Apri nel planner'}</button
				>
			</div>
		</article>
	{/each}
	{#if results.length}
		<p class="piccolo">
			Proposte composte dal grafo dei sentieri con una funzione di qualità esplicita (sentieri
			segnati, varietà, luoghi, segnalazioni, stagione): verifica sempre percorso e condizioni prima
			di partire.
		</p>
	{/if}
</section>

<style>
	.generatore {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.testa {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	h2 {
		margin: 0;
		font-size: 1.1rem;
	}
	h3 {
		margin: 0.1rem 0 0.2rem;
		font-size: 1.05rem;
	}
	.riga {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.4rem 0.6rem;
	}
	.etichetta {
		color: var(--muted);
		font-size: 0.9rem;
		min-width: 4.5rem;
	}
	.muto {
		color: var(--muted);
	}
	fieldset {
		border: 0;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	legend {
		color: var(--muted);
		font-size: 0.9rem;
		margin-bottom: 0.3rem;
		padding: 0;
	}
	.campi {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 0.8rem;
	}
	.campi label {
		display: flex;
		flex-direction: column;
		font-size: 0.85rem;
		color: var(--muted);
	}
	select {
		font: inherit;
		min-height: 44px;
		color: var(--text);
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
	}
	button {
		min-height: 44px;
		padding: 0 0.8rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
		font: inherit;
		font-size: 0.92rem;
		cursor: pointer;
	}
	button:disabled {
		opacity: 0.55;
		cursor: default;
	}
	button[aria-pressed='true'] {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--surface);
	}
	button.primario {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--surface);
		font-weight: 600;
	}
	button.link {
		border: 0;
		background: none;
		color: var(--accent);
		text-decoration: underline;
	}
	.piccolo {
		margin: 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.stato {
		margin: 0;
		padding: 0.45rem 0.7rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 10px;
	}
	.locandina {
		background: var(--surface);
		border: 1px solid var(--border);
		border-left: 5px solid #7b2cbf;
		border-radius: 12px;
		padding: 0.6rem 0.8rem;
	}
	.locandina.attiva {
		box-shadow: 0 0 0 2px #7b2cbf;
	}
	.locandina p {
		margin: 0.25rem 0;
		font-size: 0.93rem;
	}
	.etichetta-gen {
		display: inline-block;
		font-size: 0.75rem !important;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.02em;
		color: #7b2cbf;
	}
	.metriche {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem;
	}
	details summary {
		cursor: pointer;
		min-height: 44px;
		display: flex;
		align-items: center;
		color: var(--accent);
	}
	.tappe {
		margin: 0.2rem 0;
		padding-left: 1.2rem;
		font-size: 0.9rem;
	}
	.tappe li {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.tappe .t {
		min-width: 3.4rem;
		font-variant-numeric: tabular-nums;
	}
	.azioni {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-top: 0.3rem;
	}
</style>
