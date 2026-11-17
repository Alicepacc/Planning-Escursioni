// Motore del planner: dai punti del piano ai tratti del percorso, con il router nel browser
// (ADR 0010). I tasselli del grafo si scaricano una volta sola; i tratti già calcolati restano in
// cache, così spostare un punto ricalcola solo i due tratti vicini.

import {
	TrailGraph,
	haversineM,
	snap,
	type BBox,
	type GraphIndex,
	type RawTile
} from '../routing/graph';
import { poisAlong, type PoiAlong } from '../routing/pois';
import { routeBetween, type Leg, type RoutePoint } from '../routing/router';
import type { LegMode, Plan, PlanPoint } from './plan';

/** Pezzo da disegnare: sul sentiero o a mano libera (tratteggiato). */
export interface Piece {
	points: RoutePoint[];
	free: boolean;
}

export interface PlannedLeg extends Leg {
	pieces: Piece[];
	/** il tratto doveva seguire i sentieri ma è a mano libera: perché */
	fallback?: 'lontano' | 'nessun_percorso' | 'grafo';
	/** quote non disponibili (né modello del terreno né grafo) */
	noEle?: boolean;
}

export interface EngineDeps {
	/** file del grafo: 'index.json' o '<ix>_<iy>.json' */
	fetchJson: (name: string) => Promise<unknown>;
	/** quote dal modello del terreno; null dove mancano */
	elevations?: (points: [number, number][]) => Promise<(number | null)[]>;
}

export const SNAP_M = 250; // raggio di aggancio dei punti del piano ai sentieri
const CONNECT_M = 15; // oltre questa distanza dal sentiero si disegna un raccordo a mano libera
const FREE_STEP_M = 25; // passo dei campioni di quota nei tratti a mano libera
const MARGIN_KM = 2;
const RETRY_MARGIN_KM = 6;
const CACHE_MAX = 300;

const round5 = (v: number) => Math.round(v * 1e5) / 1e5;
const key5 = (p: PlanPoint) => `${round5(p.lon)},${round5(p.lat)}`;

export function bboxOf(points: { lon: number; lat: number }[]): BBox {
	const lons = points.map((p) => p.lon);
	const lats = points.map((p) => p.lat);
	return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
}

export class PlannerEngine {
	graph: TrailGraph | null = null;
	private index?: Promise<TrailGraph | null>;
	private readonly tiles = new Map<string, Promise<void>>();
	private readonly cache = new Map<string, Promise<PlannedLeg>>();

	constructor(private readonly deps: EngineDeps) {}

	/** Indice del grafo (null se non disponibile: il planner resta a mano libera). */
	load(): Promise<TrailGraph | null> {
		this.index ??= this.deps
			.fetchJson('index.json')
			.then((ix) => (this.graph = new TrailGraph(ix as GraphIndex)))
			.catch(() => null);
		return this.index;
	}

	/** Carica i tasselli del riquadro allargato di `marginKm`; ogni tassello una volta sola. */
	async area(bbox: BBox, marginKm = MARGIN_KM): Promise<TrailGraph | null> {
		const g = await this.load();
		if (!g) return null;
		const dLat = marginKm / 111;
		const dLon = marginKm / (111 * Math.cos((((bbox[1] + bbox[3]) / 2) * Math.PI) / 180));
		const keys = g.tilesFor([bbox[0] - dLon, bbox[1] - dLat, bbox[2] + dLon, bbox[3] + dLat]);
		await Promise.all(
			keys.map((k) => {
				let job = this.tiles.get(k);
				if (!job) {
					job = this.deps
						.fetchJson(`${k}.json`)
						.then((raw) => g.addTile(k, raw as RawTile))
						.catch(() => {
							this.tiles.delete(k); // riprova alla prossima occasione
						});
					this.tiles.set(k, job);
				}
				return job;
			})
		);
		return g;
	}

	/** Il punto è nell'area coperta dal grafo dei sentieri? */
	async covers(p: PlanPoint): Promise<boolean> {
		const g = await this.load();
		return !!g && g.tilesFor([p.lon, p.lat, p.lon, p.lat]).length > 0;
	}

	/** Aggancia un punto toccato al sentiero ammesso più vicino entro `maxM` metri. */
	async snapPoint(
		p: PlanPoint,
		maxDiff: number,
		maxM = SNAP_M
	): Promise<{ lon: number; lat: number; ele: number; dist: number } | null> {
		const g = await this.area([p.lon, p.lat, p.lon, p.lat], 1);
		if (!g) return null;
		const s = snap(g, p.lon, p.lat, maxDiff, maxM);
		return s ? { lon: round5(s.lon), lat: round5(s.lat), ele: s.ele, dist: s.dist } : null;
	}

	/** Tratti del piano, nell'ordine; quelli già calcolati arrivano dalla cache. */
	legs(plan: Plan): Promise<PlannedLeg[]> {
		return Promise.all(
			plan.modes.map((mode, i) =>
				this.leg(plan.points[i], plan.points[i + 1], mode, plan.shapes[i], plan.maxDiff)
			)
		);
	}

	leg(
		a: PlanPoint,
		b: PlanPoint,
		mode: LegMode,
		shape: PlanPoint[] | null,
		maxDiff: number
	): Promise<PlannedLeg> {
		const key =
			mode === 'f'
				? `f|${key5(a)}|${key5(b)}|${(shape ?? []).map(key5).join(';')}`
				: `r|${key5(a)}|${key5(b)}|${maxDiff}`;
		let job = this.cache.get(key);
		if (!job) {
			job = mode === 'f' ? this.freehand([a, ...(shape ?? []), b]) : this.routed(a, b, maxDiff);
			this.cache.set(key, job);
			if (this.cache.size > CACHE_MAX) this.cache.delete(this.cache.keys().next().value!);
		} else {
			// usato di recente: in fondo alla coda
			this.cache.delete(key);
			this.cache.set(key, job);
		}
		return job;
	}

	/** Luoghi del grafo (cime, laghi, rifugi…) entro `maxM` metri dal percorso. */
	poisAlong(points: RoutePoint[], maxM = 120): PoiAlong[] {
		return this.graph ? poisAlong(this.graph, points, maxM) : [];
	}

	private async routed(a: PlanPoint, b: PlanPoint, maxDiff: number): Promise<PlannedLeg> {
		const box = bboxOf([a, b]);
		const g = await this.area(box);
		if (!g) return { ...(await this.freehand([a, b])), fallback: 'grafo' };
		const sa = snap(g, a.lon, a.lat, maxDiff, SNAP_M);
		const sb = snap(g, b.lon, b.lat, maxDiff, SNAP_M);
		if (!sa || !sb) return { ...(await this.freehand([a, b])), fallback: 'lontano' };
		let leg = routeBetween(g, sa, sb, { maxDiff });
		if (!leg) {
			await this.area(box, RETRY_MARGIN_KM);
			leg = routeBetween(g, sa, sb, { maxDiff });
		}
		if (!leg) return { ...(await this.freehand([a, b])), fallback: 'nessun_percorso' };

		const out: PlannedLeg = {
			...leg,
			points: [...leg.points],
			parts: [...leg.parts],
			pieces: [{ points: leg.points, free: false }]
		};
		// raccordi dichiarati tra il punto scelto e il sentiero
		if (sa.dist > CONNECT_M) {
			const c = await this.freehand([a, { lon: sa.lon, lat: sa.lat }]);
			out.points = [...c.points.slice(0, -1), ...out.points];
			out.parts = [...c.parts, ...out.parts];
			out.pieces = [...c.pieces, ...out.pieces];
		}
		if (sb.dist > CONNECT_M) {
			const c = await this.freehand([{ lon: sb.lon, lat: sb.lat }, b]);
			out.points = [...out.points, ...c.points.slice(1)];
			out.parts = [...out.parts, ...c.parts];
			out.pieces = [...out.pieces, ...c.pieces];
		}
		return out;
	}

	/** Tratto a mano libera lungo i punti dati, con le quote dal modello del terreno. */
	private async freehand(line: PlanPoint[]): Promise<PlannedLeg> {
		const dense: [number, number][] = [];
		let len = 0;
		for (let i = 0; i + 1 < line.length; i++) {
			const a = line[i];
			const b = line[i + 1];
			const d = haversineM(a.lon, a.lat, b.lon, b.lat);
			len += d;
			const n = Math.max(1, Math.ceil(d / FREE_STEP_M));
			for (let k = 0; k < n; k++)
				dense.push([a.lon + ((b.lon - a.lon) * k) / n, a.lat + ((b.lat - a.lat) * k) / n]);
		}
		const last = line[line.length - 1];
		dense.push([last.lon, last.lat]);

		let eles: (number | null)[] = this.deps.elevations
			? await this.deps.elevations(dense).catch(() => dense.map(() => null))
			: dense.map(() => null);
		// senza modello del terreno: quota del sentiero più vicino, se c'è
		if (eles.some((e) => e == null)) {
			const g = await this.area(bboxOf(line), 0.5);
			if (g) eles = eles.map((e, i) => e ?? snap(g, dense[i][0], dense[i][1], 3, 300)?.ele ?? null);
		}
		const noEle = eles.every((e) => e == null);
		const filled = fillGaps(eles);
		const points: RoutePoint[] = dense.map(([lon, lat], i) => [lon, lat, filled[i]]);
		return {
			points,
			parts: [{ len, diff: null, cls: null, flags: 0, ref: '', freehand: true }],
			freehand: true,
			pieces: [{ points, free: true }],
			...(noEle ? { noEle } : {})
		};
	}
}

/** Riempie i buchi interpolando tra i valori noti (0 se non ce n'è nessuno). */
export function fillGaps(values: (number | null)[]): number[] {
	const known = values.flatMap((v, i) => (v == null ? [] : [i]));
	if (!known.length) return values.map(() => 0);
	return values.map((v, i) => {
		if (v != null) return v;
		const after = known.find((k) => k > i);
		const before = [...known].reverse().find((k) => k < i);
		if (before == null) return values[after!]!;
		if (after == null) return values[before]!;
		const t = (i - before) / (after - before);
		return values[before]! + (values[after]! - values[before]!) * t;
	});
}
