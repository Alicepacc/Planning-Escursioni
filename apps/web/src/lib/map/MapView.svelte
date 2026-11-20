<script module lang="ts">
	// condiviso tra tutte le mappe della pagina: i protocolli si registrano una volta sola
	let protocolsReady: Promise<string | undefined> | undefined;
</script>

<script lang="ts">
	// Mappa MapLibre: base OpenFreeMap, rilievo e isoipse da Mapterhorn, sentieri CAI (PMTiles).
	import { onDestroy, onMount } from 'svelte';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import type { GeoJSONSource, Map as MlMap, Marker as MlMarker } from 'maplibre-gl';
	import { resolve } from '$app/paths';
	import { generatedAsset } from '../data/paths';
	// MapLibre 6 (ESM) carica il worker relativo a sé stesso: con Vite va dichiarato come asset
	import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
	import type { MapPoint, TrailWayProps } from '../data/types';
	import { demSource } from './dem';
	import MapLegend from './MapLegend.svelte';
	import { BASEMAP_STYLE_URL, ESCURSIONE_POINT_COLOR, withCordataLayers } from './style';

	interface StageMarker {
		n: number;
		name: string;
		lon: number;
		lat: number;
	}

	interface Props {
		bbox?: [number, number, number, number];
		line?: [number, number][];
		lineColor?: string;
		/** traccia tratteggiata: ricostruzione non ancora verificata */
		lineDashed?: boolean;
		cursor?: [number, number] | null;
		stages?: StageMarker[];
		label?: string;
		onTrailClick?: (ways: TrailWayProps[], lngLat: [number, number]) => void;
		/** proposte da mostrare come punti cliccabili */
		points?: MapPoint[];
		selected?: string | null;
		onPointClick?: (id: string) => void;
		/** riquadro visibile dopo ogni spostamento; `byUser` se l'ha mosso l'utente */
		onMoveEnd?: (bbox: [number, number, number, number], byUser: boolean) => void;
		/** riquadro da inquadrare quando cambia */
		focus?: [number, number, number, number] | null;
		/** mappa pronta: chi la usa può aggiungere sorgenti, layer e gestori (planner) */
		onReady?: (map: MlMap, lib: typeof import('maplibre-gl')) => void;
		/** sezioni della legenda oltre a sentieri e luoghi */
		legend?: ('escursioni' | 'percorso' | 'planner')[];
	}

	let {
		bbox,
		line,
		lineColor = '#c0392b',
		lineDashed = false,
		cursor = null,
		stages = [],
		label = 'Mappa dei sentieri',
		onTrailClick,
		points = [],
		selected = null,
		onPointClick,
		onMoveEnd,
		focus = null,
		onReady,
		legend = []
	}: Props = $props();

	let container: HTMLDivElement;
	let map: MlMap | undefined;
	let ready = $state(false);
	let failed = $state<string | null>(null);
	let cursorMarker: MlMarker | undefined;
	let stageMarkers: MlMarker[] = [];
	let resizeObserver: ResizeObserver | undefined;
	let lib: typeof import('maplibre-gl') | undefined;
	// la pagina può cambiare mentre la mappa si sta ancora caricando
	let destroyed = false;
	let collapseTimer: ReturnType<typeof setTimeout> | undefined;

	const PILOT_BOUNDS: [number, number, number, number] = [10.38, 45.67, 12.75, 47.1];

	async function setupProtocols(ml: typeof import('maplibre-gl')): Promise<string | undefined> {
		// pmtiles:// per i sentieri; isoipse calcolate nel browser dal DEM (maplibre-contour), con
		// la stessa sorgente che il planner usa per le quote
		const { Protocol } = await import('pmtiles');
		ml.addProtocol('pmtiles', new Protocol().tile);
		const dem = await demSource();
		if (!dem) return undefined;
		dem.setupMaplibre(ml);
		return dem.contourProtocolUrl({
			thresholds: { 11: [100, 500], 12: [50, 250], 13: [25, 100], 14: [20, 100], 15: [10, 50] },
			contourLayer: 'contours',
			elevationKey: 'ele',
			levelKey: 'level'
		});
	}

	function pointsGeoJSON(list: MapPoint[], sel: string | null) {
		return {
			type: 'FeatureCollection' as const,
			features: list.map((p) => ({
				type: 'Feature' as const,
				properties: { id: p.id, k: p.k, sel: p.id === sel ? 1 : 0 },
				geometry: { type: 'Point' as const, coordinates: [p.lon, p.lat] }
			}))
		};
	}

	function lineGeoJSON(coords: [number, number][] | undefined) {
		return {
			type: 'FeatureCollection' as const,
			features: coords?.length
				? [
						{
							type: 'Feature' as const,
							properties: {},
							geometry: { type: 'LineString' as const, coordinates: coords }
						}
					]
				: []
		};
	}

	onMount(async () => {
		try {
			lib = await import('maplibre-gl');
			lib.setWorkerUrl(workerUrl);
			protocolsReady ??= setupProtocols(lib);
			const contourTilesUrl = await protocolsReady;
			const base = await fetch(BASEMAP_STYLE_URL).then((r) => {
				if (!r.ok) throw new Error(`mappa di base: HTTP ${r.status}`);
				return r.json();
			});
			if (destroyed) return;
			const trailsUrl = new URL(generatedAsset('tiles/pilota.pmtiles'), window.location.href).href;
			const style = withCordataLayers(base, { trailsUrl, contourTilesUrl });
			const bounds = bbox ?? PILOT_BOUNDS;
			map = new lib.Map({
				container,
				style,
				bounds,
				fitBoundsOptions: { padding: 32 },
				attributionControl: false,
				maxPitch: 60
			});
			map.addControl(new lib.NavigationControl({ visualizePitch: true }), 'top-right');
			map.addControl(
				new lib.GeolocateControl({
					positionOptions: { enableHighAccuracy: true },
					trackUserLocation: true
				}),
				'top-right'
			);
			map.addControl(new lib.ScaleControl({ unit: 'metric' }), 'bottom-left');
			map.addControl(
				new lib.AttributionControl({
					compact: true,
					customAttribution: `<a href="${resolve('/fonti')}">Fonti e licenze</a>`
				}),
				'bottom-right'
			);
			map.on('load', () => {
				if (!map) return;
				map.addSource('percorso', { type: 'geojson', data: lineGeoJSON(line) });
				map.addLayer(
					{
						id: 'percorso-alone',
						type: 'line',
						source: 'percorso',
						layout: { 'line-cap': 'round', 'line-join': 'round' },
						paint: { 'line-color': '#ffffff', 'line-width': 9, 'line-opacity': 0.9 }
					},
					'sentieri-numeri'
				);
				map.addLayer(
					{
						id: 'percorso',
						type: 'line',
						source: 'percorso',
						// estremità piatte per il tratteggio: quelle arrotondate riempirebbero gli spazi
						layout: { 'line-cap': lineDashed ? 'butt' : 'round', 'line-join': 'round' },
						paint: {
							'line-color': lineColor,
							'line-width': 5,
							...(lineDashed ? { 'line-dasharray': [2, 1.5] } : {})
						}
					},
					'sentieri-numeri'
				);
				map.addSource('proposte', { type: 'geojson', data: pointsGeoJSON(points, selected) });
				map.addLayer({
					id: 'proposte',
					type: 'circle',
					source: 'proposte',
					paint: {
						'circle-radius': ['case', ['==', ['get', 'sel'], 1], 10, 7],
						// un solo colore per le escursioni, diverso da quelli dei sentieri (ADR 0012)
						'circle-color': ESCURSIONE_POINT_COLOR,
						'circle-stroke-color': '#1f2933',
						'circle-stroke-width': ['case', ['==', ['get', 'sel'], 1], 4, 2]
					}
				});
				map.on('click', 'proposte', (e) => {
					const id = e.features?.[0]?.properties?.id;
					if (id && onPointClick) onPointClick(String(id));
				});
				map.on('mouseenter', 'proposte', () => map && (map.getCanvas().style.cursor = 'pointer'));
				map.on('mouseleave', 'proposte', () => map && (map.getCanvas().style.cursor = ''));
				ready = true;
				container.dataset.ready = 'true';
				// attribuzioni compatte: visibili all'apertura, poi si chiudono (restano sul pulsante i)
				// al primo tocco o dopo qualche secondo, per non coprire la mappa sui telefoni
				const collapse = () =>
					container
						?.querySelector('.maplibregl-compact.maplibregl-compact-show')
						?.classList.remove('maplibregl-compact-show');
				map.once('click', collapse);
				collapseTimer = setTimeout(collapse, 6000);
				if (onReady && lib) onReady(map, lib);
			});
			map.on('moveend', (e) => {
				if (!map || !onMoveEnd) return;
				const b = map.getBounds();
				onMoveEnd(
					[b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
					Boolean((e as { originalEvent?: unknown }).originalEvent)
				);
			});
			// il contenitore cambia dimensione con il layout (griglia, pannelli): la mappa si adatta
			resizeObserver = new ResizeObserver(() => map?.resize());
			resizeObserver.observe(container);
			// accesso alla mappa per i test end-to-end (Playwright)
			(container as HTMLDivElement & { maplibreMap?: MlMap }).maplibreMap = map;
			map.on('click', 'sentieri', (e) => {
				if (!onTrailClick || !e.features?.length || !map) return;
				// un clic su una proposta non è anche un clic sul sentiero sotto
				if (
					map.getLayer('proposte') &&
					map.queryRenderedFeatures(e.point, { layers: ['proposte'] }).length
				)
					return;
				const props = e.features.map((f) => f.properties as unknown as TrailWayProps);
				onTrailClick(props, [e.lngLat.lng, e.lngLat.lat]);
			});
			map.on('mouseenter', 'sentieri', () => map && (map.getCanvas().style.cursor = 'pointer'));
			map.on('mouseleave', 'sentieri', () => map && (map.getCanvas().style.cursor = ''));
		} catch (err) {
			failed = err instanceof Error ? err.message : String(err);
		}
	});

	onDestroy(() => {
		destroyed = true;
		clearTimeout(collapseTimer);
		resizeObserver?.disconnect();
		map?.remove();
	});

	// proposte (Esplora)
	$effect(() => {
		const data = pointsGeoJSON(points, selected);
		if (ready && map) (map.getSource('proposte') as GeoJSONSource | undefined)?.setData(data);
	});

	// inquadratura richiesta dalla pagina
	$effect(() => {
		if (ready && map && focus) map.fitBounds(focus, { padding: 40, maxZoom: 14, duration: 600 });
	});

	// traccia evidenziata
	$effect(() => {
		const data = lineGeoJSON(line);
		if (ready && map) (map.getSource('percorso') as GeoJSONSource | undefined)?.setData(data);
	});

	// marker che segue il profilo altimetrico
	$effect(() => {
		if (!ready || !map || !lib) return;
		if (!cursor) {
			cursorMarker?.remove();
			cursorMarker = undefined;
			return;
		}
		if (!cursorMarker) {
			const el = document.createElement('div');
			el.className = 'cursore';
			cursorMarker = new lib.Marker({ element: el }).setLngLat(cursor).addTo(map);
		} else {
			cursorMarker.setLngLat(cursor);
		}
	});

	// punti chiave numerati
	$effect(() => {
		if (!ready || !map || !lib) return;
		for (const m of stageMarkers) m.remove();
		stageMarkers = stages.map((s) => {
			const el = document.createElement('div');
			el.className = 'tappa';
			el.textContent = String(s.n);
			el.title = s.name;
			el.setAttribute('aria-label', `${s.n}. ${s.name}`);
			return new lib!.Marker({ element: el }).setLngLat([s.lon, s.lat]).addTo(map!);
		});
	});
</script>

<div class="map" bind:this={container} role="region" aria-label={label}>
	{#if !failed}<MapLegend parts={legend} />{/if}
	{#if failed}
		<p class="errore">
			La mappa non si è caricata ({failed}). I dati della scheda restano disponibili qui sotto.
		</p>
	{/if}
</div>

<style>
	/* riempie il contenitore, che deve essere posizionato e avere un'altezza */
	.map {
		position: absolute;
		inset: 0;
		background: #e8e4da;
	}
	.errore {
		position: absolute;
		inset: auto 1rem 1rem 1rem;
		margin: 0;
		padding: 0.75rem 1rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 10px;
	}
	.map :global(.cursore) {
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: #ffffff;
		border: 4px solid #1f2933;
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
	}
	.map :global(.tappa) {
		min-width: 22px;
		height: 22px;
		padding: 0 4px;
		box-sizing: border-box;
		border-radius: 11px;
		background: #1f2933;
		color: #ffffff;
		font:
			700 12px/22px system-ui,
			sans-serif;
		text-align: center;
		border: 2px solid #ffffff;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
	}
	.map :global(.maplibregl-ctrl-group button) {
		width: 40px;
		height: 40px;
	}
</style>
