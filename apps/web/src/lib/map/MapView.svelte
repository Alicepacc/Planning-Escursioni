<script module lang="ts">
	// condiviso tra tutte le mappe della pagina: i protocolli si registrano una volta sola
	let protocolsReady: Promise<string | undefined> | undefined;
</script>

<script lang="ts">
	// Mappa MapLibre: base OpenFreeMap, rilievo e isoipse da Mapterhorn, sentieri CAI (PMTiles).
	import { onDestroy, onMount } from 'svelte';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import type { GeoJSONSource, Map as MlMap, Marker as MlMarker } from 'maplibre-gl';
	import { generatedAsset } from '../data/paths';
	// MapLibre 6 (ESM) carica il worker relativo a sé stesso: con Vite va dichiarato come asset
	import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
	import type { TrailWayProps } from '../data/types';
	import { BASEMAP_STYLE_URL, TERRAIN_MAXZOOM, TERRAIN_TILES, withCordataLayers } from './style';

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
		cursor?: [number, number] | null;
		stages?: StageMarker[];
		label?: string;
		onTrailClick?: (ways: TrailWayProps[], lngLat: [number, number]) => void;
	}

	let {
		bbox,
		line,
		lineColor = '#c0392b',
		cursor = null,
		stages = [],
		label = 'Mappa dei sentieri',
		onTrailClick
	}: Props = $props();

	let container: HTMLDivElement;
	let map: MlMap | undefined;
	let ready = $state(false);
	let failed = $state<string | null>(null);
	let cursorMarker: MlMarker | undefined;
	let stageMarkers: MlMarker[] = [];
	let lib: typeof import('maplibre-gl') | undefined;

	const PILOT_BOUNDS: [number, number, number, number] = [10.38, 45.67, 12.75, 47.1];

	async function setupProtocols(ml: typeof import('maplibre-gl')): Promise<string | undefined> {
		// pmtiles:// per i sentieri; isoipse calcolate nel browser dal DEM (maplibre-contour)
		const { Protocol } = await import('pmtiles');
		ml.addProtocol('pmtiles', new Protocol().tile);
		try {
			const mlcontour = (await import('maplibre-contour')).default;
			const dem = new mlcontour.DemSource({
				url: TERRAIN_TILES,
				encoding: 'terrarium',
				maxzoom: TERRAIN_MAXZOOM,
				worker: true
			});
			dem.setupMaplibre(ml);
			return dem.contourProtocolUrl({
				thresholds: { 11: [100, 500], 12: [50, 250], 13: [25, 100], 14: [20, 100], 15: [10, 50] },
				contourLayer: 'contours',
				elevationKey: 'ele',
				levelKey: 'level'
			});
		} catch (err) {
			console.warn('isoipse non disponibili', err);
			return undefined;
		}
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
					customAttribution: '<a href="/fonti">Fonti e licenze</a>'
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
						layout: { 'line-cap': 'round', 'line-join': 'round' },
						paint: { 'line-color': lineColor, 'line-width': 5 }
					},
					'sentieri-numeri'
				);
				ready = true;
				container.dataset.ready = 'true';
			});
			// accesso alla mappa per i test end-to-end (Playwright)
			(container as HTMLDivElement & { maplibreMap?: MlMap }).maplibreMap = map;
			map.on('click', 'sentieri', (e) => {
				if (!onTrailClick || !e.features?.length) return;
				const props = e.features.map((f) => f.properties as unknown as TrailWayProps);
				onTrailClick(props, [e.lngLat.lng, e.lngLat.lat]);
			});
			map.on('mouseenter', 'sentieri', () => map && (map.getCanvas().style.cursor = 'pointer'));
			map.on('mouseleave', 'sentieri', () => map && (map.getCanvas().style.cursor = ''));
		} catch (err) {
			failed = err instanceof Error ? err.message : String(err);
		}
	});

	onDestroy(() => map?.remove());

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
