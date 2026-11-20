<script lang="ts">
	// Scopri (ADR 0015): la pagina iniziale. Ricerca, scorciatoie verso la mappa già filtrata,
	// avviso di primo uso sull'affidabilità, gite CAI in programma e itinerari verificati.
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { generatedAsset } from '#lib/data/paths.ts';
	import type { ExploreIndex, ExploreItem } from '#lib/search/explore.ts';
	import HikeCard from '#lib/ui/HikeCard.svelte';
	import HikeRow from '#lib/ui/HikeRow.svelte';
	import Icon from '#lib/ui/Icon.svelte';

	const WELCOME_KEY = 'cordata.benvenuto';
	let items = $state<ExploreItem[] | null>(null);
	let loadError = $state('');
	let query = $state('');
	let welcome = $state(false);

	const hour = new Date().getHours();
	const greeting = hour < 12 ? 'Buongiorno' : hour < 18 ? 'Buon pomeriggio' : 'Buonasera';
	const weekday = new Date().getDay();
	const headline =
		weekday >= 4 || weekday === 0
			? 'Dove andiamo questo fine settimana?'
			: 'Dove andiamo la prossima volta?';

	const SHORTCUTS = [
		{ label: 'Vicino a me', query: 'vicino=1' },
		{ label: 'Mezza giornata', query: 'preset=mezza' },
		{ label: 'Laghi', query: 'preset=laghi' },
		{ label: 'Cime', query: 'preset=cima' },
		{ label: 'Panoramiche', query: 'preset=panorama' },
		{ label: 'Con bambini', query: 'preset=bambini' }
	];

	onMount(async () => {
		try {
			welcome = localStorage.getItem(WELCOME_KEY) !== 'visto';
		} catch {
			welcome = true;
		}
		try {
			const res = await fetch(generatedAsset('data/esplora/index.json'));
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			items = ((await res.json()) as ExploreIndex).items.filter((i) => !i.hide);
		} catch (err) {
			loadError = `Escursioni non disponibili (${err instanceof Error ? err.message : err}).`;
		}
	});

	const upcoming = $derived(
		(items ?? [])
			.filter((i) => i.fut && i.date)
			.sort((a, b) => (a.date ?? '').localeCompare(b.date ?? ''))
			.slice(0, 10)
	);
	const picks = $derived(
		(items ?? [])
			.filter((i) => i.ok && !i.fut)
			.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
			.slice(0, 6)
	);
	const count = $derived(items?.length ?? 0);

	function hrefFor(item: ExploreItem): string {
		return item.k === 'a'
			? resolve('/attivita/[id]', { id: item.id })
			: resolve('/itinerario/[slug]', { slug: item.id });
	}

	function dismiss() {
		welcome = false;
		try {
			localStorage.setItem(WELCOME_KEY, 'visto');
		} catch {
			// spazio locale non disponibile: l'avviso riappare alla prossima visita
		}
	}

	function search(e: SubmitEvent) {
		e.preventDefault();
		const q = query.trim();
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso da resolve() con parametri
		goto(`${resolve('/mappa')}${q ? `?q=${encodeURIComponent(q)}` : ''}`);
	}
</script>

<svelte:head><title>Cordata – escursioni in Trentino-Alto Adige e Dolomiti</title></svelte:head>

<div class="pagina scopri">
	<p class="hello">{greeting}</p>
	<h1>{headline}</h1>

	<form class="search" role="search" onsubmit={search}>
		<Icon name="cerca" size={20} />
		<input
			type="search"
			bind:value={query}
			placeholder="Cima, rifugio, valle o «facile con lago»"
			aria-label="Cerca un'escursione"
			enterkeyhint="search"
		/>
	</form>

	<nav class="chips" aria-label="Scorciatoie">
		{#each SHORTCUTS as s (s.label)}
			<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso da resolve() con parametri -->
			<a class="chip" href={`${resolve('/mappa')}?${s.query}`}>{s.label}</a>
		{/each}
	</nav>

	{#if welcome}
		<aside class="welcome">
			<span class="shield"><Icon name="affidabile" size={30} stroke={2.2} /></span>
			<div>
				<b>Solo escursioni affidabili</b>
				<p>
					Le gite vengono dalle locandine delle sezioni CAI. La traccia la ricostruiamo noi e la
					confrontiamo con la locandina: pubblichiamo solo quelle che coincidono.
				</p>
				<div class="actions">
					<a href={resolve('/fonti')}>Come funziona</a>
					<button type="button" onclick={dismiss}>Ho capito</button>
				</div>
			</div>
		</aside>
	{/if}

	{#if loadError}
		<p class="errore" role="alert">{loadError}</p>
	{:else if !items}
		<p class="nota">Caricamento…</p>
	{:else}
		{#if upcoming.length}
			<section aria-labelledby="programma">
				<div class="sec">
					<h2 id="programma">In programma con il CAI</h2>
					<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso da resolve() con parametri -->
					<a href={`${resolve('/mappa')}?futuro=1`}>Vedi tutte</a>
				</div>
				<div class="carousel">
					{#each upcoming as item (item.id)}<HikeCard {item} href={hrefFor(item)} />{/each}
				</div>
			</section>
		{/if}
		<section aria-labelledby="itinerari">
			<div class="sec">
				<h2 id="itinerari">Itinerari verificati</h2>
				<a href={resolve('/mappa')}>Tutte le {count}</a>
			</div>
			{#each picks as item (item.id)}<HikeRow {item} href={hrefFor(item)} />{/each}
		</section>
	{/if}

	<p class="fonti">
		Dati aperti: OpenStreetMap, catasto sentieri CAI (INFOMONT), locandine delle sezioni CAI.
		<a href={resolve('/fonti')}>Fonti e licenze</a>
	</p>
</div>

<style>
	.scopri {
		padding-bottom: 2rem;
	}
	.hello {
		margin: 0.6rem 0 0.15rem;
		color: var(--muted);
	}
	h1 {
		font-size: 1.95rem;
		margin: 0;
		max-width: 22rem;
	}
	.search {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		height: 3.1rem;
		margin: 1rem 0 0.75rem;
		padding: 0 0.9rem;
		border-radius: 16px;
		background: var(--surface);
		border: 1px solid var(--border);
		box-shadow: var(--shadow);
		color: var(--muted);
	}
	.search input {
		flex: 1;
		min-width: 0;
		border: 0;
		background: transparent;
		color: var(--text);
		font: 400 1rem var(--font-body);
		outline: none;
		height: 100%;
	}
	.chips {
		display: flex;
		gap: 0.5rem;
		overflow-x: auto;
		margin: 0 -1.1rem;
		padding: 0 1.1rem 0.2rem;
		scrollbar-width: none;
	}
	.chip {
		flex: none;
		display: inline-flex;
		align-items: center;
		height: 2.4rem;
		padding: 0 0.85rem;
		border-radius: 999px;
		background: var(--chip);
		color: var(--text);
		font: 500 0.9rem var(--font-body);
		text-decoration: none;
	}
	.chip:first-child {
		background: var(--accent);
		color: var(--on-accent);
	}
	.welcome {
		display: flex;
		gap: 0.8rem;
		margin-top: 1rem;
		padding: 0.95rem;
		border-radius: var(--r-lg);
		background: var(--brand-soft);
	}
	.shield {
		color: var(--accent);
	}
	.welcome p {
		margin: 0.15rem 0 0.5rem;
		font-size: 0.88rem;
	}
	.actions {
		display: flex;
		gap: 1rem;
		align-items: center;
	}
	.actions a,
	.actions button {
		font: 600 0.9rem var(--font-body);
		min-height: 44px;
		display: inline-flex;
		align-items: center;
	}
	.actions a {
		text-decoration: none;
	}
	.actions button {
		border: 0;
		background: none;
		color: var(--muted);
		padding: 0;
		cursor: pointer;
	}
	.sec {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		margin: 1.5rem 0 0.6rem;
	}
	.sec h2 {
		font-size: 1.3rem;
		margin: 0;
	}
	.sec a {
		font: 600 0.9rem var(--font-body);
		text-decoration: none;
	}
	.carousel {
		display: flex;
		gap: 0.75rem;
		overflow-x: auto;
		scroll-snap-type: x mandatory;
		margin: 0 -1.1rem;
		padding: 0 1.1rem 0.4rem;
		scroll-padding: 0 1.1rem;
		scrollbar-width: none;
	}
	.nota,
	.fonti {
		color: var(--muted);
	}
	.fonti {
		margin-top: 2rem;
		font-size: 0.8rem;
	}
	.errore {
		color: #b42318;
	}
</style>
