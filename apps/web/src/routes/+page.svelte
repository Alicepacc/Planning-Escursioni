<script lang="ts">
	// Esplora (SPEC §5.1): mappa + lista sincronizzate, ricerca (luoghi, nomi e frasi in italiano),
	// preset rapidi, filtri come chip modificabili, ordinamento, «Cerca in quest'area».
	import { onMount, tick } from 'svelte';
	import { resolve } from '$app/paths';
	import { goto } from '$app/navigation';
	import { generatedAsset } from '#lib/data/paths.ts';
	import MapView from '#lib/map/MapView.svelte';
	import ResultCard from '#lib/components/ResultCard.svelte';
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
		}
	});

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
		results.map((i) => ({ id: i.id, lon: i.s[0], lat: i.s[1], k: i.k }))
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
		const text = query.trim();
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
</script>

<svelte:head>
	<title>Esplora – Cordata</title>
	<meta
		name="description"
		content="Escursioni delle sezioni CAI e SAT in Trentino-Alto Adige e Dolomiti venete, dalle loro locandine: filtri, mappa dei sentieri e schede."
	/>
</svelte:head>

<div class="esplora">
	<div class="mappa">
		<MapView
			label="Mappa delle escursioni"
			legend={['escursioni']}
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

	<section class="pannello-lista" aria-label="Escursioni">
		<form class="cerca" role="search" onsubmit={submitSearch}>
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
			<button type="submit">Cerca</button>
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
			{#each PRESETS as p (p.id)}
				<button type="button" aria-pressed={p.active(filters)} onclick={() => togglePreset(p.id)}
					>{p.label}</button
				>
			{/each}
		</div>

		<div class="attivi">
			<button type="button" class="filtri" onclick={() => (showFilters = true)}>
				Filtri{#if activeCount}
					({activeCount}){/if}
			</button>
			{#each chips as chip (chip.key)}
				<button
					type="button"
					class="chip"
					onclick={() => removeFilter(chip.key)}
					aria-label="Togli il filtro {chip.label}">{chip.label} ✕</button
				>
			{/each}
		</div>
		{#each notes as n (n)}<p class="nota">{n}</p>{/each}

		<div class="intestazione">
			<p aria-live="polite">
				{#if loadError}{loadError}{:else if !items.length}Carico le escursioni…{:else}<strong
						>{results.length}</strong
					>
					{results.length === 1 ? 'escursione' : 'escursioni'} delle sezioni CAI{/if}
			</p>
			<label
				>Ordina <select bind:value={sort}>
					<option value="rilevanza">rilevanza</option>
					<option value="distanza" disabled={!origin}>distanza</option>
					<option value="durata">durata</option>
					<option value="dislivello">dislivello</option>
					<option value="data">data</option>
				</select></label
			>
		</div>

		<ul class="lista">
			{#each shown as item (item.id)}
				<li>
					<ResultCard
						{item}
						href={hrefFor(item)}
						selected={item.id === selected}
						distanceKm={origin ? haversineKm(item.s, origin) : null}
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
	.esplora {
		display: grid;
		/* minmax(0, …): la riga dei preset scorre in orizzontale invece di allargare la pagina */
		grid-template-columns: minmax(0, 1fr);
		grid-template-rows: 44dvh auto;
	}
	@media (min-width: 900px) {
		.esplora {
			grid-template-rows: none;
			grid-template-columns: 420px minmax(0, 1fr);
			/* intestazione (≈ 65 px) e barra di navigazione (≈ 57 px) del layout */
			height: calc(100dvh - 122px);
		}
		.pannello-lista {
			order: -1;
			overflow-y: auto;
			min-height: 0;
		}
	}
	.mappa {
		position: relative;
		min-height: 260px;
	}
	.qui {
		position: absolute;
		top: 0.75rem;
		left: 50%;
		transform: translateX(-50%);
		z-index: 2;
		min-height: 44px;
		padding: 0 1rem;
		border-radius: 999px;
		border: none;
		background: var(--accent);
		color: #fff;
		font: inherit;
		font-weight: 700;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
		cursor: pointer;
	}
	.pannello-lista {
		padding: 0.75rem 1rem 1.5rem;
		min-width: 0;
	}
	.cerca {
		position: relative;
		display: flex;
		gap: 0.5rem;
	}
	.cerca input {
		flex: 1;
		min-width: 0;
		min-height: 44px;
		padding: 0 0.8rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		font: inherit;
		background: var(--surface);
		color: inherit;
	}
	.cerca > button,
	.filtri,
	.altri {
		min-height: 44px;
		padding: 0 1rem;
		border-radius: 10px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: inherit;
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.suggerimenti {
		position: absolute;
		top: calc(100% + 4px);
		left: 0;
		right: 0;
		z-index: 20;
		list-style: none;
		margin: 0;
		padding: 0.25rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 10px;
		box-shadow: 0 6px 18px rgba(0, 0, 0, 0.15);
	}
	.suggerimenti button {
		width: 100%;
		text-align: left;
		min-height: 44px;
		border: none;
		background: none;
		color: inherit;
		font: inherit;
		padding: 0.3rem 0.5rem;
		cursor: pointer;
		border-radius: 8px;
	}
	.suggerimenti button:hover {
		background: color-mix(in srgb, var(--accent) 10%, transparent);
	}
	.suggerimenti span {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.preset,
	.attivi {
		display: flex;
		gap: 0.4rem;
		overflow-x: auto;
		padding: 0.6rem 0 0.1rem;
		scrollbar-width: none;
	}
	.attivi {
		flex-wrap: wrap;
		overflow: visible;
	}
	.preset button,
	.chip {
		flex: none;
		min-height: 40px;
		padding: 0 0.85rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: inherit;
		font: inherit;
		font-size: 0.92rem;
		cursor: pointer;
	}
	.preset button[aria-pressed='true'],
	.chip {
		background: color-mix(in srgb, var(--accent) 14%, var(--surface));
		border-color: var(--accent);
	}
	.intestazione {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}
	.intestazione select {
		min-height: 40px;
		font: inherit;
	}
	.lista {
		list-style: none;
		padding: 0;
		margin: 0.25rem 0 0;
		display: grid;
		gap: 0.6rem;
	}
	.altri {
		width: 100%;
		margin-top: 0.75rem;
	}
	.nota,
	.fonti {
		color: var(--muted);
		font-size: 0.85rem;
		margin: 0.4rem 0 0;
	}
	.fonti {
		margin-top: 1rem;
	}
	.velo {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.35);
		border: none;
		z-index: 40;
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
	}
</style>
