// Stile della mappa: base OpenFreeMap + rilievo Mapterhorn + sentieri e POI di Cordata.
// Tutti i servizi sono gratuiti e senza chiavi (ADR 0005); attribuzioni in /fonti.
import type {
	AddLayerObject,
	DataDrivenPropertyValueSpecification,
	ExpressionSpecification,
	StyleSpecification
} from 'maplibre-gl';
import { CAI_SCALES } from '../hiking/difficulty';

export const BASEMAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty';
export const TERRAIN_TILES = 'https://tiles.mapterhorn.com/{z}/{x}/{y}.webp';
export const TERRAIN_MAXZOOM = 12; // disponibile ovunque; i livelli superiori solo in parte
export const TRAILS_SOURCE = 'cordata';
export const TRAIL_LAYERS = ['sentieri'];
export const FONT_REGULAR = ['Noto Sans Regular'];
export const FONT_BOLD = ['Noto Sans Bold'];

export const scaleColor: ExpressionSpecification = [
	'match',
	['get', 'scale'],
	'T',
	CAI_SCALES.T.color,
	'E',
	CAI_SCALES.E.color,
	'EE',
	CAI_SCALES.EE.color,
	'EEA',
	CAI_SCALES.EEA.color,
	'#8a5a44'
];

const POI_COLORS: Record<string, string> = {
	rifugio: '#b5651d',
	bivacco: '#b5651d',
	riparo: '#b5651d',
	cima: '#5b4636',
	sella: '#5b4636',
	lago: '#1f6fb2',
	sorgente: '#1f6fb2',
	acqua_potabile: '#1f6fb2',
	cascata: '#1f6fb2',
	parcheggio: '#3b5b8c',
	panorama: '#2f7a4f',
	palina: '#c0392b',
	localita: '#555'
};

const poiColor: DataDrivenPropertyValueSpecification<string> = [
	'match',
	['get', 'kind'],
	...Object.entries(POI_COLORS).flat(),
	'#555'
] as unknown as DataDrivenPropertyValueSpecification<string>;

/** Primo layer della base con cui inserire sotto i nostri elementi (strade o etichette). */
function firstLayerId(style: StyleSpecification, predicate: (l: AddLayerObject) => boolean) {
	return style.layers.find((l) => predicate(l as AddLayerObject))?.id;
}

export interface CordataStyleOptions {
	trailsUrl: string;
	contourTilesUrl?: string;
}

/** Aggiunge allo stile di base le sorgenti e i layer di Cordata, nell'ordine giusto. */
export function withCordataLayers(base: StyleSpecification, opts: CordataStyleOptions) {
	const style: StyleSpecification = structuredClone(base);
	style.sources.terrain = {
		type: 'raster-dem',
		tiles: [TERRAIN_TILES],
		tileSize: 512,
		encoding: 'terrarium',
		maxzoom: TERRAIN_MAXZOOM,
		attribution: '<a href="https://mapterhorn.com/attribution">© Mapterhorn</a>'
	};
	style.sources[TRAILS_SOURCE] = {
		type: 'vector',
		url: `pmtiles://${opts.trailsUrl}`,
		attribution:
			'<a href="https://infomont.cai.it">© CAI INFOMONT</a> · <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap</a> (ODbL)'
	};
	if (opts.contourTilesUrl) {
		style.sources.contours = { type: 'vector', tiles: [opts.contourTilesUrl], maxzoom: 15 };
	}

	const beforeRoads = firstLayerId(
		style,
		(l) =>
			'source-layer' in l &&
			(l['source-layer'] === 'transportation' || l['source-layer'] === 'building')
	);
	const beforeLabels = firstLayerId(style, (l) => l.type === 'symbol');

	const relief: AddLayerObject[] = [
		{
			id: 'rilievo',
			type: 'hillshade',
			source: 'terrain',
			paint: {
				'hillshade-exaggeration': 0.35,
				'hillshade-shadow-color': '#3d3527',
				'hillshade-highlight-color': '#ffffff'
			}
		}
	];
	if (opts.contourTilesUrl) {
		relief.push(
			{
				id: 'isoipse',
				type: 'line',
				source: 'contours',
				'source-layer': 'contours',
				minzoom: 11,
				paint: {
					'line-color': 'rgba(120, 85, 45, 0.55)',
					'line-width': ['match', ['get', 'level'], 1, 0.9, 0.45]
				}
			},
			{
				id: 'isoipse-quote',
				type: 'symbol',
				source: 'contours',
				'source-layer': 'contours',
				minzoom: 13,
				filter: ['>', ['get', 'level'], 0],
				layout: {
					'symbol-placement': 'line',
					'text-field': ['concat', ['number-format', ['get', 'ele'], {}], ' m'],
					'text-font': FONT_REGULAR,
					'text-size': 10
				},
				paint: {
					'text-color': 'rgb(120, 85, 45)',
					'text-halo-color': 'rgba(255,255,255,0.85)',
					'text-halo-width': 1.2
				}
			}
		);
	}

	const trails: AddLayerObject[] = [
		{
			id: 'sentieri-alone',
			type: 'line',
			source: TRAILS_SOURCE,
			'source-layer': 'sentieri',
			layout: { 'line-cap': 'round', 'line-join': 'round' },
			paint: {
				'line-color': '#ffffff',
				'line-opacity': 0.85,
				'line-width': ['interpolate', ['linear'], ['zoom'], 9, 2, 13, 5, 16, 8]
			}
		},
		{
			id: 'sentieri',
			type: 'line',
			source: TRAILS_SOURCE,
			'source-layer': 'sentieri',
			layout: { 'line-cap': 'round', 'line-join': 'round' },
			paint: {
				'line-color': scaleColor,
				'line-width': ['interpolate', ['linear'], ['zoom'], 9, 1, 13, 2.6, 16, 4.5],
				// tratti con difficoltà stimata da sac_scale (non dichiarata): tratteggio
				'line-dasharray': [
					'case',
					['get', 'scale_derived'],
					['literal', [2, 1.5]],
					['literal', [1, 0]]
				]
			}
		}
	];

	const labels: AddLayerObject[] = [
		{
			id: 'sentieri-numeri',
			type: 'symbol',
			source: TRAILS_SOURCE,
			'source-layer': 'sentieri',
			minzoom: 12,
			filter: ['!=', ['get', 'refs'], ''],
			layout: {
				'symbol-placement': 'line',
				'symbol-spacing': 350,
				'text-field': ['get', 'refs'],
				'text-font': FONT_BOLD,
				'text-size': ['interpolate', ['linear'], ['zoom'], 12, 11, 16, 14],
				'text-max-angle': 30
			},
			paint: { 'text-color': scaleColor, 'text-halo-color': '#ffffff', 'text-halo-width': 2 }
		},
		{
			id: 'poi-punti',
			type: 'circle',
			source: TRAILS_SOURCE,
			'source-layer': 'poi',
			filter: ['!=', ['get', 'kind'], 'localita'],
			paint: {
				'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 2.5, 15, 5],
				'circle-color': poiColor,
				'circle-stroke-color': '#ffffff',
				'circle-stroke-width': 1.2
			}
		},
		{
			id: 'poi-nomi',
			type: 'symbol',
			source: TRAILS_SOURCE,
			'source-layer': 'poi',
			minzoom: 12,
			filter: ['all', ['!=', ['get', 'name'], ''], ['!=', ['get', 'kind'], 'localita']],
			layout: {
				'text-field': [
					'case',
					['has', 'ele'],
					[
						'format',
						['get', 'name'],
						{},
						'\n',
						{},
						['concat', ['to-string', ['get', 'ele']], ' m'],
						{ 'font-scale': 0.85 }
					],
					['get', 'name']
				],
				'text-font': FONT_REGULAR,
				'text-size': ['match', ['get', 'kind'], ['rifugio', 'cima'], 13, 11.5],
				'text-offset': [0, 0.6],
				'text-anchor': 'top',
				'text-max-width': 9,
				'symbol-sort-key': ['match', ['get', 'kind'], 'cima', 1, 'rifugio', 2, 'lago', 3, 10]
			},
			paint: { 'text-color': '#2b2b2b', 'text-halo-color': '#ffffff', 'text-halo-width': 1.6 }
		}
	];

	const insertAt = (layers: AddLayerObject[], beforeId: string | undefined) => {
		const index = beforeId ? style.layers.findIndex((l) => l.id === beforeId) : style.layers.length;
		style.layers.splice(
			index < 0 ? style.layers.length : index,
			0,
			...(layers as typeof style.layers)
		);
	};
	insertAt(relief, beforeRoads);
	insertAt(trails, beforeLabels);
	insertAt(labels, undefined);
	return style;
}
