<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import favicon from '#lib/assets/favicon.svg';
	import { t, type MessageKey } from '#lib/i18n/index.ts';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	const sections: { path: '/' | '/pianifica' | '/uscite' | '/profilo'; label: MessageKey }[] = [
		{ path: '/', label: 'nav.explore' },
		{ path: '/pianifica', label: 'nav.plan' },
		{ path: '/uscite', label: 'nav.outings' },
		{ path: '/profilo', label: 'nav.profile' }
	];
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>{t('app.name')} – {t('app.tagline')}</title>
	<meta name="description" content={t('app.tagline')} />
</svelte:head>

<div class="shell">
	<header>
		<a class="brand" href={resolve('/')}>{t('app.name')}</a>
		<a class="sources" href={resolve('/fonti')}>{t('nav.sources')}</a>
	</header>

	<main>
		{@render children()}
	</main>

	<nav aria-label="Sezioni principali">
		{#each sections as section (section.path)}
			<a
				href={resolve(section.path)}
				aria-current={page.url.pathname === section.path ? 'page' : undefined}
			>
				{t(section.label)}
			</a>
		{/each}
	</nav>
</div>

<style>
	:global(:root) {
		--bg: #f6f5f1;
		--surface: #ffffff;
		--text: #1b1f1d;
		--muted: #56605b;
		--accent: #1f5f3f;
		--border: #d9d6cc;
		color-scheme: light dark;
	}
	@media (prefers-color-scheme: dark) {
		:global(:root) {
			--bg: #141816;
			--surface: #1e2421;
			--text: #f1f3ef;
			--muted: #b3bcb6;
			--accent: #8fd3ab;
			--border: #38413c;
		}
	}
	:global(body) {
		margin: 0;
		background: var(--bg);
		color: var(--text);
		font:
			16px/1.5 system-ui,
			-apple-system,
			'Segoe UI',
			Roboto,
			sans-serif;
	}
	:global(a) {
		color: var(--accent);
	}
	.shell {
		display: flex;
		flex-direction: column;
		min-height: 100dvh;
		max-width: 48rem;
		margin: 0 auto;
	}
	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.5rem 1rem;
	}
	.brand {
		font-size: 1.25rem;
		font-weight: 700;
		text-decoration: none;
		color: var(--text);
		min-height: 48px;
		display: inline-flex;
		align-items: center;
	}
	.sources {
		min-height: 48px;
		display: inline-flex;
		align-items: center;
	}
	main {
		flex: 1;
		padding: 0.5rem 1rem 1.5rem;
	}
	nav {
		position: sticky;
		bottom: 0;
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		background: var(--surface);
		border-top: 1px solid var(--border);
		padding-bottom: env(safe-area-inset-bottom);
	}
	nav a {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 56px;
		text-decoration: none;
		color: var(--muted);
		font-weight: 600;
	}
	nav a[aria-current='page'] {
		color: var(--accent);
		box-shadow: inset 0 3px 0 var(--accent);
	}
</style>
