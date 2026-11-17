import { describe, expect, it } from 'vitest';
import { isLoop } from '../planner/plan';
import { F_MARKED, TrailGraph, haversineM, type RawTile } from '../routing/graph';
import { sunFromGradients } from './exposure';
import { exposureFactor, generate, similarity, type GenOptions } from './generator';
import { PlannerEngine } from '../planner/engine';
import { fitLine } from '../planner/fit';
import { routeStats } from '../routing/stats';
import {
	GENERATED_LABEL,
	equipmentFor,
	makePoster,
	ofName,
	proposalAnchors,
	proposalLine
} from './poster';

//            B (lago) ──E segnato── A (Monte Prova) ──EE── C (Cima Alta)
//            │                      │
//         T, carrareccia         E segnato
//            │                      │
//            S ─────────────────────┘
const P = {
	S: [11.0, 46.0, 1000],
	A: [11.012, 46.004, 1350],
	B: [11.0, 46.009, 1150],
	C: [11.022, 46.009, 1700]
} as const;
type K = keyof typeof P;
const ids: Record<K, number> = { S: 0, A: 1, B: 2, C: 3 };

/** arco con un punto intermedio (per avere forme e quote lungo il tratto) */
function edge(
	a: K,
	b: K,
	diff: number,
	cls: number,
	flags: number,
	ref: number
): RawTile['e'][number] {
	const len = haversineM(P[a][0], P[a][1], P[b][0], P[b][1]);
	const dz = P[b][2] - P[a][2];
	const mx = Math.round(((P[a][0] + P[b][0]) / 2) * 1e5) - Math.round(P[a][0] * 1e5);
	const my = Math.round(((P[a][1] + P[b][1]) / 2) * 1e5) - Math.round(P[a][1] * 1e5);
	return [
		ids[a],
		ids[b],
		len,
		Math.max(dz, 0),
		Math.max(-dz, 0),
		diff,
		cls,
		flags,
		ref,
		[mx, my, (P[a][2] + P[b][2]) / 2]
	];
}

const TILE: RawTile = {
	n: (Object.keys(P) as K[]).map((k) => [
		ids[k],
		Math.round(P[k][0] * 1e5),
		Math.round(P[k][1] * 1e5),
		P[k][2]
	]),
	e: [
		edge('S', 'A', 1, 0, F_MARKED, 0),
		edge('A', 'B', 1, 0, F_MARKED, 1),
		edge('S', 'B', 0, 1, 0, -1),
		edge('A', 'C', 2, 0, F_MARKED, 2)
	],
	r: ['301', '302', '303'],
	p: [
		['c', Math.round(P.A[0] * 1e5), Math.round(P.A[1] * 1e5), 1350, 'Monte Prova'],
		['l', Math.round(P.B[0] * 1e5) + 30, Math.round(P.B[1] * 1e5), 1148, 'Lago Prova'],
		['c', Math.round(P.C[0] * 1e5), Math.round(P.C[1] * 1e5), 1700, 'Cima Alta'],
		['k', Math.round(P.S[0] * 1e5) + 50, Math.round(P.S[1] * 1e5), null, 'Parcheggio Prova']
	]
};

function graph(): TrailGraph {
	const g = new TrailGraph({
		schema: 1,
		tile: [0.1, 0.05],
		scale: 1e5,
		tiles: ['110_920'],
		attribution: ''
	});
	g.addTile('110_920', TILE);
	return g;
}

/** motore del planner sullo stesso tassello (per aprire le proposte nel planner) */
function engine(): PlannerEngine {
	return new PlannerEngine({
		fetchJson: async (name) =>
			name === 'index.json'
				? { schema: 1, tile: [0.1, 0.05], scale: 1e5, tiles: ['110_920'], attribution: '' }
				: TILE
	});
}

const base: GenOptions = {
	start: { lon: P.S[0], lat: P.S[1] },
	type: 'anello',
	minMinutes: 20,
	maxMinutes: 240,
	maxDiff: 1,
	wishes: [],
	month: 7
};

describe('generatore di proposte', () => {
	it('compone un anello con cima e lago, rientro per un’altra via', () => {
		const { proposals } = generate(graph(), { ...base, wishes: ['cima', 'lago'] });
		expect(proposals.length).toBeGreaterThanOrEqual(1);
		const p = proposals[0];
		expect(p.type).toBe('anello');
		expect(p.shares.overlap).toBeLessThan(0.2);
		const names = p.along.map((a) => a.poi.name);
		expect(names).toContain('Monte Prova');
		expect(names).toContain('Lago Prova');
		expect(p.factors.partenza).toBe(6); // parcheggio a 40 m
		expect(p.stats.maxDiff).toBe('E');
		// fattori espliciti: il punteggio è la loro somma
		expect(p.score).toBeCloseTo(
			Object.values(p.factors).reduce((s, v) => s + v, 0),
			6
		);
	});

	it('rispetta la difficoltà massima: la Cima Alta (EE) solo se ammessa', () => {
		const easy = generate(graph(), { ...base, wishes: ['cima'] });
		expect(easy.proposals.every((p) => !p.along.some((a) => a.poi.name === 'Cima Alta'))).toBe(
			true
		);
		const hard = generate(graph(), {
			...base,
			type: 'andata_ritorno',
			wishes: ['cima'],
			maxDiff: 2
		});
		expect(hard.proposals.some((p) => p.vias.some((v) => v.name === 'Cima Alta'))).toBe(true);
		expect(hard.proposals.find((p) => p.vias[0]?.name === 'Cima Alta')!.stats.maxDiff).toBe('EE');
	});

	it('andata e ritorno: stessa via al ritorno, salita = discesa', async () => {
		const { proposals } = generate(graph(), { ...base, type: 'andata_ritorno', wishes: ['lago'] });
		const p = proposals[0];
		expect(p.legs).toHaveLength(2);
		expect(Math.abs(p.stats.up - p.stats.down)).toBeLessThan(1);
		const poster = makePoster(p, base, 'Parcheggio Prova');
		expect(poster.description.join(' ')).toContain('Il ritorno è per la stessa via.');
		const plan = await fitLine(engine(), proposalLine(p), proposalAnchors(p), {
			maxDiff: 1,
			name: poster.title,
			ar: true
		});
		expect(plan.ar).toBe(true);
	});

	it('traversata verso un arrivo dato', () => {
		const { proposals } = generate(graph(), {
			...base,
			type: 'traversata',
			end: { lon: P.B[0], lat: P.B[1] },
			wishes: ['cima']
		});
		expect(proposals[0].vias[0].name).toBe('Monte Prova');
		const last = proposals[0].points.at(-1)!;
		expect(haversineM(last[0], last[1], P.B[0], P.B[1])).toBeLessThan(5);
	});

	it('vincoli impossibili: nessuna proposta e il motivo', () => {
		const r = generate(graph(), { ...base, minMinutes: 600, maxMinutes: 700 });
		expect(r.proposals).toEqual([]);
		expect(r.reason).toBeTruthy();
		const far = generate(graph(), { ...base, start: { lon: 11.3, lat: 46.3 } });
		expect(far.reason).toMatch(/lontana/);
	});

	it('locandina: titolo dai luoghi, etichetta, tappe in ordine con tempi crescenti', async () => {
		const p = generate(graph(), { ...base, wishes: ['cima', 'lago'] }).proposals[0];
		const poster = makePoster(p, base, 'Parcheggio Prova');
		expect(poster.title).toBe('Anello del Monte Prova e del Lago Prova');
		expect(poster.label).toBe(GENERATED_LABEL);
		const mins = poster.stages.map((s) => s.minutes);
		expect([...mins].sort((a, b) => a - b)).toEqual(mins);
		expect(poster.stages[0].name).toBe('Parcheggio Prova');
		expect(poster.stages.at(-1)!.name).toBe('Rientro alla partenza');
		expect(poster.description[0]).toMatch(/^Anello di \d+,\d km con \d+ m di dislivello/);
		expect(poster.why[0]).toMatch(/su sentieri numerati/);
		// nel planner: anello chiuso con pochi punti, stesso percorso
		const e = engine();
		const plan = await fitLine(e, proposalLine(p), proposalAnchors(p), {
			maxDiff: 1,
			name: poster.title
		});
		expect(isLoop(plan)).toBe(true);
		expect(plan.points.length).toBeLessThanOrEqual(6);
		const km = routeStats(await e.legs(plan)).km;
		expect(Math.abs(km - p.stats.km)).toBeLessThan(0.05);
	});

	it('somiglianza tra proposte e diversità', () => {
		const a = new Map([
			[1, 100],
			[2, 100]
		]);
		expect(similarity(a, a)).toBe(1);
		expect(similarity(a, new Map([[3, 50]]))).toBe(0);
		expect(similarity(a, new Map([[2, 100]]))).toBe(1);
	});
});

describe('qualità: esposizione, stagione, testi', () => {
	it('esposizione dai gradienti del terreno', () => {
		expect(sunFromGradients([[0, 0.5]])).toBeGreaterThan(0.9); // sale verso nord: guarda a sud
		expect(sunFromGradients([[0, -0.5]])).toBeLessThan(0.1);
		expect(sunFromGradients([[0.01, 0.01]])).toBe(0.5);
		expect(sunFromGradients([])).toBeNull();
	});

	it("d'inverno il sole conta a favore, d'estate l'ombra", () => {
		expect(exposureFactor(1, 1)).toBeGreaterThan(0);
		expect(exposureFactor(1, 7)).toBeLessThan(0);
		expect(exposureFactor(0, 9)).toBe(0);
	});

	it('articoli italiani e attrezzatura', () => {
		expect(ofName('Lago di Erdemolo')).toBe('del Lago di Erdemolo');
		expect(ofName("Cima d'Asta")).toBe("della Cima d'Asta");
		expect(ofName('Laghi di Bombasel')).toBe('dei Laghi di Bombasel');
		expect(ofName('Alpe di Siusi')).toBe("dell'Alpe di Siusi");
		expect(ofName('Fravort')).toBe('di Fravort');
		expect(equipmentFor(1, 1800, 'E')).toContain('ciaspole e ramponcini');
		expect(equipmentFor(7, 2300, 'EE')).toEqual(
			expect.arrayContaining([
				'giacca antivento e strato caldo',
				'scarponi con suola rigida, passo sicuro'
			])
		);
	});
});
