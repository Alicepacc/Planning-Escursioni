// Quote dal modello del terreno nel browser: gli stessi tasselli Mapterhorn (Terrarium, z12) del
// rilievo e delle isoipse, decodificati da maplibre-contour con la sua cache. Servono per i tratti
// a mano libera e per le tracce importate, che non hanno quote dal grafo dei sentieri.

import { TERRAIN_MAXZOOM, TERRAIN_TILES } from './style';

type Contour = typeof import('maplibre-contour').default;
export type DemSource = InstanceType<Contour['DemSource']>;

let source: Promise<DemSource | null> | undefined;

/** Unica sorgente DEM della pagina, condivisa da mappa (isoipse) e planner. */
export function demSource(): Promise<DemSource | null> {
	source ??= import('maplibre-contour')
		.then(
			(m) =>
				new m.default.DemSource({
					url: TERRAIN_TILES,
					encoding: 'terrarium',
					maxzoom: TERRAIN_MAXZOOM,
					worker: true,
					cacheSize: 120
				})
		)
		.catch((err) => {
			console.warn('modello del terreno non disponibile', err);
			return null;
		});
	return source;
}

/** Posizione nel tassello z/x/y: indici del tassello e coordinate frazionarie. */
export function tileCoords(lon: number, lat: number, z: number) {
	const n = 2 ** z;
	const xf = ((lon + 180) / 360) * n;
	const r = (lat * Math.PI) / 180;
	const yf = ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n;
	return {
		tx: Math.floor(xf),
		ty: Math.floor(yf),
		fx: xf - Math.floor(xf),
		fy: yf - Math.floor(yf)
	};
}

/** Interpolazione bilineare tra i centri dei pixel (bordi del tassello bloccati). */
export function bilinear(
	tile: { width: number; height: number; data: ArrayLike<number> },
	fx: number,
	fy: number
): number {
	const u = fx * tile.width - 0.5;
	const v = fy * tile.height - 0.5;
	const clampX = (i: number) => Math.max(0, Math.min(tile.width - 1, i));
	const clampY = (i: number) => Math.max(0, Math.min(tile.height - 1, i));
	const x0 = Math.floor(u);
	const y0 = Math.floor(v);
	const tu = u - x0;
	const tv = v - y0;
	const at = (x: number, y: number) => tile.data[clampY(y) * tile.width + clampX(x)];
	const top = at(x0, y0) * (1 - tu) + at(x0 + 1, y0) * tu;
	const bottom = at(x0, y0 + 1) * (1 - tu) + at(x0 + 1, y0 + 1) * tu;
	return top * (1 - tv) + bottom * tv;
}

/** Quote dei punti [lon, lat]; null dove il tassello non si carica. */
export async function elevations(points: [number, number][]): Promise<(number | null)[]> {
	const dem = await demSource();
	if (!dem) return points.map(() => null);
	const z = TERRAIN_MAXZOOM;
	const tiles = new Map<
		string,
		Promise<{ width: number; height: number; data: Float32Array } | null>
	>();
	return Promise.all(
		points.map(async ([lon, lat]) => {
			const { tx, ty, fx, fy } = tileCoords(lon, lat, z);
			const key = `${tx}/${ty}`;
			let tile = tiles.get(key);
			if (!tile) {
				tile = dem.getDemTile(z, tx, ty).catch(() => null);
				tiles.set(key, tile);
			}
			const t = await tile;
			return t ? bilinear(t, fx, fy) : null;
		})
	);
}
