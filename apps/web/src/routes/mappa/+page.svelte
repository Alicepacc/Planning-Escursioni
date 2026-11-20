<script lang="ts">
	// Esplora (SPEC §5.1): mappa + lista sincronizzate, ricerca (luoghi, nomi e frasi in italiano),
	// preset rapidi, filtri come chip modificabili, ordinamento, «Cerca in quest'area».
	import { onMount, tick } from 'svelte';
	import { resolve } from '$app/paths';
	import { goto } from '$app/navigation';
	import { generatedAsset } from '#lib/data/paths.ts';
	import MapView from '#lib/map/MapView.svelte';
	import HikeRow from '#lib/ui/HikeRow.svelte';
	import Icon from '#lib/ui/Icon.svelte';
	import TrailInfo from '#lib/components/TrailInfo.svelte';
	import FiltersPanel from '#lib/components/FiltersPanel.svelte';
	import {
		EMPTY_FILTERS,
		PRESETS,
		chipsFor,
		filterItems,
		haversineKm,
		removeChip,
		sectionsIn,
		sortItems,
		textScore,
		type BBox,
		type Chip,
		type ExploreIndex,
		type ExploreItem,
		type Filters,
		type SortKey
	} from '#lib/search/explore.ts';
	import { parseQuery, resolvePlace, type PlaceRow } from '#lib/search/nl.ts';
	import type { MapPoint, TrailWayProps } from '#lib/data/types.ts';

	const PAGE = 40;
	const PLACE_KIND: Record<string, string> = {
		c: 'cima',
		r: 'rifugio',
		b: 'bivacco',
		l: 'lago',
		p: 'paese',
		f: 'frazione',
		s: 'passo/forcella',
		v: 'valle',
		g: 'ghiacciaio'
	};

	let items = $state<ExploreItem[]>([]);
	let loadError = $state('');
	let places = $state<PlaceRow[] | null>(null);
	let filters = $state<Filters>({ ...EMPTY_FILTERS });
	let sort = $state<SortKey>('rilevanza');
	let query = $state('');
	let notes = $state<string[]>([]);
	let selected = $state<string | null>(null);
	let showFilters = $state(false);
	let visible = $state(PAGE);
	let mapBBox = $state<BBox | null>(null);
	let movedByUser = $state(false);
	let focus = $state<BBox | null>(null);
	/** tratti di sentiero toccati sulla mappa: se ne mostrano le informazioni (ADR 0012) */
	let trailWays = $state<TrailWayProps[] | null>(null);

	onMount(async () => {
		try {
			const res = await fetch(generatedAsset('data/esplora/index.json'));
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			items = ((await res.json()) as ExploreIndex).items;
		} catch (err) {
			loadError = `Elenco delle escursioni non disponibile (${err instanceof Error ? err.message : err}).`;
			return;
		}
		// arrivi da «Scopri»: ricerca, scorciatoia o «vicino a me» nell'indirizzo
		const params = new URL(location.href).searchParams;
		const preset = params.get('preset');
		if (preset && PRESETS.some((p) => p.id === preset)) togglePreset(preset);
		const q = params.get('q');
		if (q) await runSearch(q);
		if (params.has('futuro')) filters = { ...filters, futureOnly: true };
		if (params.has('vicino')) locateMe();
	});

	let locating = $state(false);
	function locateMe() {
		if (!navigator.geolocation) {
			notes = ['Posizione non disponibile su questo dispositivo.'];
			return;
		}
		locating = true;
		navigator.geolocation.getCurrentPosition(
			(pos) => {
				locating = false;
				const { longitude: lon, latitude: lat } = pos.coords;
				filters = { ...filters, near: { lon, lat, label: 'te', km: 20 }, area: null };
				focus = aroundBBox(lon, lat, 20);
				visible = PAGE;
			},
			() => {
				locating = false;
				notes = ['Non riesco a leggere la posizione (permesso negato o segnale assente).'];
			},
			{ enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
		);
	}

	async function loadPlaces(): Promise<PlaceRow[]> {
		if (places) return places;
		try {
			const res = await fetch(generatedAsset('data/esplora/luoghi.json'));
			places = res.ok ? ((await res.json()).places as PlaceRow[]) : [];
		} catch {
			places = [];
		}
		return places;
	}

	const origin = $derived<[number, number] | null>(
		filters.near ? [filters.near.lon, filters.near.lat] : null
	);
	const results = $derived(sortItems(filterItems(items, filters), sort, filters, origin));
	const shown = $derived(results.slice(0, visible));
	const points = $derived<MapPoint[]>(
		results.flatMap((i) => (i.s ? [{ id: i.id, lon: i.s[0], lat: i.s[1], k: i.k }] : []))
	);
	const chips = $derived(chipsFor(filters));
	const activeCount = $derived(chips.length);

	// suggerimenti mentre si scrive: luoghi ed escursioni
	const suggestions = $derived.by(() => {
		const q = query.trim();
		if (q.length < 2) return [];
		const out: { label: string; detail: string; action: () => void }[] = [];
		const lower = q.toLowerCase();
		if (places) {
			const seen: Record<string, true> = {};
			for (const p of places) {
				if (out.length >= 5) break;
				if (!p[0].toLowerCase().includes(lower)) continue;
				const key = `${p[0]}|${p[1]}`;
				if (seen[key]) continue;
				seen[key] = true;
				out.push({
					label: p[0],
					detail: `${PLACE_KIND[p[1]] ?? 'luogo'}${p[4] ? ` · ${p[4]} m` : ''}`,
					action: () => choosePlace(p)
				});
			}
		}
		const matching = items.filter((i) => !i.hide && textScore(i, q) === 1).slice(0, 5);
		for (const i of matching)
			// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor usa resolve()
			out.push({ label: i.t, detail: i.src, action: () => goto(hrefFor(i)) });
		return out;
	});

	function hrefFor(item: ExploreItem): string {
		if (item.k === 'a') return resolve('/attivita/[id]', { id: item.id });
		if (item.k === 'i') return resolve('/itinerario/[slug]', { slug: item.id });
		return resolve('/sentiero/[id]', { id: item.id });
	}

	function aroundBBox(lon: number, lat: number, km: number): BBox {
		const dLat = km / 111;
		const dLon = km / (111 * Math.cos((lat * Math.PI) / 180));
		return [lon - dLon, lat - dLat, lon + dLon, lat + dLat];
	}

	function choosePlace(p: PlaceRow, km = 10) {
		filters = { ...filters, near: { lon: p[2], lat: p[3], label: p[0], km }, area: null };
		focus = aroundBBox(p[2], p[3], km);
		query = '';
		visible = PAGE;
	}

	async function submitSearch(e: SubmitEvent) {
		e.preventDefault();
		await runSearch(query.trim());
	}

	async function runSearch(text: string) {
		if (!text) return;
		const before = JSON.stringify(filters);
		const r = parseQuery(text, filters);
		const nextNotes = [...r.unsupported];
		let next = r.filters;
		if (r.place) {
			const found = resolvePlace(r.place.query, await loadPlaces());
			if (found) {
				next = {
					...next,
					near: { lon: found[2], lat: found[3], label: found[0], km: r.place.km },
					area: null
				};
				focus = aroundBBox(found[2], found[3], r.place.km);
				if (r.place.approx) nextNotes.push(r.place.approx);
			} else nextNotes.push(`Luogo «${r.place.query}» non trovato nell'area pilota.`);
		}
		if (JSON.stringify(next) === before && !r.place) {
			// nessun filtro riconosciuto: è una ricerca per nome (luogo o proposta)
			const place = resolvePlace(text, await loadPlaces());
			const named = items.some((i) => textScore(i, text) === 1);
			if (!named && place) {
				choosePlace(place);
				return;
			}
			next = { ...next, text };
		}
		filters = next;
		notes = nextNotes;
		query = '';
		visible = PAGE;
	}

	function togglePreset(id: string) {
		const preset = PRESETS.find((p) => p.id === id)!;
		if (preset.active(filters)) {
			const reset: Record<string, Chip['key'][]> = {
				mezza: ['maxMinutes'],
				intera: ['maxMinutes'],
				bambini: ['maxMinutes', 'maxUp', 'diff:T', 'diff:E'],
				panorama: ['tag:panorama'],
				laghi: ['tag:lago'],
				cima: ['tag:cima']
			};
			filters = reset[id].reduce((f, key) => removeChip(f, key), filters);
		} else filters = preset.apply(filters);
		visible = PAGE;
	}

	function removeFilter(key: Chip['key']) {
		filters = removeChip(filters, key);
		if (key === 'near' || key === 'text') notes = [];
		visible = PAGE;
	}

	function searchHere() {
		if (!mapBBox) return;
		filters = { ...filters, area: mapBBox, near: null };
		movedByUser = false;
		visible = PAGE;
	}

	async function selectItem(id: string, scroll = true) {
		selected = id;
		if (scroll && sheet === 'basso') sheet = 'medio';
		const i = results.findIndex((r) => r.id === id);
		if (i >= visible) visible = i + 1;
		if (!scroll) return;
		await tick();
		document
			.querySelector(`.lista [data-id="${CSS.escape(id)}"]`)
			?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
	}

	function onTrailClick(ways: TrailWayProps[]) {
		trailWays = ways;
	}

	// sul telefono la mappa si inquadra sopra il foglio dell'elenco e sotto la ricerca
	let wide = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(min-width: 900px)');
		wide = mq.matches;
		mq.addEventListener('change', (e) => (wide = e.matches));
	});
	const padding = $derived(
		wide
			? 40
			: {
					top: 130,
					bottom: Math.round((typeof window === 'undefined' ? 800 : window.innerHeight) * 0.42),
					left: 24,
					right: 60
				}
	);

	// foglio dell'elenco: basso (solo l'intestazione), medio (metà schermo) o alto
	type SheetState = 'basso' | 'medio' | 'alto';
	let sheet = $state<SheetState>('medio');
	let sheetEl = $state<HTMLElement>();
	let dragTop = $state<number | null>(null);
	let dragMoved = false;

	function cycleSheet() {
		if (dragMoved) return; // era un trascinamento, non un tocco
		sheet = sheet === 'medio' ? 'alto' : sheet === 'alto' ? 'basso' : 'medio';
	}

	function startDrag(e: PointerEvent) {
		if (!sheetEl?.parentElement) return;
		const box = sheetEl.parentElement.getBoundingClientRect();
		const start = e.clientY;
		const top0 = sheetEl.getBoundingClientRect().top - box.top;
		dragMoved = false;
		const move = (ev: PointerEvent) => {
			const dy = ev.clientY - start;
			if (Math.abs(dy) > 6) dragMoved = true;
			dragTop = Math.min(Math.max(top0 + dy, 90), box.height - 100);
		};
		const end = () => {
			window.removeEventListener('pointermove', move);
			window.removeEventListener('pointerup', end);
			if (dragTop != null && dragMoved) {
				const share = dragTop / box.height;
				sheet = share < 0.3 ? 'alto' : share < 0.7 ? 'medio' : 'basso';
			}
			dragTop = null;
			setTimeout(() => (dragMoved = false), 0);
		};
		window.addEventListener('pointermove', move);
		window.addEventListener('pointerup', end);
	}
</script>

<svelte:head>
	<title>Esplora – Cordata</title>
	<meta
		name="description"
		content="Escursioni delle sezioni CAI e SAT in Trentino-Alto Adige e Dolomiti venete, dalle loro locandine: filtri, mappa dei sentieri e schede."
	/>
</svelte:head>

<div class="esplora" data-foglio={sheet}>
	<div class="mappa">
		<MapView
			label="Mappa delle escursioni"
			legend={['escursioni']}
			{padding}
			{points}
			{selected}
			{focus}
			onPointClick={(id) => selectItem(id)}
			onMoveEnd={(b, byUser) => {
				mapBBox = b;
				if (byUser) movedByUser = true;
			}}
			{onTrailClick}
		/>
		{#if movedByUser}
			<button type="button" class="qui" onclick={searchHere}>Cerca in quest'area</button>
		{/if}
		{#if trailWays}
			<div class="info-sentiero">
				<TrailInfo ways={trailWays} onclose={() => (trailWays = null)} />
			</div>
		{/if}
	</div>

	<div class="sopra">
		<form class="cerca" role="search" onsubmit={submitSearch}>
			<Icon name="cerca" size={20} />
			<label class="sr" for="q">Cerca un luogo o descrivi la gita</label>
			<input
				id="q"
				type="search"
				bind:value={query}
				onfocus={loadPlaces}
				placeholder="Luogo, gita o «anello di 4 ore con un lago»"
				autocomplete="off"
				enterkeyhint="search"
			/>
			<button
				type="button"
				class="filtri"
				aria-label={activeCount ? `Filtri (${activeCount} attivi)` : 'Filtri'}
				onclick={() => (showFilters = true)}
			>
				<Icon name="filtri" size={22} />
				{#if activeCount}<span class="conta">{activeCount}</span>{/if}
			</button>
			{#if suggestions.length}
				<ul class="suggerimenti" role="listbox" aria-label="Suggerimenti">
					{#each suggestions as s, i (i)}
						<li role="option" aria-selected="false">
							<button type="button" onclick={s.action}
								><strong>{s.label}</strong> <span>{s.detail}</span></button
							>
						</li>
					{/each}
				</ul>
			{/if}
		</form>
		<div class="preset" role="group" aria-label="Preset rapidi">
			{#if locating}<span class="cerco">Cerco la posizione…</span>{/if}
			{#each PRESETS as p (p.id)}
				<button type="button" aria-pressed={p.active(filters)} onclick={() => togglePreset(p.id)}
					>{p.label}</button
				>
			{/each}
		</div>
	</div>

	<section
		class="foglio"
		aria-label="Escursioni"
		style:top={dragTop != null ? `${dragTop}px` : null}
		bind:this={sheetEl}
	>
		<button
			type="button"
			class="maniglia"
			aria-label={sheet === 'alto' ? "Riduci l'elenco" : "Allarga l'elenco"}
			onclick={cycleSheet}
			onpointerdown={startDrag}
		>
			<span></span>
		</button>
		<div class="intestazione">
			<h2 aria-live="polite">
				{#if loadError}{loadError}{:else if !items.length}Carico le escursioni…{:else}{results.length}
					{results.length === 1 ? 'escursione' : 'escursioni'}{/if}
			</h2>
			<label class="ordina"
				><span class="sr">Ordina per</span><select bind:value={sort}>
					<option value="rilevanza">Più adatte</option>
					<option value="distanza" disabled={!origin}>Più vicine</option>
					<option value="durata">Più brevi</option>
					<option value="dislivello">Meno dislivello</option>
					<option value="data">Per data</option>
				</select></label
			>
		</div>
		{#if chips.length}
			<div class="attivi">
				{#each chips as chip (chip.key)}
					<button
						type="button"
						class="chip"
						onclick={() => removeFilter(chip.key)}
						aria-label="Togli il filtro {chip.label}">{chip.label} ✕</button
					>
				{/each}
			</div>
		{/if}
		{#each notes as n (n)}<p class="nota">{n}</p>{/each}

		<ul class="lista">
			{#each shown as item (item.id)}
				<li>
					<HikeRow
						{item}
						href={hrefFor(item)}
						selected={item.id === selected}
						distanceKm={origin && item.s ? haversineKm(item.s, origin) : null}
						onfocusitem={(id) => selectItem(id, false)}
					/>
				</li>
			{/each}
		</ul>
		{#if results.length > visible}
			<button type="button" class="altri" onclick={() => (visible += PAGE)}
				>Mostra altre {Math.min(PAGE, results.length - visible)}</button
			>
		{/if}
		<p class="fonti">
			Escursioni: sintesi delle locandine delle sezioni CAI e SAT, con link agli originali; tracce
			ricostruite (tratteggiate se non verificate). Mappa: sentieri del catasto CAI (OSM2CAI) e ©
			OpenStreetMap (ODbL); tocca un sentiero per vederne le informazioni. <a
				href={resolve('/fonti')}>Fonti e licenze</a
			>
		</p>
	</section>
</div>

{#if showFilters}
	<button
		type="button"
		class="velo"
		aria-label="Chiudi i filtri"
		onclick={() => (showFilters = false)}
	></button>
	<FiltersPanel
		bind:filters
		count={results.length}
		sections={sectionsIn(items)}
		onclose={() => (showFilters = false)}
	/>
{/if}

<style>
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
	/* la mappa riempie lo schermo sopra le schede; l'elenco è un foglio che si alza e si abbassa */
	.esplora {
		position: relative;
		height: calc(100dvh - 58px - env(safe-area-inset-bottom));
		overflow: hidden;
	}
	.mappa {
		position: absolute;
		inset: 0;
	}
	/* sul telefono controlli della mappa e legenda stanno sotto la ricerca galleggiante */
	@media (max-width: 899px) {
		.mappa :global(.maplibregl-ctrl-top-right),
		.mappa :global(.legenda) {
			top: calc(env(safe-area-inset-top) + 7.4rem);
		}
	}
	.sopra {
		position: absolute;
		top: calc(env(safe-area-inset-top) + 0.6rem);
		left: 0.9rem;
		right: 0.9rem;
		z-index: 4;
	}
	.cerca {
		position: relative;
		display: flex;
		align-items: center;
		gap: 0.55rem;
		height: 3.1rem;
		padding: 0 0.4rem 0 0.9rem;
		border-radius: 16px;
		background: var(--surface);
		box-shadow: 0 4px 18px rgb(0 0 0 / 14%);
		color: var(--muted);
	}
	.cerca input {
		flex: 1;
		min-width: 0;
		height: 100%;
		border: 0;
		background: transparent;
		color: var(--text);
		font: 400 1rem var(--font-body);
		outline: none;
	}
	.filtri {
		position: relative;
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		border: 0;
		border-radius: 12px;
		background: transparent;
		color: var(--text);
		cursor: pointer;
	}
	.conta {
		position: absolute;
		top: 2px;
		right: 2px;
		min-width: 18px;
		height: 18px;
		border-radius: 9px;
		background: var(--rust);
		color: #fff;
		font: 700 0.68rem/18px var(--font-body);
		text-align: center;
	}
	.suggerimenti {
		position: absolute;
		top: calc(100% + 6px);
		left: 0;
		right: 0;
		margin: 0;
		padding: 0.3rem;
		list-style: none;
		background: var(--surface);
		border-radius: 14px;
		box-shadow: var(--shadow);
		z-index: 6;
	}
	.suggerimenti button {
		width: 100%;
		min-height: 44px;
		padding: 0.4rem 0.6rem;
		border: 0;
		background: none;
		color: var(--text);
		text-align: left;
		font: inherit;
		border-radius: 10px;
		cursor: pointer;
	}
	.suggerimenti button:hover {
		background: var(--chip);
	}
	.suggerimenti span {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.preset {
		display: flex;
		gap: 0.45rem;
		overflow-x: auto;
		margin: 0.6rem -0.9rem 0;
		padding: 0 0.9rem 0.3rem;
		scrollbar-width: none;
	}
	.preset button,
	.cerco {
		flex: none;
		min-height: 38px;
		padding: 0 0.85rem;
		border: 0;
		border-radius: 999px;
		background: var(--surface);
		color: var(--text);
		font: 500 0.88rem var(--font-body);
		box-shadow: 0 2px 8px rgb(0 0 0 / 12%);
		cursor: pointer;
	}
	.cerco {
		display: inline-flex;
		align-items: center;
		color: var(--muted);
	}
	.preset button[aria-pressed='true'] {
		background: var(--accent);
		color: var(--on-accent);
	}
	.qui {
		position: absolute;
		top: calc(env(safe-area-inset-top) + 8.6rem);
		left: 50%;
		transform: translateX(-50%);
		z-index: 3;
		min-height: 40px;
		padding: 0 1rem;
		border-radius: 999px;
		border: none;
		background: var(--accent);
		color: var(--on-accent);
		font: 600 0.9rem var(--font-body);
		box-shadow: 0 2px 8px rgb(0 0 0 / 30%);
		cursor: pointer;
	}
	.info-sentiero {
		position: absolute;
		left: 0.6rem;
		right: 3.4rem;
		top: calc(env(safe-area-inset-top) + 8.4rem);
		max-height: 45%;
		display: flex;
		z-index: 5;
	}
	.foglio {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		top: 46%;
		z-index: 4;
		display: flex;
		flex-direction: column;
		background: var(--surface);
		border-radius: 22px 22px 0 0;
		box-shadow: 0 -6px 24px rgb(0 0 0 / 14%);
		padding: 0 1.1rem;
		overflow-y: auto;
		overscroll-behavior: contain;
		transition: top 0.25s ease;
	}
	[data-foglio='alto'] .foglio {
		top: calc(env(safe-area-inset-top) + 8rem);
	}
	[data-foglio='basso'] .foglio {
		top: calc(100% - 7.5rem);
	}
	.maniglia {
		position: sticky;
		top: 0;
		z-index: 2;
		flex: none;
		display: grid;
		place-items: center;
		height: 26px;
		margin: 0 -1.1rem;
		border: 0;
		background: var(--surface);
		cursor: grab;
		touch-action: none;
	}
	.maniglia span {
		width: 40px;
		height: 5px;
		border-radius: 3px;
		background: var(--border);
	}
	.intestazione {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
	}
	.intestazione h2 {
		margin: 0;
		font-size: 1.25rem;
	}
	.ordina select {
		min-height: 40px;
		border: 0;
		background: transparent;
		color: var(--muted);
		font: 500 0.88rem var(--font-body);
		text-align: right;
	}
	.attivi {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-top: 0.4rem;
	}
	.chip {
		min-height: 36px;
		padding: 0 0.75rem;
		border: 0;
		border-radius: 999px;
		background: var(--brand-soft);
		color: var(--accent);
		font: 600 0.82rem var(--font-body);
		cursor: pointer;
	}
	.nota {
		margin: 0.4rem 0 0;
		color: var(--muted);
		font-size: 0.88rem;
	}
	.lista {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.altri {
		margin: 0.8rem 0;
		min-height: 44px;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--surface);
		color: var(--accent);
		font: 600 0.92rem var(--font-body);
		cursor: pointer;
	}
	.fonti {
		color: var(--muted);
		font-size: 0.78rem;
		padding-bottom: 1.2rem;
	}
	.velo {
		position: fixed;
		inset: 0;
		z-index: 40;
		border: 0;
		background: rgb(0 0 0 / 35%);
	}
	/* schermi larghi: elenco a sinistra, mappa a destra */
	@media (min-width: 900px) {
		.foglio,
		[data-foglio='alto'] .foglio,
		[data-foglio='basso'] .foglio {
			top: 0;
			right: auto;
			width: 420px;
			border-radius: 0;
			box-shadow: 1px 0 0 var(--border);
			padding-top: 6.6rem;
		}
		.maniglia {
			display: none;
		}
		.sopra {
			right: auto;
			width: 392px;
			z-index: 5;
		}
		.mappa {
			left: 420px;
		}
	}
</style>
