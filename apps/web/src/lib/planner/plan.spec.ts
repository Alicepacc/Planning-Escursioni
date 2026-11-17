import { describe, expect, it } from 'vitest';
import {
	addPoint,
	closeLoop,
	decodePoints,
	emptyPlan,
	encodePoints,
	insertPoint,
	isLoop,
	movePoint,
	openLoop,
	planFromLine,
	planFromParams,
	planToParams,
	removePoint,
	reversePlan,
	sampleLine,
	setAr,
	setMode,
	type Plan
} from './plan';

const A = { lon: 11.5218, lat: 46.149 };
const B = { lon: 11.5445, lat: 46.1347 };
const C = { lon: 11.5522, lat: 46.1421 };
const D = { lon: 11.5505, lat: 46.1508 };

function abc(): Plan {
	let p = emptyPlan();
	for (const q of [A, B, C]) p = addPoint(p, q);
	return p;
}

describe('codifica del piano', () => {
	it('i punti fanno andata e ritorno con precisione di 1e-5°', () => {
		const pts = [A, B, C, { lon: -0.00001, lat: -89.99999 }, { lon: 179.99999, lat: 0 }];
		const text = encodePoints(pts);
		expect(text).toMatch(/^[A-Za-z0-9_-]+$/);
		expect(decodePoints(text)).toEqual(pts);
	});

	it('URL compatto e reversibile, con tratti a mano libera, forme e opzioni', () => {
		let plan = addPoint(abc(), D, 'f');
		plan.shapes[2] = [{ lon: 11.551, lat: 46.146 }];
		plan = { ...plan, maxDiff: 2, ar: true, name: 'Giro dei laghi' };
		const q = planToParams(plan);
		expect(q.get('f')).toBe('2');
		expect(q.get('d')).toBe('2');
		const back = planFromParams(new URLSearchParams(q.toString()));
		expect(back).toEqual(plan);
		// 4 punti in una manciata di caratteri
		expect(q.get('p')!.length).toBeLessThan(40);
	});

	it('parametri rovinati non rompono la pagina', () => {
		expect(planFromParams(new URLSearchParams('p=%%%&d=9')).points).toEqual([]);
		const p = planFromParams(new URLSearchParams(`p=${encodePoints([A, B])}&f=7.x&s=9.AA&d=9`));
		expect(p.points).toHaveLength(2);
		expect(p.modes).toEqual(['r']);
		expect(p.maxDiff).toBe(1);
	});
});

describe('operazioni sul piano', () => {
	it('aggiunge, inserisce e toglie punti mantenendo i tratti allineati', () => {
		let plan = abc();
		expect(plan.modes).toEqual(['r', 'r']);
		plan = insertPoint(plan, 0, D);
		expect(plan.points).toEqual([A, D, B, C]);
		expect(plan.modes).toHaveLength(3);
		plan = removePoint(plan, 1);
		expect(plan.points).toEqual([A, B, C]);
		expect(plan.modes).toEqual(['r', 'r']);
		expect(removePoint(plan, 0).points).toEqual([B, C]);
		expect(removePoint(plan, 2).modes).toEqual(['r']);
	});

	it('due tratti a mano libera uniti restano a mano libera, con le forme', () => {
		const plan = setMode(setMode(abc(), 0, 'f'), 1, 'f');
		plan.shapes = [[D], [{ lon: 11.55, lat: 46.14 }]];
		const merged = removePoint(plan, 1);
		expect(merged.modes).toEqual(['f']);
		expect(merged.shapes[0]).toHaveLength(2);
		expect(removePoint(setMode(abc(), 0, 'f'), 1).modes).toEqual(['r']);
	});

	it('anello: chiude, sposta insieme partenza e arrivo, riapre', () => {
		const loop = closeLoop(abc());
		expect(isLoop(loop)).toBe(true);
		expect(closeLoop(loop)).toBe(loop);
		const moved = movePoint(loop, 0, D);
		expect(moved.points[0]).toEqual(D);
		expect(moved.points[3]).toEqual(D);
		expect(openLoop(loop).points).toEqual([A, B, C]);
		// togliere la partenza: l'anello riparte dal punto successivo
		const fromB = removePoint(loop, 0);
		expect(fromB.points).toEqual([B, C, B]);
		expect(isLoop(fromB)).toBe(true);
	});

	it('inverte punti, modi e forme; andata e ritorno non vale per gli anelli', () => {
		const plan = setMode(abc(), 0, 'f');
		plan.shapes[0] = [D, { lon: 11.53, lat: 46.14 }];
		const rev = reversePlan(plan);
		expect(rev.points).toEqual([C, B, A]);
		expect(rev.modes).toEqual(['r', 'f']);
		expect(rev.shapes[1]).toEqual([{ lon: 11.53, lat: 46.14 }, D]);
		expect(setAr(plan, true).ar).toBe(true);
		expect(setAr(closeLoop(plan), true).ar).toBe(false);
	});

	it('inserire in un tratto con forma la divide nel vertice più vicino', () => {
		let plan = setMode(addPoint(emptyPlan(), A), 0, 'f');
		plan = addPoint(plan, C, 'f');
		const s = [
			{ lon: 11.53, lat: 46.145 },
			{ lon: 11.54, lat: 46.14 },
			{ lon: 11.545, lat: 46.141 }
		];
		plan.shapes[0] = s;
		const split = insertPoint(plan, 0, { lon: 11.5401, lat: 46.1401 });
		expect(split.shapes).toEqual([[s[0]], [s[2]]]);
		expect(split.modes).toEqual(['f', 'f']);
	});
});

describe('da una traccia esistente', () => {
	it('campiona la linea ogni ~800 m, estremi compresi', () => {
		// 5 km verso est a passi di 100 m
		const line = Array.from({ length: 51 }, (_, i) => ({ lon: 11.5 + i * 0.0012943, lat: 46.15 }));
		const pts = sampleLine(line, 800);
		expect(pts[0]).toEqual(line[0]);
		expect(pts[pts.length - 1]).toEqual(line[50]);
		expect(pts.length).toBeGreaterThanOrEqual(6);
		expect(pts.length).toBeLessThanOrEqual(8);
		const plan = planFromLine(line, { maxDiff: 2, name: 'Prova' });
		expect(plan.modes.every((m) => m === 'r')).toBe(true);
		expect(plan.maxDiff).toBe(2);
	});
});
