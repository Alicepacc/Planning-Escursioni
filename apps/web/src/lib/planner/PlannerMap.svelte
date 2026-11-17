<script lang="ts">
	// Mappa del planner (SPEC §5.3): tocca per aggiungere un punto, trascina i punti per spostarli,
	// tocca la linea per inserire un punto intermedio. Percorso pieno sui sentieri, tratteggiato a
	// mano libera.
	import { onDestroy } from 'svelte';
	import type { GeoJSONSource, Map as MlMap, MapMouseEvent, Marker as MlMarker } from 'maplibre-gl';
	import MapView from '../map/MapView.svelte';
	import type { PlannedLeg } from './engine';
	import { isLoop, type Plan } from './plan';

	interface Props {
		plan: Plan;
		legs: PlannedLeg[];
		selected: number | null;
		cursor?: [number, number] | null;
		focus?: [number, number, number, number] | null;
		onAdd: (lon: number, lat: number, metersPerPixel: number) => void;
		onInsert: (leg: number, lon: number, lat: number) => void;
		onMove: (i: number, lon: number, lat: number, metersPerPixel: number) => void;
		onSelect: (i: number | null) => void;
		onRemove: (i: number) => void;
	}

	let {
		plan,
		legs,
		selected,
		cursor = null,
		focus = null,
		onAdd,
		onInsert,
		onMove,
		onSelect,
		onRemove
	}: Props = $props();

	const ROUTE = '#174ea6';
	const FREE = '#a85200';
	const LINE_LAYERS = ['piano-pieno', 'piano-libero'];

	let map = $state<MlMap | undefined>();
	let lib: typeof import('maplibre-gl') | undefined;
	let markers: MlMarker[] = [];

	/** metri per pixel allo zoom e alla latitudine dati (tasselli da 512 px) */
	function metersPerPixel(m: MlMap, lat: number): number {
		return (40075016.686 * Math.cos((lat * Math.PI) / 180)) / (512 * 2 ** m.getZoom());
	}

	/** centro della mappa, per aggiungere un punto senza toccare la mappa (tastiera) */
	export function center(): { lon: number; lat: number; mpp: number } | null {
		if (!map) return null;
		const c = map.getCenter();
		return { lon: c.lng, lat: c.lat, mpp: metersPerPixel(map, c.lat) };
	}

	function legsGeoJSON(list: PlannedLeg[]) {
		return {
			type: 'FeatureCollection' as const,
			features: list.flatMap((leg, i) =>
				leg.pieces
					.filter((p) => p.points.length > 1)
					.map((p) => ({
						type: 'Feature' as const,
						properties: { leg: i, free: p.free ? 1 : 0 },
						geometry: {
							type: 'LineString' as const,
							coordinates: p.points.map(([lon, lat]) => [lon, lat])
						}
					}))
			)
		};
	}

	function setup(m: MlMap, ml: typeof import('maplibre-gl')) {
		lib = ml;
		m.addSource('piano', { type: 'geojson', data: legsGeoJSON(legs) });
		const before = m.getLayer('sentieri-numeri') ? 'sentieri-numeri' : undefined;
		m.addLayer(
			{
				id: 'piano-alone',
				type: 'line',
				source: 'piano',
				layout: { 'line-cap': 'round', 'line-join': 'round' },
				paint: { 'line-color': '#ffffff', 'line-width': 9, 'line-opacity': 0.9 }
			},
			before
		);
		m.addLayer(
			{
				id: 'piano-pieno',
				type: 'line',
				source: 'piano',
				filter: ['==', ['get', 'free'], 0],
				layout: { 'line-cap': 'round', 'line-join': 'round' },
				paint: { 'line-color': ROUTE, 'line-width': 5 }
			},
			before
		);
		m.addLayer(
			{
				id: 'piano-libero',
				type: 'line',
				source: 'piano',
				filter: ['==', ['get', 'free'], 1],
				// estremità piatte: con quelle arrotondate il tratteggio sparirebbe
				layout: { 'line-cap': 'butt', 'line-join': 'round' },
				paint: { 'line-color': FREE, 'line-width': 4.5, 'line-dasharray': [2, 1.4] }
			},
			before
		);
		m.on('click', (e: MapMouseEvent) => {
			const target = e.originalEvent?.target as HTMLElement | null;
			if (target?.closest?.('.wp')) return;
			const { x, y } = e.point;
			const hit = m.queryRenderedFeatures(
				[
					[x - 10, y - 10],
					[x + 10, y + 10]
				],
				{ layers: LINE_LAYERS }
			);
			if (hit.length) {
				onInsert(Number(hit[0].properties?.leg), e.lngLat.lng, e.lngLat.lat);
				return;
			}
			onAdd(e.lngLat.lng, e.lngLat.lat, metersPerPixel(m, e.lngLat.lat));
		});
		for (const id of LINE_LAYERS) {
			m.on('mouseenter', id, () => (m.getCanvas().style.cursor = 'copy'));
			m.on('mouseleave', id, () => (m.getCanvas().style.cursor = ''));
		}
		m.getCanvas().style.cursor = 'crosshair';
		map = m;
	}

	// percorso
	$effect(() => {
		const data = legsGeoJSON(legs);
		if (map) (map.getSource('piano') as GeoJSONSource | undefined)?.setData(data);
	});

	// punti: pulsanti trascinabili, numerati; in un anello partenza e arrivo sono lo stesso punto
	$effect(() => {
		const m = map;
		const points = plan.points;
		const loop = isLoop(plan);
		const sel = selected;
		if (!m || !lib) return;
		const ml = lib;
		for (const mk of markers) mk.remove();
		const n = points.length;
		markers = points.flatMap((p, i) => {
			if (loop && i === n - 1) return [];
			const el = document.createElement('button');
			el.type = 'button';
			const role = i === 0 ? 'inizio' : i === n - 1 ? 'fine' : '';
			el.className = `wp ${role} ${i === sel ? 'sel' : ''} ${loop && i === 0 ? 'anello' : ''}`;
			el.textContent = String(i + 1);
			const what =
				i === 0 ? (loop ? 'partenza e arrivo' : 'partenza') : i === n - 1 ? 'arrivo' : '';
			el.setAttribute(
				'aria-label',
				`Punto ${i + 1}${what ? ` (${what})` : ''}: trascina per spostarlo, Canc per eliminarlo`
			);
			const mk = new ml.Marker({ element: el, draggable: true }).setLngLat([p.lon, p.lat]).addTo(m);
			let dragged = false;
			mk.on('dragstart', () => (dragged = true));
			mk.on('dragend', () => {
				const ll = mk.getLngLat();
				onMove(i, ll.lng, ll.lat, metersPerPixel(m, ll.lat));
				setTimeout(() => (dragged = false), 0);
			});
			el.addEventListener('click', (ev) => {
				ev.stopPropagation();
				if (!dragged) onSelect(i === sel ? null : i);
			});
			el.addEventListener('keydown', (ev) => {
				if (ev.key === 'Delete' || ev.key === 'Backspace') {
					ev.preventDefault();
					onRemove(i);
				}
			});
			return [mk];
		});
	});

	onDestroy(() => {
		for (const mk of markers) mk.remove();
	});
</script>

<MapView label="Mappa del planner" {cursor} {focus} onReady={setup} />

<style>
	:global(.wp) {
		width: 28px;
		height: 28px;
		padding: 0;
		border-radius: 50%;
		border: 3px solid #ffffff;
		background: #174ea6;
		color: #ffffff;
		font:
			700 12px/22px system-ui,
			sans-serif;
		text-align: center;
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.45);
		cursor: grab;
		touch-action: none;
	}
	:global(.wp.inizio) {
		background: #1f7a3f;
	}
	:global(.wp.fine) {
		background: #1f2933;
	}
	:global(.wp.anello) {
		box-shadow:
			0 0 0 3px #1f2933,
			0 1px 4px rgba(0, 0, 0, 0.45);
	}
	:global(.wp.sel) {
		outline: 3px solid #f2b705;
		outline-offset: 1px;
	}
	:global(.wp:focus-visible) {
		outline: 3px solid #f2b705;
		outline-offset: 2px;
	}
</style>
