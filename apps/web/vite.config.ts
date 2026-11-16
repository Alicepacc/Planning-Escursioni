import { defineConfig } from 'vitest/config';
import { existsSync, readFileSync } from 'node:fs';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';

// Schede dei sentieri da prerenderizzare: tutte quelle prodotte dalla pipeline di ingestion
// (services/ingest, `python -m cordata_ingest.build trails`). Senza dati la build funziona lo stesso.
const trailIndex = 'static/data/sentieri/index.json';
const trailEntries: `/${string}`[] = existsSync(trailIndex)
	? JSON.parse(readFileSync(trailIndex, 'utf8')).trails.map(
			(t: { id: string }) => `/sentiero/${t.id}` as const
		)
	: [];

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// sito statico su Cloudflare Pages (ADR 0005); 404.html fa da fallback per le pagine
			// non prerenderizzate, che vengono disegnate nel browser
			adapter: adapter({ fallback: '404.html' }),
			prerender: {
				entries: ['*', ...trailEntries],
				// senza i dati generati (es. in CI) le schede non esistono: avvisa e prosegui
				handleHttpError: 'warn'
			}
		})
	],
	test: {
		expect: { requireAssertions: true },
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'server',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
