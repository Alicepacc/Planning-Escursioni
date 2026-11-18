<script lang="ts">
	// Pianifica (SPEC §5.3): il percorso si aggancia ai sentieri con il router nel browser
	// (ADR 0010). Lo stato del piano è tutto nell'URL: ogni modifica è una voce della cronologia,
	// quindi Indietro annulla e il link si può condividere; l'ultimo piano resta nel browser.
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import ElevationProfile from '#lib/components/ElevationProfile.svelte';
	import DifficultyBadge from '#lib/components/DifficultyBadge.svelte';
	import SafetyNote from '#lib/components/SafetyNote.svelte';
	import { generatedAsset } from '#lib/data/paths.ts';
	import { download, fileName, toGpx } from '#lib/export/gpx.ts';
	import { formatDuration, formatKm, formatMeters } from '#lib/hiking/format.ts';
	import { elevations } from '#lib/map/dem.ts';
	import GeneratorPanel from '#lib/generator/GeneratorPanel.svelte';
	import PlannerMap from '#lib/planner/PlannerMap.svelte';
	import { PlannerEngine, bboxOf, type PlannedLeg } from '#lib/planner/engine.ts';
	import {
		keepTrackWhereRoutingDeviates,
		parseGpx,
		planFromTrack,
		type ImportedTrack
	} from '#lib/planner/gpx-import.ts';
	import {
		addPoint,
		closeLoop,
		emptyPlan,
		insertPoint,
		isLoop,
		movePoint,
		openLoop,
		planFromParams,
		planToParams,
		removePoint,
		reversePlan,
		setAr,
		setMaxDiff,
		setMode,
		setName,
		straightLength,
		type Plan,
		type PlanPoint
	} from '#lib/planner/plan.ts';
	import {
		DEFAULT_PACE,
		isSaved,
		loadLast,
		loadPace,
		planKey,
		saveLast,
		savePace,
		savedList,
		toggleSaved,
		type Pace,
		type SavedEntry
	} from '#lib/planner/storage.ts';
	import { DIFF_LABELS, type Poi } from '#lib/routing/graph.ts';
	import {
		lengthText,
		profileStats,
		reverseLeg,
		routeProfile,
		routeWarnings
	} from '#lib/routing/stats.ts';

	const BASE = resolve('/pianifica');
	const DIFF_NAMES = [
		'T – turistico',
		'E – escursionistico',
		'EE – per esperti',
		'EEA – attrezzato'
	];
	const POI_NAMES: Record<string, string> = {
		c: 'cima',
		l: 'lago',
		r: 'rifugio',
		b: 'bivacco',
		v: 'punto panoramico',
		k: 'parcheggio'
	};

	const engine = new PlannerEngine({
		fetchJson: async (name) => {
			const r = await fetch(generatedAsset(`data/grafo/${name}`));
			if (!r.ok) throw new Error(`grafo: HTTP ${r.status}`);
			return r.json();
		},
		elevations
	});

	// --- stato: il piano viene dall'URL (dopo il montaggio: la pagina è prerenderizzata) ---
	let mounted = $state(false);
	const url = $derived(mounted ? (page.shallow?.url ?? page.url) : null);
	const plan = $derived<Plan>(url ? planFromParams(url.searchParams) : emptyPlan());
	const query = $derived(planToParams(plan).toString());
	const depth = $derived(mounted ? (page.state.depth ?? 0) : 0);
	let maxDepth = $state(0);
	$effect(() => {
		if (depth > maxDepth) maxDepth = depth;
	});

	let legs = $state.raw<PlannedLeg[]>([]);
	let computing = $state(false);
	let token = 0;
	$effect(() => {
		const p = plan;
		const t = ++token;
		if (!p.modes.length) {
			legs = [];
			computing = false;
			return;
		}
		computing = true;
		engine.legs(p).then((ls) => {
			if (t !== token) return;
			legs = ls;
			computing = false;
		});
	});

	let selected = $state<number | null>(null);
	let freeMode = $state(false);
	let profileIndex = $state<number | null>(null);
	let focus = $state<[number, number, number, number] | null>(null);
	let pace = $state<Pace>({ ...DEFAULT_PACE });
	let paceOpen = $state(false);
	let note = $state('');
	let noteTimer: ReturnType<typeof setTimeout> | undefined;
	let saved = $state(false);
	let savedPlans = $state<SavedEntry[]>([]);
	let importing = $state<{ track: ImportedTrack; km: number } | null>(null);
	let fileInput = $state<HTMLInputElement>();
	let mapRef = $state<{ center: () => { lon: number; lat: number; mpp: number } | null }>();
	let restored = $state(false);

	// generatore: compone giri su richiesta (strumento del planner, ADR 0012)
	let genOpen = $state(false);
	let genStart = $state<PlanPoint | null>(null);
	let genEnd = $state<PlanPoint | null>(null);
	let genPicking = $state<'start' | 'end' | null>(null);
	let preview = $state<[number, number][] | null>(null);
	const genMarks = $derived(
		genOpen
			? [
					...(genStart
						? [{ ...genStart, label: 'P', title: 'Partenza del giro da comporre' }]
						: []),
					...(genEnd ? [{ ...genEnd, label: 'A', title: 'Arrivo del giro da comporre' }] : [])
				]
			: []
	);

	// --- valori derivati ---
	const legsReady = $derived(legs.length === plan.modes.length);
	const fullLegs = $derived(plan.ar ? [...legs, ...[...legs].reverse().map(reverseLeg)] : legs);
	const profile = $derived(routeProfile(fullLegs));
	const stats = $derived(profileStats(fullLegs, profile));
	const warnings = $derived(routeWarnings(fullLegs, plan.maxDiff));
	const minutes = $derived(stats.minutes * pace.fitness * pace.stops * pace.group);
	const paceChanged = $derived(pace.fitness !== 1 || pace.stops !== 1 || pace.group !== 1);
	const loop = $derived(isLoop(plan));
	const empty = $derived(plan.points.length < 2);
	const noEle = $derived(legs.some((l) => l.noEle));
	const fallbacks = $derived(
		legs.flatMap((l, i) => (l.fallback ? [{ leg: i, why: l.fallback }] : []))
	);
	const along = $derived(legsReady ? engine.poisAlong(legs.flatMap((l) => l.points)) : []);
	const huts = $derived(along.filter((a) => a.poi.kind === 'r' || a.poi.kind === 'b'));
	const highlights = $derived(along.filter((a) => a.poi.kind !== 'k').slice(0, 12));
	const cursor = $derived<[number, number] | null>(
		profileIndex != null && profile[profileIndex]
			? [profile[profileIndex][2], profile[profileIndex][3]]
			: null
	);

	/** «Rifugio X» senza ripetere il tipo quando il nome lo contiene già. */
	function hutName(poi: Poi): string {
		const kind = poi.kind === 'r' ? 'Rifugio' : 'Bivacco';
		return /rifugio|bivacco|hütte|hutte|malga|baita/i.test(poi.name)
			? poi.name
			: `${kind} ${poi.name}`;
	}

	function nearestPoi(p: PlanPoint, maxM: number): Poi | null {
		const g = engine.graph;
		if (!g) return null;
		let best: Poi | null = null;
		let bestD = maxM;
		const kx = 111320 * Math.cos((p.lat * Math.PI) / 180);
		for (const poi of g.pois) {
			const d = Math.hypot((poi.lon - p.lon) * kx, (poi.lat - p.lat) * 110950);
			if (d < bestD && poi.name) {
				bestD = d;
				best = poi;
			}
		}
		return best;
	}

	/** Nome automatico dai luoghi (solo se l'utente non ne ha dato uno). */
	const autoName = $derived.by(() => {
		if (!plan.points.length || !legsReady) return 'Nuovo percorso';
		const first = nearestPoi(plan.points[0], 700)?.name;
		const last = nearestPoi(plan.points[plan.points.length - 1], 700)?.name;
		const peaks = along
			.filter((a) => a.poi.kind === 'c')
			.sort((x, y) => (y.poi.ele ?? 0) - (x.poi.ele ?? 0));
		const top = peaks[0]?.poi.name;
		if (loop)
			return first
				? `Anello da ${first}${top && top !== first ? ` per ${top}` : ''}`
				: top
					? `Anello per ${top}`
					: 'Anello';
		if (plan.ar && last)
			return `${last}, andata e ritorno${first && first !== last ? ` da ${first}` : ''}`;
		if (first && last && first !== last) return `Da ${first} a ${last}`;
		return top ? `Verso ${top}` : 'Nuovo percorso';
	});
	const title = $derived(plan.name || autoName);

	// --- modifiche: una alla volta, ognuna è una voce della cronologia ---
	let queue: Promise<unknown> = Promise.resolve();
	function enqueue(job: () => Promise<unknown>) {
		queue = queue.then(job).catch((err) => console.error(err));
	}

	function href(q: string): string {
		return q ? `${BASE}?${q}` : BASE;
	}

	async function commit(next: Plan) {
		const q = planToParams(next).toString();
		if (q === query) return;
		const d = depth + 1;
		maxDepth = d;
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- BASE viene da resolve()
		await goto(href(q), { shallow: true, state: { depth: d }, persistState: true });
	}

	function say(text: string) {
		note = text;
		clearTimeout(noteTimer);
		noteTimer = setTimeout(() => (note = ''), 6000);
	}

	function snapRadius(mpp: number): number {
		return Math.min(400, Math.max(60, mpp * 30));
	}

	function addAt(lon: number, lat: number, mpp: number) {
		selected = null;
		if (genOpen) {
			// con il generatore aperto il tocco sceglie partenza (o arrivo), non modifica il piano
			const which = genPicking ?? 'start';
			genPicking = null;
			void engine.snapPoint({ lon, lat }, plan.maxDiff, snapRadius(mpp)).then((s) => {
				const p = s ? { lon: s.lon, lat: s.lat } : { lon, lat };
				if (which === 'start') genStart = p;
				else genEnd = p;
				if (!s) say('Nessun sentiero ammesso vicino a quel punto: sceglilo su un sentiero.');
			});
			return;
		}
		enqueue(async () => {
			if (freeMode) return commit(addPoint(plan, { lon, lat }, 'f'));
			const radius = snapRadius(mpp);
			const s = await engine.snapPoint({ lon, lat }, plan.maxDiff, radius);
			if (s) return commit(addPoint(plan, s, 'r'));
			if (!plan.points.length) {
				// la partenza può stare fuori dai sentieri: il tratto successivo li raggiunge
				say('Partenza lontana dai sentieri: il primo tratto sarà a mano libera.');
				return commit(addPoint(plan, { lon, lat }, 'f'));
			}
			const covered = await engine.covers({ lon, lat });
			say(
				covered
					? `Nessun sentiero fino a ${DIFF_LABELS[plan.maxDiff]} entro ${Math.round(radius)} m: tratto a mano libera.`
					: 'Fuori dall’area coperta dai dati dei sentieri: tratto a mano libera.'
			);
			return commit(addPoint(plan, { lon, lat }, 'f'));
		});
	}

	function openGenerator() {
		selected = null;
		genOpen = true;
		genStart = genStart ?? plan.points[0] ?? null;
		genPicking = genStart ? null : 'start';
	}

	function closeGenerator() {
		genOpen = false;
		genPicking = null;
		preview = null;
	}

	function openProposal(next: Plan) {
		closeGenerator();
		focus = bboxOf(next.points);
		act(() => next);
	}

	function addAtCenter() {
		const c = mapRef?.center();
		if (c) addAt(c.lon, c.lat, c.mpp);
	}

	function insertAt(leg: number, lon: number, lat: number) {
		selected = null;
		enqueue(async () => {
			let p: PlanPoint = { lon, lat };
			if (plan.modes[leg] === 'r') {
				const s = await engine.snapPoint(p, plan.maxDiff, 60);
				if (s) p = s;
			}
			return commit(insertPoint(plan, leg, p));
		});
	}

	function moveTo(i: number, lon: number, lat: number, mpp: number) {
		enqueue(async () => {
			const n = plan.points.length;
			const touching = [
				plan.modes[i - 1],
				plan.modes[i],
				loop && i === 0 ? plan.modes[n - 2] : undefined
			];
			let p: PlanPoint = { lon, lat };
			if (touching.includes('r')) {
				const s = await engine.snapPoint(p, plan.maxDiff, snapRadius(mpp));
				if (s) p = s;
				else say('Punto lontano dai sentieri: i tratti vicini diventano a mano libera.');
			}
			return commit(movePoint(plan, i, p));
		});
	}

	function remove(i: number) {
		selected = null;
		enqueue(() => commit(removePoint(plan, i)));
	}

	function act(make: (p: Plan) => Plan) {
		selected = null;
		enqueue(() => commit(make(plan)));
	}

	function undo() {
		if (depth > 0) history.back();
	}
	function redo() {
		if (depth < maxDepth) history.forward();
	}

	function onKey(e: KeyboardEvent) {
		const target = e.target as HTMLElement;
		if (target.closest('input, select, textarea')) return;
		if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
			e.preventDefault();
			if (e.shiftKey) redo();
			else undo();
		}
	}

	// --- import ed export ---
	async function onFile() {
		const file = fileInput?.files?.[0];
		if (!file) return;
		try {
			const track = parseGpx(await file.text());
			importing = { track, km: straightLength(track.points) / 1000 };
		} catch (err) {
			say(err instanceof Error ? err.message : 'File non leggibile.');
		} finally {
			if (fileInput) fileInput.value = '';
		}
	}

	function importTrack(snapIt: boolean) {
		const imp = importing;
		if (!imp) return;
		importing = null;
		selected = null;
		enqueue(async () => {
			const tp = planFromTrack(imp.track, { snap: snapIt, maxDiff: plan.maxDiff });
			let next = tp.plan;
			if (snapIt) {
				say('Aggancio della traccia ai sentieri…');
				const ls = await engine.legs(next);
				const r = keepTrackWhereRoutingDeviates(tp, ls);
				next = r.plan;
				say(
					r.replaced
						? `Traccia agganciata ai sentieri; ${r.replaced === 1 ? '1 tratto' : `${r.replaced} tratti`} su ${ls.length} ${r.replaced === 1 ? 'segue' : 'seguono'} la traccia originale (lì i sentieri se ne allontanavano).`
						: 'Traccia agganciata ai sentieri.'
				);
			} else say('Traccia importata a mano libera: le quote vengono dal modello del terreno.');
			focus = bboxOf(next.points);
			return commit(next);
		});
	}

	function trackPoints() {
		return fullLegs.flatMap((l, i) => (i ? l.points.slice(1) : l.points));
	}

	function exportGpx() {
		const wpts = plan.points
			.slice(0, loop ? -1 : undefined)
			.map((p, i) => ({ name: `${i + 1}`, lon: p.lon, lat: p.lat }));
		download(
			toGpx(
				title,
				trackPoints(),
				wpts,
				'Pianificato con Cordata · sentieri © OpenStreetMap (ODbL) e © CAI · quote Mapterhorn'
			),
			fileName(title, 'gpx'),
			'application/gpx+xml'
		);
	}

	async function share() {
		const link = location.href;
		try {
			if (navigator.share) {
				await navigator.share({ title, text: `${title} · Cordata`, url: link });
				return;
			}
			await navigator.clipboard.writeText(link);
			say('Link copiato: chi lo apre vede questo percorso.');
		} catch {
			/* condivisione annullata */
		}
	}

	function toggleSave() {
		const key = planKey(query);
		const state = toggleSaved({ key, title, href: `${location.pathname}${location.search}` });
		if (state == null) say('Impossibile salvare in questo browser.');
		else {
			saved = state;
			say(state ? 'Percorso salvato in questo browser.' : 'Tolto dai salvati.');
			savedPlans = savedList().filter((e) => e.key.startsWith('piano:'));
		}
	}

	function setPace(p: Partial<Pace>) {
		pace = { ...pace, ...p };
		savePace(pace);
	}

	// --- ciclo di vita ---
	onMount(() => {
		pace = loadPace();
		savedPlans = savedList().filter((e) => e.key.startsWith('piano:'));
		const initial = new URLSearchParams(location.search);
		if (!initial.has('p')) {
			const last = loadLast();
			if (last && new URLSearchParams(last).has('p')) {
				restored = true;
				// eslint-disable-next-line svelte/no-navigation-without-resolve -- BASE viene da resolve()
				void goto(href(last), { shallow: true, replace: true, state: { depth: 0 } });
				const p = planFromParams(new URLSearchParams(last));
				if (p.points.length) focus = bboxOf(p.points);
			}
		} else {
			const p = planFromParams(initial);
			if (p.points.length) focus = bboxOf(p.points);
		}
		mounted = true;
	});

	$effect(() => {
		if (!mounted) return;
		saveLast(query);
		saved = !!query && isSaved(planKey(query));
	});

	// il punto selezionato può sparire (annulla, elimina)
	$effect(() => {
		if (selected != null && selected >= plan.points.length) selected = null;
	});
</script>

<svelte:head>
	<title>{plan.points.length ? `${title} – Pianifica` : 'Pianifica'} – Cordata</title>
	<meta
		name="description"
		content="Pianifica un'escursione sui sentieri del Trentino-Alto Adige: percorso agganciato ai sentieri, dislivello, tempi e avvisi."
	/>
</svelte:head>

<svelte:window onkeydown={onKey} />

<div
	class="planner"
	data-points={plan.points.length}
	data-legs={legs.length}
	data-busy={computing ? 'true' : 'false'}
>
	<section class="stats" aria-label="Statistiche del percorso" aria-live="polite">
		<div class="stat">
			<b>{empty ? '–' : formatKm(stats.km)}</b><span>distanza</span>
		</div>
		<div class="stat">
			<b
				>↗ {noEle || empty ? '–' : formatMeters(stats.up)} ↘ {noEle || empty
					? '–'
					: formatMeters(stats.down)}</b
			><span>dislivello</span>
		</div>
		<button
			type="button"
			class="stat tempo"
			aria-expanded={paceOpen}
			aria-controls="passo"
			onclick={() => (paceOpen = !paceOpen)}
		>
			<b>{empty ? '–' : formatDuration(minutes)}</b><span
				>{paceChanged ? 'col tuo passo ▾' : 'tempo netto ▾'}</span
			>
		</button>
		<div class="stat">
			<b>{noEle ? '–' : formatMeters(stats.maxEle)}</b><span>quota max</span>
		</div>
		<div class="stat">
			<b
				>{#if stats.maxDiff}<DifficultyBadge code={stats.maxDiff} />{:else}–{/if}</b
			><span>max incontrata</span>
		</div>
		<label class="stat ammessa">
			<select
				value={plan.maxDiff}
				onchange={(e) => {
					const d = Number(e.currentTarget.value);
					act((p) => setMaxDiff(p, d));
				}}
				aria-describedby="ammessa-nota"
			>
				{#each DIFF_NAMES as name, d (name)}
					<option value={d}>Max: {DIFF_LABELS[d]}</option>
				{/each}
			</select>
			<span id="ammessa-nota">difficoltà ammessa</span>
		</label>
		{#if paceOpen}
			<div class="passo" id="passo">
				<p>
					Tempo netto senza soste (modello CAI): <strong>{formatDuration(stats.minutes)}</strong>.
					Adattalo a te:
				</p>
				<label
					>Allenamento
					<select
						value={pace.fitness}
						onchange={(e) => setPace({ fitness: Number(e.currentTarget.value) })}
					>
						<option value={0.8}>molto allenato (−20%)</option>
						<option value={0.9}>allenato (−10%)</option>
						<option value={1}>nella media</option>
						<option value={1.2}>poco allenato (+20%)</option>
						<option value={1.4}>fuori allenamento (+40%)</option>
					</select>
				</label>
				<label
					>Soste
					<select
						value={pace.stops}
						onchange={(e) => setPace({ stops: Number(e.currentTarget.value) })}
					>
						<option value={1}>non contate</option>
						<option value={1.15}>brevi (+15%)</option>
						<option value={1.2}>con pranzo (+20%)</option>
					</select>
				</label>
				<label
					>Gruppo
					<select
						value={pace.group}
						onchange={(e) => setPace({ group: Number(e.currentTarget.value) })}
					>
						<option value={1}>adulti</option>
						<option value={1.25}>numeroso (+25%)</option>
						<option value={1.5}>con bambini (+50%)</option>
					</select>
				</label>
			</div>
		{/if}
	</section>

	<div class="mappa">
		<PlannerMap
			bind:this={mapRef}
			{plan}
			{legs}
			{selected}
			{cursor}
			{focus}
			onAdd={addAt}
			onInsert={insertAt}
			onMove={moveTo}
			onSelect={(i) => (selected = i)}
			onRemove={remove}
			{preview}
			marks={genMarks}
		/>
		{#if genOpen && (genPicking || !genStart)}
			<p class="suggerimento">
				Tocca la mappa per {genPicking === 'end' ? 'l’arrivo' : 'la partenza'} del giro da comporre.
			</p>
		{:else if genOpen}
			<!-- nessun suggerimento: la mappa mostra l'anteprima -->
		{:else if !plan.points.length}
			<p class="suggerimento">
				Avvicina la mappa e <strong>tocca un sentiero</strong> per la partenza, poi i punti successivi:
				il percorso segue i sentieri.
			</p>
		{:else if freeMode}
			<p class="suggerimento libero">✋ A mano libera: i prossimi tratti saranno linee dirette.</p>
		{/if}
		{#if computing}<p class="calcolo" role="status">Calcolo del percorso…</p>{/if}
	</div>

	<section class="foglio" aria-label="Strumenti del planner">
		{#if note}<p class="nota" role="status">{note}</p>{/if}
		{#if restored && plan.points.length}
			<p class="ripreso">
				Ripreso l'ultimo piano.
				<button type="button" class="link" onclick={() => act(() => emptyPlan(plan.maxDiff))}
					>Nuovo percorso</button
				>
			</p>
		{/if}

		{#if genOpen}
			<GeneratorPanel
				{engine}
				start={genStart}
				end={genEnd}
				bind:picking={genPicking}
				maxDiff={plan.maxDiff}
				placeName={(p) => nearestPoi(p, 700)?.name ?? null}
				onPreview={(line, box) => {
					preview = line;
					if (box) focus = box;
				}}
				onOpen={openProposal}
				onClose={closeGenerator}
			/>
		{:else}
			<div class="strumenti" role="toolbar" aria-label="Modifica del percorso">
				<button type="button" onclick={undo} disabled={depth === 0} title="Annulla (Ctrl+Z)"
					>↶ <span>Annulla</span></button
				>
				<button
					type="button"
					onclick={redo}
					disabled={depth >= maxDepth}
					title="Ripeti (Ctrl+Maiusc+Z)">↷ <span>Ripeti</span></button
				>
				<button
					type="button"
					onclick={() => act((p) => (loop ? openLoop(p) : closeLoop(p, freeMode ? 'f' : 'r')))}
					disabled={plan.points.length < 2}
					aria-pressed={loop}>⟲ {loop ? 'Riapri anello' : 'Chiudi ad anello'}</button
				>
				<button type="button" onclick={() => act(reversePlan)} disabled={plan.points.length < 2}
					>⇄ Inverti</button
				>
				<button
					type="button"
					onclick={() => act((p) => setAr(p, !p.ar))}
					disabled={plan.points.length < 2 || loop}
					aria-pressed={plan.ar}>⇆ Andata e ritorno</button
				>
				<button type="button" onclick={() => (freeMode = !freeMode)} aria-pressed={freeMode}
					>✋ A mano libera</button
				>
				<button type="button" onclick={addAtCenter} title="Aggiunge un punto al centro della mappa"
					>＋ Punto al centro</button
				>
				<button type="button" class="proponi" onclick={openGenerator}>✨ Componi un giro</button>
			</div>
			{#if !plan.points.length}
				<p class="invito">
					Non sai dove andare? Guarda le <a href={resolve('/')}>escursioni delle sezioni CAI</a>,
					oppure
					<button type="button" class="link" onclick={openGenerator}
						>componi un giro automaticamente</button
					>.
				</p>
			{/if}

			{#if selected != null && plan.points[selected]}
				{@const i = selected}
				<div class="punto" aria-label="Punto selezionato">
					<p>
						<strong>Punto {i + 1}</strong>
						{#if nearestPoi(plan.points[i], 300)}· vicino a {nearestPoi(plan.points[i], 300)
								?.name}{/if}
					</p>
					<div class="azioni">
						{#if i > 0}
							<button
								type="button"
								aria-pressed={plan.modes[i - 1] === 'f'}
								onclick={() => act((p) => setMode(p, i - 1, p.modes[i - 1] === 'f' ? 'r' : 'f'))}
								>{plan.modes[i - 1] === 'f'
									? 'Tratto precedente sui sentieri'
									: 'Tratto precedente a mano libera'}</button
							>
						{/if}
						<button type="button" class="elimina" onclick={() => remove(i)}>Elimina punto</button>
						<button type="button" class="link" onclick={() => (selected = null)}>Chiudi</button>
					</div>
				</div>
			{/if}

			{#if importing}
				<div class="import" role="dialog" aria-label="Importa traccia GPX">
					<p>
						<strong>{importing.track.name || 'Traccia importata'}</strong>: {importing.track.points
							.length}
						punti, circa {formatKm(importing.km)}.
					</p>
					<div class="azioni">
						<button type="button" class="primario" onclick={() => importTrack(true)}
							>Aggancia ai sentieri</button
						>
						<button type="button" onclick={() => importTrack(false)}>Mantieni la traccia</button>
						<button type="button" class="link" onclick={() => (importing = null)}>Annulla</button>
					</div>
					<p class="piccolo">
						Agganciando, dove i sentieri si allontanano dalla traccia resta la traccia originale. La
						traccia resta nel tuo browser.
					</p>
				</div>
			{/if}

			{#if plan.points.length}
				<label class="nome">
					<span>Nome</span>
					<input
						type="text"
						value={plan.name}
						placeholder={autoName}
						maxlength="120"
						onchange={(e) => {
							const name = e.currentTarget.value.trim();
							act((p) => setName(p, name));
						}}
					/>
				</label>

				{#if warnings.length || fallbacks.length || noEle || huts.length}
					<ul class="avvisi" aria-label="Avvisi">
						{#each fallbacks as f (f.leg)}
							<li class="forte">
								Tratto {f.leg + 1}–{f.leg + 2}: {f.why === 'nessun_percorso'
									? `nessun percorso sui sentieri fino a ${DIFF_LABELS[plan.maxDiff]}, disegnato a mano libera.`
									: f.why === 'lontano'
										? `un punto è lontano dai sentieri ammessi (${DIFF_LABELS[plan.maxDiff]}), disegnato a mano libera.`
										: 'dati dei sentieri non disponibili, disegnato a mano libera.'}
								{#if f.why !== 'grafo' && plan.maxDiff < 3}
									<button
										type="button"
										class="link"
										onclick={() => act((p) => setMaxDiff(p, p.maxDiff + 1))}
										>Ammetti {DIFF_LABELS[plan.maxDiff + 1]}</button
									>
								{/if}
							</li>
						{/each}
						{#each warnings as w (w.kind)}
							<li class={w.kind === 'segnalazione' || w.kind === 'oltre_difficolta' ? 'forte' : ''}>
								{w.text}.
							</li>
						{/each}
						{#if noEle}
							<li>
								Quote non disponibili per alcuni tratti: dislivello e quota massima non calcolati.
							</li>
						{/if}
						{#each huts as h (h.poi.name + h.at)}
							<li>
								{hutName(h.poi)} (km {(h.at / 1000).toFixed(1).replace('.', ',')}): apertura da
								verificare sul sito del rifugio o della sezione.
							</li>
						{/each}
					</ul>
				{/if}
				<p class="piccolo">
					Zero termico previsto e apertura dei rifugi lungo il percorso arriveranno con i dati
					meteo.
				</p>

				{#if profile.length > 1}
					<ElevationProfile points={profile} bind:index={profileIndex} height={150} />
				{/if}

				{#if highlights.length}
					<div class="luoghi">
						<h2>Lungo il percorso</h2>
						<ul>
							{#each highlights as h (h.poi.kind + h.poi.name + h.at)}
								<li>
									<span class="km">{lengthText(h.at / 1000)}</span>
									{h.poi.name}
									<span class="tipo"
										>{POI_NAMES[h.poi.kind]}{h.poi.ele != null
											? ` · ${formatMeters(h.poi.ele)}`
											: ''}</span
									>
								</li>
							{/each}
						</ul>
					</div>
				{/if}
			{/if}

			<div class="file">
				<button type="button" onclick={() => fileInput?.click()}>⬆ Importa GPX</button>
				<input
					bind:this={fileInput}
					type="file"
					accept=".gpx,application/gpx+xml"
					hidden
					onchange={onFile}
				/>
				{#if plan.points.length > 1}
					<button type="button" onclick={exportGpx} disabled={!legsReady}>⬇ GPX</button>
					<button type="button" onclick={share}>Condividi</button>
					<button type="button" onclick={toggleSave} aria-pressed={saved}
						>{saved ? '★ Salvato' : '☆ Salva'}</button
					>
				{/if}
				{#if plan.points.length}
					<button type="button" class="link" onclick={() => act(() => emptyPlan(plan.maxDiff))}
						>Nuovo percorso</button
					>
				{/if}
			</div>

			{#if !plan.points.length && savedPlans.length}
				<div class="salvati">
					<h2>Percorsi salvati in questo browser</h2>
					<ul>
						{#each savedPlans as s (s.key)}
							<!-- eslint-disable svelte/no-navigation-without-resolve -- href salvato da location -->
							<li><a href={s.href}>{s.title}</a></li>
							<!-- eslint-enable svelte/no-navigation-without-resolve -->
						{/each}
					</ul>
				</div>
			{/if}

			<p class="piccolo">
				Percorso calcolato nel browser sul grafo dei sentieri (© OpenStreetMap, ODbL; scala CAI dal
				catasto OSM2CAI); tratti a mano libera tratteggiati. Indietro annulla l'ultima modifica.
			</p>
		{/if}
		<SafetyNote />
	</section>
</div>

<style>
	.planner {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		grid-template-rows: auto minmax(260px, 1fr) auto;
		height: calc(100dvh - 122px);
		min-height: 0;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 1px;
		background: var(--border);
		border-bottom: 1px solid var(--border);
		position: relative;
		z-index: 2;
	}
	.stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.05rem;
		min-height: 40px;
		padding: 0.15rem 0.25rem;
		line-height: 1.2;
		background: var(--surface);
		color: var(--text);
		font: inherit;
		border: 0;
		text-align: center;
		min-width: 0;
	}
	.stat b {
		font-size: 0.95rem;
		white-space: nowrap;
	}
	.stat span {
		font-size: 0.7rem;
		color: var(--muted);
		white-space: nowrap;
	}
	button.stat {
		cursor: pointer;
		border-radius: 0;
		min-height: 40px;
		padding: 0.15rem 0.25rem;
	}
	.ammessa select {
		font: inherit;
		font-weight: 700;
		font-size: 0.92rem;
		min-height: 30px;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg);
		color: var(--text);
		max-width: 100%;
	}
	.passo {
		grid-column: 1 / -1;
		background: var(--surface);
		padding: 0.5rem 1rem 0.75rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
		align-items: end;
	}
	.passo p {
		margin: 0;
		flex-basis: 100%;
		font-size: 0.92rem;
	}
	.passo label {
		display: flex;
		flex-direction: column;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.passo select {
		font: inherit;
		min-height: 40px;
		color: var(--text);
		background: var(--bg);
		border: 1px solid var(--border);
		border-radius: 8px;
	}
	.mappa {
		position: relative;
		min-height: 0;
	}
	.suggerimento,
	.calcolo {
		position: absolute;
		left: 0.75rem;
		right: 3.5rem;
		top: 3.4rem; /* sotto il pulsante della legenda */
		margin: 0;
		padding: 0.5rem 0.75rem;
		background: color-mix(in srgb, var(--surface) 94%, transparent);
		border: 1px solid var(--border);
		border-radius: 10px;
		font-size: 0.92rem;
		pointer-events: none;
	}
	.suggerimento.libero {
		border-color: #a85200;
	}
	.calcolo {
		top: auto;
		bottom: 2.5rem;
		right: auto;
	}
	.foglio {
		max-height: 30dvh;
		overflow-y: auto;
		background: var(--bg);
		border-top: 1px solid var(--border);
		padding: 0.6rem 1rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
	}
	.strumenti,
	.file,
	.azioni {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	/* sul telefono gli strumenti stanno su una riga che scorre di lato, sempre in vista */
	.strumenti {
		flex-wrap: nowrap;
		overflow-x: auto;
		scrollbar-width: thin;
		margin: -0.6rem -1rem 0;
		padding: 0.6rem 1rem 0.4rem;
		position: sticky;
		top: -0.6rem;
		z-index: 1;
		background: var(--bg);
		border-bottom: 1px solid var(--border);
	}
	.strumenti button {
		flex: none;
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
		opacity: 0.45;
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
	button.elimina {
		border-color: #b3261e;
		color: #b3261e;
	}
	button.link {
		border: 0;
		background: none;
		color: var(--accent);
		text-decoration: underline;
		padding: 0 0.3rem;
		min-height: 44px;
	}
	.nota,
	.ripreso {
		margin: 0;
		padding: 0.5rem 0.75rem;
		border-radius: 10px;
		background: var(--surface);
		border: 1px solid var(--border);
	}
	.punto,
	.import {
		border: 2px solid #f2b705;
		border-radius: 12px;
		background: var(--surface);
		padding: 0.5rem 0.75rem;
	}
	.punto p,
	.import p {
		margin: 0 0 0.4rem;
	}
	.nome {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.nome span {
		color: var(--muted);
		font-size: 0.9rem;
	}
	.nome input {
		flex: 1;
		min-width: 0;
		min-height: 44px;
		font: inherit;
		padding: 0 0.6rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--surface);
		color: var(--text);
	}
	.avvisi {
		margin: 0;
		padding: 0;
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.avvisi li {
		padding: 0.45rem 0.7rem;
		border-left: 4px solid #d9a21b;
		background: var(--surface);
		border-radius: 0 8px 8px 0;
		font-size: 0.93rem;
	}
	.avvisi li.forte {
		border-left-color: #b3261e;
	}
	.piccolo {
		margin: 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	button.proponi {
		border-color: #7b2cbf;
		color: #7b2cbf;
		font-weight: 600;
	}
	.invito {
		margin: 0;
	}
	.luoghi h2,
	.salvati h2 {
		font-size: 1rem;
		margin: 0 0 0.3rem;
	}
	.luoghi ul,
	.salvati ul {
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.luoghi li {
		display: flex;
		gap: 0.5rem;
		align-items: baseline;
		padding: 0.15rem 0;
	}
	.luoghi .km {
		min-width: 4.2rem;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
		font-size: 0.9rem;
	}
	.luoghi .tipo {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.salvati li a {
		display: inline-flex;
		min-height: 44px;
		align-items: center;
	}
	@media (min-width: 900px) {
		.planner {
			grid-template-columns: minmax(0, 1fr) 400px;
			grid-template-rows: auto minmax(0, 1fr);
		}
		.stats {
			grid-column: 1 / -1;
			grid-template-columns: repeat(6, minmax(0, 1fr));
		}
		.foglio {
			max-height: none;
			border-top: 0;
			border-left: 1px solid var(--border);
		}
		.strumenti {
			flex-wrap: wrap;
			overflow: visible;
		}
	}
</style>
