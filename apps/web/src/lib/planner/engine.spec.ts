import { describe, expect, it } from 'vitest';
import { F_MARKED, haversineM, type RawTile } from '../routing/graph';
import { routeStats } from '../routing/stats';
import { PlannerEngine, fillGaps } from './engine';
import { addPoint, emptyPlan, setMode } from './plan';

// A ---E segnato--- B ---EE--- C, e una via T più lunga A – D – C (come router.spec.ts)
const P = {
	A: [11.0, 46.0, 1000],
	B: [11.01, 46.0, 1100],
	C: [11.02, 46.0, 1200],
	D: [11.01, 46.006, 1050]
} as const;
const ids = { A: 0, B: 1, C: 2, D: 3 } as const;
type K = keyof typeof P;

function edge(a: K, b: K, diff: number, cls: number, flags: number): RawTile['e'][number] {
	const len = haversineM(P[a][0], P[a][1], P[b][0], P[b][1]);
	const dz = P[b][2] - P[a][2];
	return [ids[a], ids[b], len, Math.max(dz, 0), Math.max(-dz, 0), diff, cls, flags, -1, []];
}

const TILE: RawTile = {
	n: (Object.keys(P) as K[]).map((k) => [
		ids[k],
		Math.round(P[k][0] * 1e5),
		Math.round(P[k][1] * 1e5),
		P[k][2]
	]),
	e: [
		edge('A', 'B', 1, 0, F_MARKED),
		edge('B', 'C', 2, 0, F_MARKED),
		edge('A', 'D', 0, 1, 0),
		edge('D', 'C', 0, 1, 0)
	],
	r: [],
	p: [
		['c', 1101000, 4600010, 1105, 'Dosso di prova'],
		['r', 1105000, 4610000, 1500, 'Rifugio lontano']
	]
};

function engine(elevations?: (pts: [number, number][]) => Promise<(number | null)[]>) {
	const calls: string[] = [];
	const e = new PlannerEngine({
		fetchJson: async (name) => {
			calls.push(name);
			if (name === 'index.json')
				return { schema: 1, tile: [0.1, 0.05], scale: 1e5, tiles: ['110_920'], attribution: '' };
			if (name === '110_920.json') return TILE;
			throw new Error('404');
		},
		elevations
	});
	return { e, calls };
}

const A = { lon: 11.0, lat: 46.0 };
const C = { lon: 11.02, lat: 46.0 };

describe('motore del planner', () => {
	it('instrada sui sentieri ammessi e scarica ogni tassello una volta sola', async () => {
		const { e, calls } = engine();
		let plan = addPoint(addPoint(emptyPlan(1), A), C);
		const [leg] = await e.legs(plan);
		expect(leg.freehand).toBe(false);
		expect(leg.parts.every((p) => (p.diff ?? 0) <= 1)).toBe(true); // evita B–C (EE)
		plan = { ...plan, maxDiff: 2 };
		const [hard] = await e.legs(plan);
		expect(hard.parts.some((p) => p.diff === 2)).toBe(true);
		await e.legs(plan);
		expect(calls.filter((c) => c === '110_920.json')).toHaveLength(1);
		expect(calls.filter((c) => c === 'index.json')).toHaveLength(1);
	});

	it('i tratti uguali arrivano dalla cache', async () => {
		const { e } = engine();
		const plan = addPoint(addPoint(emptyPlan(), A), C);
		const [a] = await e.legs(plan);
		const [b] = await e.legs(plan);
		expect(b).toBe(a);
	});

	it('punto lontano dai sentieri: raccordo o tratto a mano libera dichiarato', async () => {
		const { e } = engine(async (pts) => pts.map(() => 1234));
		// 100 m a nord di A: agganciato con un raccordo tratteggiato
		const near = await e.legs(addPoint(addPoint(emptyPlan(), { lon: 11.0, lat: 46.0009 }), C));
		expect(near[0].pieces[0].free).toBe(true);
		expect(near[0].pieces.some((p) => !p.free)).toBe(true);
		// 2 km a nord: niente sentiero entro 250 m
		const far = await e.legs(addPoint(addPoint(emptyPlan(), { lon: 11.0, lat: 46.018 }), C));
		expect(far[0].fallback).toBe('lontano');
		expect(far[0].freehand).toBe(true);
		expect(far[0].points.every((p) => p[2] === 1234)).toBe(true);
	});

	it('a mano libera segue la forma della traccia importata', async () => {
		const { e } = engine(async (pts) => pts.map(() => null));
		let plan = addPoint(addPoint(emptyPlan(), A), C);
		plan = setMode(plan, 0, 'f');
		plan.shapes[0] = [{ lon: 11.01, lat: 46.006 }];
		const [leg] = await e.legs(plan);
		const st = routeStats([leg]);
		expect(st.km).toBeGreaterThan(1.7); // passa da D, più lungo della linea diretta
		expect(st.freehandKm).toBeGreaterThan(1.7);
		// senza modello del terreno: quote dal sentiero più vicino
		expect(leg.noEle).toBeUndefined();
		expect(Math.max(...leg.points.map((p) => p[2]))).toBeGreaterThan(1000);
	});

	it('senza grafo il planner resta utilizzabile a mano libera', async () => {
		const e = new PlannerEngine({ fetchJson: async () => Promise.reject(new Error('offline')) });
		const [leg] = await e.legs(addPoint(addPoint(emptyPlan(), A), C));
		expect(leg.fallback).toBe('grafo');
		expect(leg.noEle).toBe(true);
		expect(await e.snapPoint(A, 1)).toBeNull();
	});

	it('trova i luoghi lungo il percorso, in ordine', async () => {
		const { e } = engine();
		// con EE ammesso il percorso passa da B, accanto al dosso
		const [leg] = await e.legs(addPoint(addPoint(emptyPlan(2), A), C));
		const pois = e.poisAlong(leg.points);
		expect(pois.map((p) => p.poi.name)).toEqual(['Dosso di prova']);
		expect(pois[0].at).toBeGreaterThan(700);
	});

	it('riempie i buchi delle quote', () => {
		expect(fillGaps([null, 100, null, 200, null])).toEqual([100, 100, 150, 200, 200]);
		expect(fillGaps([null, null])).toEqual([0, 0]);
	});
});
