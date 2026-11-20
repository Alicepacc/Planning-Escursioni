<script lang="ts">
	// Guscio dell'app (ADR 0015, direzione «Rifugio»): intestazione con marchio e profilo, quattro
	// schede in basso (Scopri, Mappa, Pianifica, Uscite), tema chiaro o scuro come il telefono.
	import '@fontsource-variable/fraunces';
	import '@fontsource-variable/inter';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import favicon from '#lib/assets/favicon.svg';
	import { t, type MessageKey } from '#lib/i18n/index.ts';
	import Icon, { type IconName } from '#lib/ui/Icon.svelte';
	import Welcome from '#lib/ui/Welcome.svelte';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	type TabPath = '/' | '/mappa' | '/pianifica' | '/uscite';
	const tabs: { path: TabPath; label: MessageKey; icon: IconName; also?: string[] }[] = [
		{ path: '/', label: 'nav.discover', icon: 'scopri' },
		{ path: '/mappa', label: 'nav.map', icon: 'mappa', also: ['/attivita', '/itinerario'] },
		{ path: '/pianifica', label: 'nav.plan', icon: 'pianifica' },
		{ path: '/uscite', label: 'nav.outings', icon: 'uscite', also: ['/uscita'] }
	];

	function active(tab: (typeof tabs)[number]): boolean {
		const here = page.url.pathname;
		const root = resolve('/');
		if (tab.path === '/') return here === root || here === root.replace(/\/$/, '');
		return [tab.path, ...(tab.also ?? [])].some((p) => here.startsWith(resolve('/') + p.slice(1)));
	}

	// la mappa e le schede occupano tutto lo schermo; le schede hanno la loro barra delle azioni
	const here = $derived(page.url.pathname);
	const isDetail = $derived(
		['/attivita', '/itinerario'].some((p) => here.startsWith(resolve('/') + p.slice(1)))
	);
	const fullBleed = $derived(here.startsWith(resolve('/mappa')) || isDetail);
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>{t('app.name')} – {t('app.tagline')}</title>
	<meta name="description" content={t('app.tagline')} />
</svelte:head>

<div class="shell" class:full={fullBleed}>
	{#if !fullBleed}
		<header>
			<a class="brand" href={resolve('/')}>
				<svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
					<rect width="32" height="32" rx="8" fill="var(--accent)" />
					<path d="M5 24 13 9l8 15Z" fill="var(--on-accent)" />
					<path d="M17.5 24 21 16.5 27 24Z" fill="var(--on-accent)" opacity=".7" />
				</svg>
				{t('app.name')}
			</a>
			<a class="profile" href={resolve('/profilo')} aria-label={t('nav.profile')}>
				<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
					<circle cx="12" cy="8.5" r="3.6" fill="none" stroke="currentColor" stroke-width="2" />
					<path
						d="M5 19.5a7 7 0 0 1 14 0"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
					/>
				</svg>
			</a>
		</header>
	{/if}

	<main>
		{@render children()}
	</main>

	<Welcome />

	<nav aria-label="Sezioni principali" class:nascosta={isDetail}>
		{#each tabs as tab (tab.path)}
			<a href={resolve(tab.path)} aria-current={active(tab) ? 'page' : undefined}>
				<Icon name={tab.icon} size={25} stroke={1.9} />
				<span>{t(tab.label)}</span>
			</a>
		{/each}
	</nav>
</div>

<style>
	/* Palette «Rifugio»: carta calda, verde bosco, ruggine. I nomi vecchi restano validi. */
	:global(:root) {
		--bg: #f4efe5;
		--surface: #fffdf8;
		--text: #1e2622;
		--muted: #6e6b60;
		--accent: #1f5c46;
		--on-accent: #ffffff;
		--border: #e4dccb;
		--brand-soft: #e3ede6;
		--chip: #ede6d8;
		--rust: #b8532a;
		--ok: #1f7a4d;
		--shadow: 0 1px 2px rgb(30 38 34 / 6%), 0 6px 18px rgb(30 38 34 / 7%);
		--diff-T: #2e7d32;
		--diff-E: #1f6fb2;
		--diff-EE: #c62828;
		--diff-EEA: #1e1e1e;
		--diff-EAI: #6a4fb3;
		--font-display: 'Fraunces Variable', Georgia, 'Times New Roman', serif;
		--font-body: 'Inter Variable', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
		--r-sm: 8px;
		--r-md: 14px;
		--r-lg: 18px;
		color-scheme: light;
	}
	/* al buio: segue il telefono, salvo scelta «chiaro» nel profilo; oppure scelta «scuro» */
	@media (prefers-color-scheme: dark) {
		:global(:root:not([data-theme='light'])) {
			--bg: #151a17;
			--surface: #1e2420;
			--text: #ede8dd;
			--muted: #a9a595;
			--accent: #7cc3a0;
			--on-accent: #10201a;
			--border: #2e3631;
			--brand-soft: #23332b;
			--chip: #262d28;
			--rust: #e08a5f;
			--ok: #6fcf97;
			--shadow: 0 1px 2px rgb(0 0 0 / 30%), 0 6px 18px rgb(0 0 0 / 30%);
			--diff-EEA: #000000;
			color-scheme: dark;
		}
	}
	:global(:root[data-theme='dark']) {
		--bg: #151a17;
		--surface: #1e2420;
		--text: #ede8dd;
		--muted: #a9a595;
		--accent: #7cc3a0;
		--on-accent: #10201a;
		--border: #2e3631;
		--brand-soft: #23332b;
		--chip: #262d28;
		--rust: #e08a5f;
		--ok: #6fcf97;
		--shadow: 0 1px 2px rgb(0 0 0 / 30%), 0 6px 18px rgb(0 0 0 / 30%);
		--diff-EEA: #000000;
		color-scheme: dark;
	}
	:global(body) {
		margin: 0;
		background: var(--bg);
		color: var(--text);
		font:
			16px/1.5 var(--font-body),
			sans-serif;
		-webkit-font-smoothing: antialiased;
	}
	:global(h1, h2, h3) {
		font-family: var(--font-display);
		font-weight: 600;
		letter-spacing: -0.01em;
		line-height: 1.15;
	}
	:global(a) {
		color: var(--accent);
	}
	/* campi dei moduli: stessi colori, bordi e altezze in tutte le pagine, anche al buio.
	   Con :where() la specificità è zero: gli stili delle singole pagine restano più forti */
	:global(:where(input:not([type='radio'], [type='checkbox'], [type='range']), select, textarea)) {
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		border-radius: 12px;
		font: inherit;
		min-height: 44px;
		box-sizing: border-box;
	}
	:global(:where(textarea)) {
		padding: 0.6rem 0.75rem;
	}
	:global(:where(input, textarea)::placeholder) {
		color: var(--muted);
	}
	:global(:where(fieldset)) {
		border: 1px solid var(--border);
		border-radius: var(--r-md);
		background: var(--surface);
	}
	:global(:where(legend)) {
		font-weight: 600;
		padding: 0 0.3rem;
	}
	:global(:where(input[type='radio'], input[type='checkbox'])) {
		accent-color: var(--accent);
	}
	:global(:focus-visible) {
		outline: 3px solid var(--rust);
		outline-offset: 2px;
	}
	.shell {
		display: flex;
		flex-direction: column;
		min-height: 100dvh;
	}
	header {
		position: sticky;
		top: 0;
		z-index: 20;
		background: color-mix(in srgb, var(--bg) 92%, transparent);
		backdrop-filter: blur(12px);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: calc(0.35rem + env(safe-area-inset-top)) 1.1rem 0.35rem;
	}
	.brand {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		min-height: 48px;
		font: 600 1.3rem var(--font-display);
		color: var(--text);
		text-decoration: none;
	}
	.profile {
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		border-radius: 50%;
		background: var(--brand-soft);
		color: var(--accent);
	}
	main {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-height: 0;
	}
	:global(.pagina) {
		width: 100%;
		max-width: 52rem;
		margin: 0 auto;
		padding: 0.5rem 1.1rem 1.5rem;
		box-sizing: border-box;
	}
	nav {
		position: sticky;
		bottom: 0;
		z-index: 20;
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		background: color-mix(in srgb, var(--surface) 92%, transparent);
		backdrop-filter: blur(16px);
		border-top: 1px solid var(--border);
		padding: 6px 0 env(safe-area-inset-bottom);
	}
	nav.nascosta {
		display: none;
	}
	nav a {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		min-height: 52px;
		text-decoration: none;
		color: var(--muted);
		font: 500 0.72rem var(--font-body);
	}
	nav a[aria-current='page'] {
		color: var(--accent);
		font-weight: 600;
	}
	@media (min-width: 900px) {
		nav a {
			flex-direction: row;
			gap: 0.5rem;
			font-size: 0.9rem;
		}
	}
</style>
