// Valutazione del generatore (SPEC §5.7 a): con gli stessi vincoli che chiederebbe un utente, il
// generatore «riscopre» le gite reali delle sezioni? Per ogni gita con traccia verificata si
// danno partenza (e arrivo per le traversate), tipo, tempo e dislivello con un margine, difficoltà
// massima, mese e tipo di meta principale; mai la traccia.

import type { ItineraryDoc } from '../data/types';
import { haversineM, type Poi, type TrailGraph } from '../routing/graph';
import { poisAlong } from '../routing/pois';
import { generate, type GenOptions, type ProposalType, type Wish } from './generator';

export const MATCH_COVERAGE = 0.7;
export const MATCH_TOLERANCE_M = 150;
export const TOP_K = 5;

type LonLat = [number, number];

/** Punti ogni `stepM` metri lungo la linea. */
export function resample(line: LonLat[], stepM = 50): LonLat[] {
	if (line.length < 2) return line;
	const out: LonLat[] = [line[0]];
	let carry = 0;
	for (let i = 1; i < line.length; i++) {
		const [x1, y1] = line[i - 1];
		const [x2, y2] = line[i];
		const d = haversineM(x1, y1, x2, y2);
		let at = stepM - carry;
		while (at <= d) {
			const t = at / d;
			out.push([x1 + (x2 - x1) * t, y1 + (y2 - y1) * t]);
			at += stepM;
		}
		carry = d - (at - stepM);
	}
	out.push(line[line.length - 1]);
	return out;
}

/** Quota dei punti di `a` (ogni 50 m) entro `tolM` metri dalla linea `b`. */
export function coverage(a: LonLat[], b: LonLat[], tolM = MATCH_TOLERANCE_M): number {
	const pts = resample(a);
	if (!pts.length || b.length < 2) return 0;
	const lat0 = (pts[0][1] * Math.PI) / 180;
	const kx = 111320 * Math.cos(lat0);
	const ky = 110950;
	// indice a griglia dei segmenti di b (celle di ~tolM)
	const cell = tolM;
	const grid = new Map<string, number[]>();
	const xy = b.map(([lon, lat]) => [lon * kx, lat * ky]);
	for (let i = 0; i + 1 < xy.length; i++) {
		const [x1, y1] = xy[i];
		const [x2, y2] = xy[i + 1];
		for (
			let gx = Math.floor(Math.min(x1, x2) / cell);
			gx <= Math.floor(Math.max(x1, x2) / cell);
			gx++
		)
			for (
				let gy = Math.floor(Math.min(y1, y2) / cell);
				gy <= Math.floor(Math.max(y1, y2) / cell);
				gy++
			) {
				const k = `${gx}_${gy}`;
				const list = grid.get(k);
				if (list) list.push(i);
				else grid.set(k, [i]);
			}
	}
	let inside = 0;
	for (const [lon, lat] of pts) {
		const px = lon * kx;
		const py = lat * ky;
		const gx = Math.floor(px / cell);
		const gy = Math.floor(py / cell);
		let ok = false;
		for (let dx = -1; dx <= 1 && !ok; dx++)
			for (let dy = -1; dy <= 1 && !ok; dy++)
				for (const i of grid.get(`${gx + dx}_${gy + dy}`) ?? []) {
					const [ax, ay] = xy[i];
					const vx = xy[i + 1][0] - ax;
					const vy = xy[i + 1][1] - ay;
					const l2 = vx * vx + vy * vy;
					const t = l2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * vx + (py - ay) * vy) / l2)) : 0;
					if (Math.hypot(px - (ax + vx * t), py - (ay + vy * t)) <= tolM) {
						ok = true;
						break;
					}
				}
		if (ok) inside++;
	}
	return inside / pts.length;
}

export function maxDiffOf(doc: ItineraryDoc): number {
	const g = (doc.difficulty.cai ?? doc.difficulty.raw ?? '').toUpperCase();
	if (g.startsWith('EEA')) return 3;
	if (g.startsWith('EE')) return 2;
	if (g.startsWith('E')) return 1; // E ed EAI (ciaspole su sentieri E)
	if (g.startsWith('T')) return 0;
	return 2; // non dichiarata: si ammette fino a EE
}

const WISH_OF: Record<string, Wish> = { c: 'cima', l: 'lago', r: 'rifugio' };

/** Meta principale della gita reale: la cima più alta, altrimenti il primo lago o rifugio. */
export function mainDestination(graph: TrailGraph, doc: ItineraryDoc): Poi | null {
	const along = poisAlong(
		graph,
		doc.line.map(([lon, lat]) => [lon, lat, 0]),
		100
	);
	const peaks = along
		.filter((a) => a.poi.kind === 'c')
		.sort((a, b) => (b.poi.ele ?? 0) - (a.poi.ele ?? 0));
	return (
		peaks[0]?.poi ??
		along.find((a) => a.poi.kind === 'l')?.poi ??
		along.find((a) => a.poi.kind === 'r')?.poi ??
		null
	);
}

/** Vincoli che chiederebbe un utente per una gita come questa (mai la traccia). */
export function inputsFor(graph: TrailGraph, doc: ItineraryDoc): GenOptions {
	const minutes = doc.computed.cai_forward_min;
	const up = doc.computed.ascent_m;
	const dest = mainDestination(graph, doc);
	const type = (
		['anello', 'andata_ritorno', 'traversata'].includes(doc.type) ? doc.type : 'anello'
	) as ProposalType;
	const last = doc.line[doc.line.length - 1];
	return {
		start: { lon: doc.line[0][0], lat: doc.line[0][1] },
		end: type === 'traversata' ? { lon: last[0], lat: last[1] } : null,
		type,
		minMinutes: minutes * 0.8,
		maxMinutes: minutes * 1.2,
		minUp: up * 0.75,
		maxUp: up * 1.25,
		maxDiff: maxDiffOf(doc),
		wishes: dest && WISH_OF[dest.kind] ? [WISH_OF[dest.kind]] : [],
		month: doc.activity.date ? Number(doc.activity.date.slice(5, 7)) : 7,
		// una ciaspolata dichiarata (EAI) è come chiedere «con le ciaspole»
		snowshoes: /EAI/i.test(doc.difficulty.raw ?? doc.difficulty.cai ?? ''),
		limit: TOP_K
	};
}

export interface EvalRow {
	id: string;
	title: string;
	type: string;
	inputs: Omit<GenOptions, 'start' | 'end'>;
	destination: string | null;
	proposals: number;
	tried: number;
	reason: string | null;
	/** rango (1…k) della prima proposta che riscopre la gita, null se nessuna */
	matchRank: number | null;
	/** miglior copertura reciproca tra la gita e una proposta (min delle due direzioni) */
	bestCoverage: number;
	destinationHit: boolean;
	ms: number;
}

export function evaluateActivity(graph: TrailGraph, doc: ItineraryDoc): EvalRow {
	const opts = inputsFor(graph, doc);
	const t0 = performance.now();
	const result = generate(graph, opts);
	const ms = performance.now() - t0;
	const real = doc.line;
	const dest = mainDestination(graph, doc);
	let matchRank: number | null = null;
	let best = 0;
	let destinationHit = false;
	result.proposals.forEach((p, i) => {
		const line = p.points.map(([lon, lat]) => [lon, lat] as LonLat);
		const cov = Math.min(coverage(real, line), coverage(line, real));
		best = Math.max(best, cov);
		if (matchRank == null && cov >= MATCH_COVERAGE) matchRank = i + 1;
		if (dest && p.points.some(([lon, lat]) => haversineM(lon, lat, dest.lon, dest.lat) <= 150))
			destinationHit = true;
	});
	const { start: _s, end: _e, ...inputs } = opts;
	void _s;
	void _e;
	return {
		id: doc.id,
		title: doc.title,
		type: opts.type,
		inputs,
		destination: dest?.name ?? null,
		proposals: result.proposals.length,
		tried: result.tried,
		reason: result.reason ?? null,
		matchRank,
		bestCoverage: best,
		destinationHit,
		ms
	};
}

export interface EvalSummary {
	activities: number;
	withProposals: number;
	match1: number;
	match3: number;
	match5: number;
	destination5: number;
	meanBestCoverage: number;
	meanMs: number;
}

export function summarize(rows: EvalRow[]): EvalSummary {
	const n = rows.length || 1;
	const at = (k: number) => rows.filter((r) => r.matchRank != null && r.matchRank <= k).length;
	return {
		activities: rows.length,
		withProposals: rows.filter((r) => r.proposals > 0).length,
		match1: at(1),
		match3: at(3),
		match5: at(5),
		destination5: rows.filter((r) => r.destinationHit).length,
		meanBestCoverage: rows.reduce((s, r) => s + r.bestCoverage, 0) / n,
		meanMs: rows.reduce((s, r) => s + r.ms, 0) / n
	};
}
