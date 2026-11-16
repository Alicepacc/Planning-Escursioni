import { defineConfig } from 'vitest/config';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
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

// Schede delle attività CAI (archivio del pilota, `python -m cordata_ingest.build activities`)
const activityIndex = 'static/data/attivita/index.json';
const activityEntries: `/${string}`[] = existsSync(activityIndex)
	? JSON.parse(readFileSync(activityIndex, 'utf8')).map(
			(a: { id: string }) => `/attivita/${a.id}` as const
		)
	: [];

// itinerari (oggi la fixture Val d'Inferno), non più collegati da un link statico di Esplora
const itineraryDir = 'static/data/itinerari';
const itineraryEntries: `/${string}`[] = existsSync(itineraryDir)
	? readdirSync(itineraryDir)
			.filter((f) => f.endsWith('.json'))
			.map((f) => `/itinerario/${f.replace(/\.json$/, '')}` as const)
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
			// sotto-percorso per GitHub Pages (es. BASE_PATH=/Planning-Escursioni); vuoto altrove
			paths: { base: (process.env.BASE_PATH ?? '') as '' | `/${string}` },
			prerender: {
				entries: ['*', ...trailEntries, ...activityEntries, ...itineraryEntries],
				// senza i dati generati (es. in CI) le schede non esistono: avvisa e prosegui
				handleHttpError: 'warn',
				handleUnseenRoutes: 'warn'
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
