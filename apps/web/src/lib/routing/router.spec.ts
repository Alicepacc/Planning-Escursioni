import { describe, expect, it } from 'vitest';
import { F_MARKED, TrailGraph, haversineM, snap, type RawTile } from './graph';
import { freehandLeg, routeBetween } from './router';
import { routeStats, routeWarnings } from './stats';

// A ---E segnato--- B ---EE--- C      (in basso)
//  \                           /
//   ---T--- D -------T--------        (in alto: più lungo)
const P = {
	A: [11.0, 46.0, 1000],
	B: [11.01, 46.0, 1100],
	C: [11.02, 46.0, 1200],
	D: [11.01, 46.006, 1050]
} as const;
const id = { A: 0, B: 1, C: 2, D: 3 } as const;

function edge(a: keyof typeof P, b: keyof typeof P, diff: number, cls: number, flags: number) {
	const len = haversineM(P[a][0], P[a][1], P[b][0], P[b][1]);
	const dz = P[b][2] - P[a][2];
	return [
		id[a],
		id[b],
		len,
		Math.max(dz, 0),
		Math.max(-dz, 0),
		diff,
		cls,
		flags,
		-1,
		[]
	] as RawTile['e'][number];
}

function graph(): TrailGraph {
	const g = new TrailGraph({
		schema: 1,
		tile: [0.1, 0.05],
		scale: 100000,
		tiles: ['110_920'],
		attribution: ''
	});
	g.addTile('110_920', {
		n: (Object.keys(P) as (keyof typeof P)[]).map((k) => [
			id[k],
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
		p: [['c', 1102000, 4600600, 1050, 'Cima prova']]
	});
	return g;
}

describe('router nel browser', () => {
	it("aggancia un punto all'arco più vicino", () => {
		const g = graph();
		const s = snap(g, 11.005, 46.0003)!;
		expect(s.edge.a).toBe(id.A);
		expect(s.edge.b).toBe(id.B);
		expect(s.dist).toBeLessThan(40);
		expect(g.pois[0].name).toBe('Cima prova');
	});

	it('evita i tratti oltre la difficoltà scelta, li usa se ammessi', () => {
		const g = graph();
		// l'aggancio rispetta la difficoltà massima, come nel planner
		const from = snap(g, 11.0, 46.0, 1)!;
		const to = snap(g, 11.02, 46.0, 1)!;
		const easy = routeBetween(g, from, to, { maxDiff: 1 })!;
		expect(easy.parts.every((p) => (p.diff ?? 0) <= 1)).toBe(true);
		expect(easy.points.some((p) => Math.abs(p[1] - 46.006) < 1e-6)).toBe(true); // passa da D
		const hard = routeBetween(g, snap(g, 11.0, 46.0, 2)!, snap(g, 11.02, 46.0, 2)!, {
			maxDiff: 2
		})!;
		expect(hard.parts.some((p) => p.diff === 2)).toBe(true); // passa da B, più corto
		const t = routeBetween(g, snap(g, 11.0, 46.0, 0)!, snap(g, 11.02, 46.0, 0)!, { maxDiff: 0 })!;
		expect(t.parts.every((p) => p.diff === 0)).toBe(true);
	});

	it('percorso sullo stesso arco e statistiche', () => {
		const g = graph();
		const a = snap(g, 11.002, 46.0)!;
		const b = snap(g, 11.008, 46.0)!;
		const leg = routeBetween(g, a, b, { maxDiff: 3 })!;
		const st = routeStats([leg]);
		expect(st.km).toBeGreaterThan(0.4);
		expect(st.km).toBeLessThan(0.5);
		expect(st.up).toBeGreaterThan(50);
		expect(st.down).toBe(0);
		expect(st.maxDiff).toBe('E');
	});

	it('tratti a mano libera e avvisi', () => {
		const leg = freehandLeg([11.0, 46.0, 1000], [11.0, 46.01, 1300]);
		expect(leg.freehand).toBe(true);
		const w = routeWarnings([leg], 1);
		expect(w[0].kind).toBe('mano_libera');
		expect(routeStats([leg]).freehandKm).toBeGreaterThan(1);
	});
});
