// Grafo pedonale a tasselli (ADR 0010), prodotto da services/ingest/src/cordata_ingest/build/graph.py.
// Il browser carica solo i tasselli attorno ai punti del percorso.

export const DIFF_LABELS = ['T', 'E', 'EE', 'EEA'] as const;
export const F_MARKED = 1;
export const F_LOW_VIS = 2;
export const F_ISSUE = 4;
export const F_STEPS = 8;
export const F_FERRATA = 16;

export type BBox = [number, number, number, number];

export interface GraphIndex {
	schema: number;
	tile: [number, number];
	scale: number;
	tiles: string[];
	attribution: string;
}

/** Tassello così com'è nel file JSON (nomi corti per la dimensione). */
export interface RawTile {
	n: [number, number, number, number][];
	e: [number, number, number, number, number, number, number, number, number, number[]][];
	r: string[];
	p: [string, number, number, number | null, string][];
}

export interface GNode {
	id: number;
	lon: number;
	lat: number;
	ele: number;
}

export interface GEdge {
	id: number;
	a: number;
	b: number;
	len: number;
	up: number;
	down: number;
	diff: number;
	cls: number;
	flags: number;
	ref: string;
	/** punti intermedi da a verso b: [lon, lat, quota] */
	shape: [number, number, number][];
}

export interface Poi {
	kind: string;
	lon: number;
	lat: number;
	ele: number | null;
	name: string;
}

const BUCKET = 0.01; // gradi: celle dell'indice per l'aggancio

export function haversineM(lon1: number, lat1: number, lon2: number, lat2: number): number {
	const r = Math.PI / 180;
	const dLat = (lat2 - lat1) * r;
	const dLon = (lon2 - lon1) * r;
	const h =
		Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dLon / 2) ** 2;
	return 2 * 6371000 * Math.asin(Math.sqrt(h));
}

export class TrailGraph {
	readonly nodes = new Map<number, GNode>();
	readonly edges: GEdge[] = [];
	readonly adj = new Map<number, number[]>();
	readonly pois: Poi[] = [];
	readonly loaded = new Set<string>();
	private readonly buckets = new Map<string, number[]>();

	constructor(readonly index: GraphIndex) {}

	/** Chiavi dei tasselli esistenti che toccano il riquadro. */
	tilesFor(bbox: BBox): string[] {
		const [dx, dy] = this.index.tile;
		const out: string[] = [];
		const have = new Set(this.index.tiles);
		for (let ix = Math.floor(bbox[0] / dx); ix <= Math.floor(bbox[2] / dx); ix++)
			for (let iy = Math.floor(bbox[1] / dy); iy <= Math.floor(bbox[3] / dy); iy++) {
				const key = `${ix}_${iy}`;
				if (have.has(key)) out.push(key);
			}
		return out;
	}

	addTile(key: string, raw: RawTile): void {
		if (this.loaded.has(key)) return;
		this.loaded.add(key);
		const s = this.index.scale;
		for (const [id, x, y, ele] of raw.n)
			if (!this.nodes.has(id)) this.nodes.set(id, { id, lon: x / s, lat: y / s, ele });
		for (const [a, b, len, up, down, diff, cls, flags, rid, deltas] of raw.e) {
			const na = this.nodes.get(a)!;
			const shape: [number, number, number][] = [];
			let px = Math.round(na.lon * s);
			let py = Math.round(na.lat * s);
			for (let i = 0; i + 2 < deltas.length; i += 3) {
				px += deltas[i];
				py += deltas[i + 1];
				shape.push([px / s, py / s, deltas[i + 2]]);
			}
			const edge: GEdge = {
				id: this.edges.length,
				a,
				b,
				len,
				up,
				down,
				diff,
				cls,
				flags,
				ref: rid >= 0 ? raw.r[rid] : '',
				shape
			};
			this.edges.push(edge);
			for (const n of [a, b]) {
				const list = this.adj.get(n);
				if (list) list.push(edge.id);
				else this.adj.set(n, [edge.id]);
			}
			this.indexEdge(edge);
		}
		for (const [kind, x, y, ele, name] of raw.p)
			this.pois.push({ kind, lon: x / s, lat: y / s, ele, name });
	}

	/** Coordinate dell'arco da a verso b, estremi compresi: [lon, lat, quota]. */
	coords(edge: GEdge): [number, number, number][] {
		const a = this.nodes.get(edge.a)!;
		const b = this.nodes.get(edge.b)!;
		return [[a.lon, a.lat, a.ele], ...edge.shape, [b.lon, b.lat, b.ele]];
	}

	private indexEdge(edge: GEdge): void {
		const pts = this.coords(edge);
		let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
		for (const [x, y] of pts) {
			x0 = Math.min(x0, x);
			y0 = Math.min(y0, y);
			x1 = Math.max(x1, x);
			y1 = Math.max(y1, y);
		}
		for (let gx = Math.floor(x0 / BUCKET); gx <= Math.floor(x1 / BUCKET); gx++)
			for (let gy = Math.floor(y0 / BUCKET); gy <= Math.floor(y1 / BUCKET); gy++) {
				const key = `${gx}_${gy}`;
				const list = this.buckets.get(key);
				if (list) list.push(edge.id);
				else this.buckets.set(key, [edge.id]);
			}
	}

	/** Archi nelle celle attorno al punto (candidati per l'aggancio). */
	edgesNear(lon: number, lat: number, rings = 1): number[] {
		const gx = Math.floor(lon / BUCKET);
		const gy = Math.floor(lat / BUCKET);
		const out = new Set<number>();
		for (let x = gx - rings; x <= gx + rings; x++)
			for (let y = gy - rings; y <= gy + rings; y++)
				for (const id of this.buckets.get(`${x}_${y}`) ?? []) out.add(id);
		return [...out];
	}
}

/** Carica i tasselli che toccano il riquadro (allargato di `marginKm`). */
export async function loadArea(
	graph: TrailGraph,
	bbox: BBox,
	fetchTile: (key: string) => Promise<RawTile>,
	marginKm = 2
): Promise<number> {
	const dLat = marginKm / 111;
	const dLon = marginKm / (111 * Math.cos((((bbox[1] + bbox[3]) / 2) * Math.PI) / 180));
	const keys = graph
		.tilesFor([bbox[0] - dLon, bbox[1] - dLat, bbox[2] + dLon, bbox[3] + dLat])
		.filter((k) => !graph.loaded.has(k));
	const tiles = await Promise.all(keys.map(async (k) => [k, await fetchTile(k)] as const));
	for (const [k, raw] of tiles) graph.addTile(k, raw);
	return keys.length;
}

export interface Snap {
	edge: GEdge;
	/** metri dall'inizio dell'arco (nodo a) al punto agganciato */
	pos: number;
	lon: number;
	lat: number;
	ele: number;
	dist: number;
}

/** Aggancia un punto all'arco percorribile più vicino entro `maxM` metri. */
export function snap(
	graph: TrailGraph,
	lon: number,
	lat: number,
	maxDiff = 3,
	maxM = 400
): Snap | null {
	const kx = 111320 * Math.cos((lat * Math.PI) / 180);
	const ky = 110950;
	let best: Snap | null = null;
	for (const id of graph.edgesNear(lon, lat, 1)) {
		const edge = graph.edges[id];
		if (edge.diff > maxDiff) continue;
		const pts = graph.coords(edge);
		let along = 0;
		for (let i = 0; i + 1 < pts.length; i++) {
			const [x1, y1, z1] = pts[i];
			const [x2, y2, z2] = pts[i + 1];
			const ax = (x1 - lon) * kx;
			const ay = (y1 - lat) * ky;
			const bx = (x2 - lon) * kx;
			const by = (y2 - lat) * ky;
			const dx = bx - ax;
			const dy = by - ay;
			const segLen = Math.hypot(dx, dy);
			const t = segLen > 0 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / (segLen * segLen))) : 0;
			const px = ax + dx * t;
			const py = ay + dy * t;
			const dist = Math.hypot(px, py);
			if (dist <= maxM && (!best || dist < best.dist)) {
				best = {
					edge,
					pos: along + segLen * t,
					lon: x1 + (x2 - x1) * t,
					lat: y1 + (y2 - y1) * t,
					ele: z1 + (z2 - z1) * t,
					dist
				};
			}
			along += segLen;
		}
	}
	return best;
}
