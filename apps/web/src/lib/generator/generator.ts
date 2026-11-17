// Generatore di proposte «stile sezione CAI» (SPEC §5.7 a). Sul grafo dei sentieri cerca anelli,
// andata e ritorno e traversate che rispettano i vincoli (tempo, dislivello, difficoltà, desideri)
// e li ordina con una funzione di qualità esplicita (ADR 0011): sentieri segnati, varietà,
// luoghi lungo il percorso, segnalazioni, stagione, parcheggio alla partenza, esposizione al sole.

import {
	F_ISSUE,
	F_LOW_VIS,
	F_MARKED,
	haversineM,
	snap,
	type Poi,
	type Snap,
	type TrailGraph
} from '../routing/graph';
import { poisAlong, type PoiAlong } from '../routing/pois';
import {
	Heap,
	edgeCost,
	edgeTime,
	routeBetween,
	type Leg,
	type RoutePoint
} from '../routing/router';
import { reverseLeg, routeStats, type RouteStats } from '../routing/stats';

export type ProposalType = 'anello' | 'andata_ritorno' | 'traversata';
export type Wish = 'cima' | 'lago' | 'rifugio' | 'panorama';

export interface GenOptions {
	start: { lon: number; lat: number };
	/** arrivo, solo per le traversate */
	end?: { lon: number; lat: number } | null;
	type: ProposalType;
	/** tempo netto (modello CAI), minuti */
	minMinutes: number;
	maxMinutes: number;
	minUp?: number | null;
	maxUp?: number | null;
	/** 0 T, 1 E, 2 EE, 3 EEA */
	maxDiff: number;
	wishes: Wish[];
	/** mese (1-12): stagione per quote, neve ed esposizione */
	month: number;
	/** con ciaspole: d'inverno quota e strade forestali non sono un difetto */
	snowshoes?: boolean;
	limit?: number;
}

export interface Shares {
	/** quota di lunghezza su sentieri numerati (catasto CAI o rete escursionistica OSM) */
	marked: number;
	/** su strade (minori e principali) */
	road: number;
	/** su strade forestali e carrarecce */
	track: number;
	issue: number;
	lowVis: number;
	/** quota ripercorsa due volte (negli anelli) */
	overlap: number;
	/** quota sopra i 1800 m */
	high: number;
}

export interface Proposal {
	type: ProposalType;
	legs: Leg[];
	points: RoutePoint[];
	stats: RouteStats;
	along: PoiAlong[];
	/** mete scelte dal generatore, in ordine */
	vias: Poi[];
	shares: Shares;
	refs: string[];
	score: number;
	/** contributi della funzione di qualità (per spiegare la proposta) */
	factors: Record<string, number>;
	/** archi percorsi e loro lunghezze (per la diversità tra proposte) */
	edgeLen: Map<number, number>;
	/** esposizione al sole dal DEM (0 a nord … 1 a sud), se calcolata */
	sun: number | null;
}

export interface GenResult {
	proposals: Proposal[];
	/** perché non ci sono proposte (o ce ne sono poche) */
	reason?: string;
	/** candidati valutati */
	tried: number;
	/** candidati scartati, per motivo */
	rejected?: Record<string, number>;
	/** mete considerate, in ordine (per la diagnosi) */
	targets?: { name: string; kind: string; minutes: number; rank: number }[];
}

export const WISH_KINDS: Record<Wish, string[]> = {
	cima: ['c'],
	lago: ['l'],
	rifugio: ['r'],
	panorama: ['v', 'c']
};
const DEFAULT_KINDS = ['c', 'l', 'r', 'v', 'b'];
const POI_WEIGHT: Record<string, number> = { c: 12, l: 9, r: 7, v: 5, b: 3 };
const USED_PENALTY = 6;
/** rapporto massimo tra costo del router (tempo × preferenze) e tempo netto, per i limiti */
const MAX_COST_PER_MINUTE = 1.6;
const MAX_SINGLE = 10;
const MAX_STRETCHED = 5;
const GENERIC_BEARINGS = [0, 60, 120, 180, 240, 300];
const MAX_PAIRS = 15;
const PAIR_MAX_KM = 5;
const WINTER = new Set([12, 1, 2, 3]);
const SUMMER = new Set([6, 7, 8]);

/** Quanto lontano caricare il grafo attorno alla partenza (km). */
export function searchRadiusKm(opts: Pick<GenOptions, 'maxMinutes' | 'type'>): number {
	const hours = opts.maxMinutes / 60;
	// a 3,5 km/h un anello si allontana al più di ~1/3 della sua lunghezza
	return Math.min(13, Math.max(3, hours * 3.5 * (opts.type === 'andata_ritorno' ? 0.55 : 0.45)));
}

function keyOf(p: Poi): string {
	return `${p.kind}|${p.name}|${p.lon.toFixed(4)}|${p.lat.toFixed(4)}`;
}

/** Albero dei percorsi migliori dalla partenza: costo del router e tempo netto per nodo. */
export interface CostTree {
	cost: Map<number, number>;
	/** tempo netto (minuti, modello CAI) lungo il percorso di costo minimo */
	time: Map<number, number>;
}

/** Percorsi di costo minimo (minuti pesati come nel router) dalla partenza, fino a `maxCost`. */
export function costTree(
	graph: TrailGraph,
	from: Snap,
	maxDiff: number,
	maxCost: number
): CostTree {
	const cost = new Map<number, number>();
	const time = new Map<number, number>();
	const heap = new Heap();
	const push = (n: number, c: number, t: number) => {
		if (c <= maxCost && c < (cost.get(n) ?? Infinity) && graph.nodes.has(n)) {
			cost.set(n, c);
			time.set(n, t);
			heap.push(n, c);
		}
	};
	const e = from.edge;
	const share = (len: number) => (e.len > 0 ? len / e.len : 0);
	push(
		e.a,
		edgeCost(e, false, from.pos, share(from.pos)),
		edgeTime(e, false, from.pos, share(from.pos))
	);
	const rest = e.len - from.pos;
	push(e.b, edgeCost(e, true, rest, share(rest)), edgeTime(e, true, rest, share(rest)));
	const done = new Set<number>();
	while (heap.size) {
		const [n, c] = heap.pop()!;
		if (done.has(n) || c > (cost.get(n) ?? Infinity)) continue;
		done.add(n);
		const t = time.get(n)!;
		for (const id of graph.adj.get(n) ?? []) {
			const edge = graph.edges[id];
			if (edge.diff > maxDiff) continue;
			const fwd = edge.a === n;
			push(fwd ? edge.b : edge.a, c + edgeCost(edge, fwd), t + edgeTime(edge, fwd));
		}
	}
	return { cost, time };
}

/** Costo e tempo netto per raggiungere un punto agganciato. */
function reach(tree: CostTree, s: Snap): { cost: number; time: number } {
	const e = s.edge;
	const share = (len: number) => (e.len > 0 ? len / e.len : 0);
	const rest = e.len - s.pos;
	const viaA = (tree.cost.get(e.a) ?? Infinity) + edgeCost(e, true, s.pos, share(s.pos));
	const viaB = (tree.cost.get(e.b) ?? Infinity) + edgeCost(e, false, rest, share(rest));
	return viaA <= viaB
		? {
				cost: viaA,
				time: (tree.time.get(e.a) ?? Infinity) + edgeTime(e, true, s.pos, share(s.pos))
			}
		: {
				cost: viaB,
				time: (tree.time.get(e.b) ?? Infinity) + edgeTime(e, false, rest, share(rest))
			};
}

interface Target {
	poi: Poi;
	snap: Snap;
	/** tempo netto dalla partenza (minuti) */
	time: number;
	rank: number;
}

/** Punto agganciato esattamente su un nodo (per passaggi e mete senza nome). */
function snapAtNode(graph: TrailGraph, n: number, maxDiff: number): Snap | null {
	const node = graph.nodes.get(n);
	if (!node) return null;
	for (const id of graph.adj.get(n) ?? []) {
		const edge = graph.edges[id];
		if (edge.diff > maxDiff) continue;
		return {
			edge,
			pos: edge.a === n ? 0 : edge.len,
			lon: node.lon,
			lat: node.lat,
			ele: node.ele,
			dist: 0
		};
	}
	return null;
}

/**
 * Passaggi per un anello partenza → meta → passaggio → partenza lungo quanto serve: tra gli
 * incroci con tempo(partenza→n) + tempo(meta→n) vicino a quello che manca, i più lontani
 * dall'asse partenza–meta, uno per lato (punti di un'ellisse con fuochi partenza e meta).
 */
function ellipseVias(
	graph: TrailGraph,
	treeS: CostTree,
	treeD: CostTree,
	from: { lon: number; lat: number },
	to: { lon: number; lat: number },
	want: number
): number[] {
	const kx = 111320 * Math.cos((from.lat * Math.PI) / 180);
	const ky = 110950;
	const ax = from.lon * kx;
	const ay = from.lat * ky;
	const dx = to.lon * kx - ax;
	const dy = to.lat * ky - ay;
	const len = Math.hypot(dx, dy) || 1;
	const best: (number | null)[] = [null, null];
	const bestOff = [0, 0];
	for (const [n, cd] of treeD.time) {
		const cs = treeS.time.get(n);
		if (cs == null) continue;
		const sum = cs + cd;
		if (sum < want * 0.85 || sum > want * 1.15 || cs < want * 0.15 || cd < want * 0.15) continue;
		if ((graph.adj.get(n)?.length ?? 0) < 3) continue; // solo incroci: niente vicoli ciechi
		const node = graph.nodes.get(n)!;
		const off = ((node.lon * kx - ax) * dy - (node.lat * ky - ay) * dx) / len;
		const side = off >= 0 ? 0 : 1;
		if (Math.abs(off) > bestOff[side]) {
			bestOff[side] = Math.abs(off);
			best[side] = n;
		}
	}
	return best.filter((n): n is number => n != null);
}

/** Mete senza nome per anelli dove mancano luoghi notevoli: un incrocio per direzione. */
function genericTargets(
	graph: TrailGraph,
	tree: CostTree,
	from: { lon: number; lat: number },
	minutes: number
): number[] {
	const kx = 111320 * Math.cos((from.lat * Math.PI) / 180);
	const out: number[] = [];
	for (const bearing of GENERIC_BEARINGS) {
		let best: number | null = null;
		let bestErr = Infinity;
		for (const [n, t] of tree.time) {
			if (t < minutes * 0.7 || t > minutes * 1.3 || (graph.adj.get(n)?.length ?? 0) < 3) continue;
			const node = graph.nodes.get(n)!;
			const b =
				(Math.atan2((node.lon - from.lon) * kx, (node.lat - from.lat) * 110950) * 180) / Math.PI;
			const err = Math.abs(((b - bearing + 540) % 360) - 180);
			if (err < bestErr && err < 30) {
				bestErr = err;
				best = n;
			}
		}
		if (best != null && !out.includes(best)) out.push(best);
	}
	return out;
}

interface Candidate {
	legs: Leg[];
	vias: Poi[];
}

function concatPoints(legs: Leg[]): RoutePoint[] {
	return legs.flatMap((l, i) => (i ? l.points.slice(1) : l.points));
}

/** Metri percorsi su ogni arco del grafo. */
function edgeLengths(legs: Leg[]): Map<number, number> {
	const out = new Map<number, number>();
	for (const p of legs.flatMap((l) => l.parts))
		if (p.edge != null) out.set(p.edge, (out.get(p.edge) ?? 0) + p.len);
	return out;
}

/** Quota di lunghezza percorsa più di una volta (sui metri davvero percorsi). */
function reusedShare(legs: Leg[]): number {
	const total = new Map<number, number>();
	const longest = new Map<number, number>();
	for (const p of legs.flatMap((l) => l.parts)) {
		if (p.edge == null) continue;
		total.set(p.edge, (total.get(p.edge) ?? 0) + p.len);
		longest.set(p.edge, Math.max(longest.get(p.edge) ?? 0, p.len));
	}
	let sum = 0;
	let reused = 0;
	for (const [id, t] of total) {
		sum += t;
		reused += t - longest.get(id)!;
	}
	return sum > 0 ? reused / sum : 0;
}

/** Somiglianza tra due proposte: lunghezza in comune sulla lunghezza della più corta. */
export function similarity(a: Map<number, number>, b: Map<number, number>): number {
	let common = 0;
	let la = 0;
	let lb = 0;
	for (const [id, l] of a) {
		la += l;
		if (b.has(id)) common += Math.min(l, b.get(id)!);
	}
	for (const l of b.values()) lb += l;
	return Math.min(la, lb) > 0 ? common / Math.min(la, lb) : 0;
}

function shareOf(legs: Leg[], pred: (p: Leg['parts'][number]) => boolean): number {
	const parts = legs.flatMap((l) => l.parts);
	const total = parts.reduce((s, p) => s + p.len, 0);
	return total > 0 ? parts.filter(pred).reduce((s, p) => s + p.len, 0) / total : 0;
}

function highShare(points: RoutePoint[], above: number): number {
	let total = 0;
	let high = 0;
	for (let i = 1; i < points.length; i++) {
		const d = haversineM(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1]);
		total += d;
		if ((points[i - 1][2] + points[i][2]) / 2 > above) high += d;
	}
	return total > 0 ? high / total : 0;
}

/** Numeri dei sentieri nell'ordine in cui si percorrono (i tratti brevi non contano). */
export function refsInOrder(legs: Leg[]): string[] {
	const out: string[] = [];
	for (const p of legs.flatMap((l) => l.parts))
		for (const r of p.ref.split(/\s*[;·,]\s*/).map((x) => x.trim()))
			if (r && !out.includes(r) && p.len > 150) out.push(r);
	return out;
}

/**
 * Proposte sul grafo già caricato attorno alla partenza (e all'arrivo per le traversate).
 * Deterministico: stessi dati e stessi vincoli danno le stesse proposte.
 */
export function generate(graph: TrailGraph, opts: GenOptions): GenResult {
	const limit = opts.limit ?? 3;
	const target = (opts.minMinutes + opts.maxMinutes) / 2;
	const start = snap(graph, opts.start.lon, opts.start.lat, opts.maxDiff, 300);
	if (!start)
		return { proposals: [], tried: 0, reason: 'La partenza è lontana dai sentieri ammessi.' };
	const end =
		opts.type === 'traversata' && opts.end
			? snap(graph, opts.end.lon, opts.end.lat, opts.maxDiff, 300)
			: null;
	if (opts.type === 'traversata' && !end)
		return {
			proposals: [],
			tried: 0,
			reason: 'Per una traversata serve un arrivo vicino ai sentieri ammessi.'
		};

	// 1. mete raggiungibili nella finestra di tempo
	const kinds = new Set(
		opts.wishes.length ? opts.wishes.flatMap((w) => WISH_KINDS[w]) : DEFAULT_KINDS
	);
	const tree = costTree(graph, start, opts.maxDiff, opts.maxMinutes * 1.6);
	const treeEnd = end ? costTree(graph, end, opts.maxDiff, opts.maxMinutes * 1.6) : null;
	const startEle = start.ele;
	const seen = new Set<string>();
	const targets: Target[] = [];
	for (const poi of graph.pois) {
		if (!kinds.has(poi.kind) || !poi.name) continue;
		const k = keyOf(poi);
		if (seen.has(k)) continue;
		seen.add(k);
		const s = snap(graph, poi.lon, poi.lat, opts.maxDiff, 150);
		if (!s) continue;
		const t = reach(tree, s).time;
		if (!Number.isFinite(t)) continue;
		let ideal: number;
		let ok: boolean;
		if (opts.type === 'andata_ritorno') {
			ideal = target / 2;
			ok = 2 * t >= opts.minMinutes * 0.8 && 2 * t <= opts.maxMinutes * 1.15;
		} else if (opts.type === 'anello') {
			ideal = target * 0.42;
			ok = t >= opts.minMinutes * 0.2 && t <= opts.maxMinutes * 0.6;
		} else {
			const te = treeEnd ? reach(treeEnd, s).time : Infinity;
			ideal = target / 2;
			ok = Number.isFinite(te) && t + te <= opts.maxMinutes * 1.15;
		}
		if (!ok) continue;
		const lift = poi.kind === 'c' && poi.ele != null ? Math.min(8, (poi.ele - startEle) / 150) : 0;
		const wished = opts.wishes.some((w) => WISH_KINDS[w].includes(poi.kind)) ? 10 : 0;
		const rank = (POI_WEIGHT[poi.kind] ?? 2) + lift + wished - (12 * Math.abs(t - ideal)) / ideal;
		targets.push({ poi, snap: s, time: t, rank });
	}
	targets.sort((a, b) => b.rank - a.rank);
	// mete troppo vicine tra loro (gruppi di laghetti, anticime) contano una volta sola; tra due
	// cime vicine resta la più alta: la vetta, non l'anticima
	const picked: Target[] = [];
	for (const t of targets) {
		const near = picked.findIndex(
			(p) => haversineM(p.poi.lon, p.poi.lat, t.poi.lon, t.poi.lat) < 300
		);
		if (near >= 0) {
			const p = picked[near];
			if (p.poi.kind === 'c' && t.poi.kind === 'c' && (t.poi.ele ?? 0) > (p.poi.ele ?? 0))
				picked[near] = t;
			continue;
		}
		picked.push(t);
		if (picked.length >= MAX_SINGLE) break;
	}

	// 2. candidati
	const route = (from: Snap, to: Snap, used: Leg[]): Leg | null => {
		const penalty = new Map<number, number>();
		for (const p of used.flatMap((l) => l.parts))
			if (p.edge != null && p.len > 1) penalty.set(p.edge, USED_PENALTY);
		return routeBetween(graph, from, to, { maxDiff: opts.maxDiff, penalty });
	};
	const candidates: Candidate[] = [];
	if (opts.type === 'andata_ritorno') {
		for (const t of picked) {
			const out = route(start, t.snap, []);
			if (out) candidates.push({ legs: [out, reverseLeg(out)], vias: [t.poi] });
		}
	} else if (opts.type === 'anello') {
		for (const t of picked) {
			const out = route(start, t.snap, []);
			const back = out && route(t.snap, start, [out]);
			if (out && back) candidates.push({ legs: [out, back], vias: [t.poi] });
		}
		const pairs: [Target, Target][] = [];
		for (let i = 0; i < picked.length; i++)
			for (let j = i + 1; j < picked.length; j++) {
				const [a, b] =
					picked[i].time <= picked[j].time ? [picked[i], picked[j]] : [picked[j], picked[i]];
				if (haversineM(a.poi.lon, a.poi.lat, b.poi.lon, b.poi.lat) / 1000 <= PAIR_MAX_KM)
					pairs.push([a, b]);
			}
		pairs.sort((x, y) => y[0].rank + y[1].rank - (x[0].rank + x[1].rank));
		for (const [a, b] of pairs.slice(0, MAX_PAIRS)) {
			const l1 = route(start, a.snap, []);
			const l2 = l1 && route(a.snap, b.snap, [l1]);
			const l3 = l1 && l2 && route(b.snap, start, [l1, l2]);
			if (l1 && l2 && l3) candidates.push({ legs: [l1, l2, l3], vias: [a.poi, b.poi] });
		}
		// anelli su misura: meta, poi un passaggio scelto per arrivare al tempo voluto
		const stretch = (dest: Snap, destTime: number, vias: Poi[]) => {
			const want = target - destTime;
			if (want <= destTime * 0.3) return;
			const treeD = costTree(graph, dest, opts.maxDiff, want * 1.2 * MAX_COST_PER_MINUTE);
			for (const n of ellipseVias(graph, tree, treeD, start, dest, want)) {
				const via = snapAtNode(graph, n, opts.maxDiff);
				const l1 = via && route(start, dest, []);
				const l2 = l1 && route(dest, via!, [l1]);
				const l3 = l1 && l2 && route(via!, start, [l1, l2]);
				if (l1 && l2 && l3) candidates.push({ legs: [l1, l2, l3], vias });
			}
		};
		for (const t of picked.slice(0, MAX_STRETCHED)) stretch(t.snap, t.time, [t.poi]);
		// pochi luoghi notevoli: anche anelli senza meta, uno per direzione
		if (picked.length < 4 && !opts.wishes.length)
			for (const n of genericTargets(graph, tree, start, target * 0.4)) {
				const dest = snapAtNode(graph, n, opts.maxDiff);
				if (dest) stretch(dest, tree.time.get(n)!, []);
			}
	} else if (end) {
		const direct = route(start, end, []);
		if (direct) candidates.push({ legs: [direct], vias: [] });
		for (const t of picked) {
			const l1 = route(start, t.snap, []);
			const l2 = l1 && route(t.snap, end, [l1]);
			if (l1 && l2) candidates.push({ legs: [l1, l2], vias: [t.poi] });
		}
	}

	// 3. vincoli e qualità
	const parking = graph.pois.filter((p) => p.kind === 'k');
	const hasParking = parking.some(
		(p) => haversineM(p.lon, p.lat, opts.start.lon, opts.start.lat) <= 400
	);
	const scored: Proposal[] = [];
	const rejected: Record<string, number> = {};
	for (const c of candidates) {
		const p = evaluate(graph, c, opts, target, hasParking);
		if (typeof p === 'string') rejected[p] = (rejected[p] ?? 0) + 1;
		else scored.push(p);
	}
	scored.sort((a, b) => b.score - a.score);

	// 4. proposte diverse tra loro
	const proposals: Proposal[] = [];
	for (const p of scored) {
		if (proposals.some((q) => similarity(q.edgeLen, p.edgeLen) > 0.7)) continue;
		proposals.push(p);
		if (proposals.length >= limit) break;
	}
	let reason: string | undefined;
	if (!proposals.length)
		reason = !picked.length
			? 'Nessuna meta adatta raggiungibile con questi vincoli: allarga il tempo o la difficoltà.'
			: 'Nessun percorso rispetta tutti i vincoli: prova un tempo più ampio, un altro tipo di giro o meno desideri.';
	return {
		proposals,
		tried: candidates.length,
		reason,
		rejected,
		targets: picked.map((t) => ({
			name: t.poi.name,
			kind: t.poi.kind,
			minutes: Math.round(t.time),
			rank: Math.round(t.rank * 10) / 10
		}))
	};
}

function evaluate(
	graph: TrailGraph,
	c: Candidate,
	opts: GenOptions,
	target: number,
	hasParking: boolean
): Proposal | string {
	const stats = routeStats(c.legs);
	if (stats.minutes < opts.minMinutes) return 'troppo breve';
	if (stats.minutes > opts.maxMinutes) return 'troppo lungo';
	if (opts.maxUp != null && stats.up > opts.maxUp * 1.05) return 'troppo dislivello';
	if (opts.minUp != null && stats.up < opts.minUp * 0.95) return 'poco dislivello';
	const points = concatPoints(c.legs);
	const along = poisAlong(graph, points, 150);
	for (const w of opts.wishes)
		if (!along.some((a) => WISH_KINDS[w].includes(a.poi.kind))) return `manca: ${w}`;
	const overlap = opts.type === 'anello' ? reusedShare(c.legs) : 0;
	if (opts.type === 'anello' && overlap > 0.5) return 'anello che ripercorre l’andata'; // sarebbe un andata e ritorno

	const shares: Shares = {
		marked: shareOf(c.legs, (p) => !!(p.flags & F_MARKED)),
		road: shareOf(c.legs, (p) => (p.cls ?? 0) >= 2),
		track: shareOf(c.legs, (p) => p.cls === 1),
		issue: shareOf(c.legs, (p) => !!(p.flags & F_ISSUE)),
		lowVis: shareOf(c.legs, (p) => !!(p.flags & F_LOW_VIS)),
		overlap,
		high: highShare(points, 1800)
	};
	// luoghi: conta soprattutto la meta più bella, gli altri aggiungono poco (e il secondo lago
	// vale meno del primo)
	const weights: number[] = [];
	const kindsSeen = new Map<string, number>();
	for (const a of along) {
		const n = kindsSeen.get(a.poi.kind) ?? 0;
		kindsSeen.set(a.poi.kind, n + 1);
		weights.push((POI_WEIGHT[a.poi.kind] ?? 0) / (n + 1));
	}
	const bestPoi = Math.max(0, ...weights);
	// una cima più alta della partenza è una meta più importante (come nella scelta delle mete)
	const startEle = c.legs[0]?.points[0]?.[2] ?? 0;
	const topPeak = Math.max(
		-Infinity,
		...along.filter((a) => a.poi.kind === 'c' && a.poi.ele != null).map((a) => a.poi.ele!)
	);
	const restPoi = weights.reduce((sum, w) => sum + w, 0) - bestPoi;
	// tempo: piccolo scarto dentro la finestra chiesta, forte fuori
	const outside =
		Math.max(0, stats.minutes - opts.maxMinutes, opts.minMinutes - stats.minutes) / target;
	const winter = WINTER.has(opts.month) && !opts.snowshoes;
	const factors: Record<string, number> = {
		segnati: 40 * shares.marked,
		strade: -25 * shares.road - (opts.snowshoes ? 0 : 10) * shares.track,
		segnalazioni: -30 * shares.issue,
		visibilita: -10 * shares.lowVis,
		varieta: opts.type === 'anello' ? 20 * (1 - overlap) - 40 * Math.max(0, overlap - 0.2) : 0,
		luoghi: Math.min(20, bestPoi + 0.35 * restPoi),
		meta: Number.isFinite(topPeak) ? Math.max(0, Math.min(8, (topPeak - startEle) / 150)) : 0,
		partenza: hasParking ? 6 : 0,
		tempo: (-10 * Math.abs(stats.minutes - target)) / target - 60 * outside,
		stagione: winter ? -30 * shares.high : 0
	};
	if (opts.minUp != null && opts.maxUp != null) {
		const mid = (opts.minUp + opts.maxUp) / 2;
		factors.dislivello = (-10 * Math.abs(stats.up - mid)) / Math.max(mid, 1);
	}
	if (opts.wishes.includes('rifugio')) {
		// rifugio a metà giro: pranzo
		const total = stats.km * 1000;
		const midHut = along.some(
			(a) => a.poi.kind === 'r' && a.at > total * 0.3 && a.at < total * 0.7
		);
		factors.pranzo = midHut ? 8 : 0;
	}
	const score = Object.values(factors).reduce((s, v) => s + v, 0);
	return {
		type: opts.type,
		legs: c.legs,
		points,
		stats,
		along,
		vias: c.vias,
		shares,
		refs: refsInOrder(c.legs),
		score,
		factors,
		edgeLen: edgeLengths(c.legs),
		sun: null
	};
}

/**
 * Esposizione al sole (0 = a nord, 1 = a sud) e contributo alla qualità per la stagione: da
 * ottobre ad aprile si preferiscono i versanti soleggiati, d'estate quelli in ombra.
 */
export function exposureFactor(sun: number, month: number): number {
	if (SUMMER.has(month)) return 6 * (0.5 - sun);
	if (month === 5 || month === 9) return 0;
	return 12 * (sun - 0.5);
}

/** Riordina le proposte aggiungendo l'esposizione al sole, se calcolabile (DEM nel browser). */
export async function withExposure(
	proposals: Proposal[],
	month: number,
	sunOf: (points: RoutePoint[]) => Promise<number | null>
): Promise<Proposal[]> {
	for (const p of proposals) {
		const sun = await sunOf(p.points).catch(() => null);
		if (sun == null) continue;
		p.sun = sun;
		p.factors.esposizione = exposureFactor(sun, month);
		p.score = Object.values(p.factors).reduce((s, v) => s + v, 0);
	}
	return [...proposals].sort((a, b) => b.score - a.score);
}
