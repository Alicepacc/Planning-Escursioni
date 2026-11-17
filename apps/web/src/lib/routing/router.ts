// Routing nel browser (ADR 0010): A* sul tempo stimato con il modello CAI, tra due punti
// agganciati al grafo. I tratti oltre la difficoltà massima sono esclusi; le strade costano di
// più dei sentieri, e i sentieri segnati meno di quelli senza segnavia.

import { swissSegmentMinutes } from '../hiking/time';
import {
	F_ISSUE,
	F_LOW_VIS,
	F_MARKED,
	haversineM,
	type GEdge,
	type Snap,
	type TrailGraph
} from './graph';

export interface RouteOptions {
	/** 0 T, 1 E, 2 EE, 3 EEA */
	maxDiff: number;
	/** moltiplicatore del costo per arco (es. archi già usati: il generatore cerca vie diverse) */
	penalty?: Map<number, number>;
}

/** Punto del percorso: [lon, lat, quota] */
export type RoutePoint = [number, number, number];

/** Tratto omogeneo del percorso, per statistiche e avvisi. */
export interface Part {
	len: number;
	diff: number | null;
	cls: number | null;
	flags: number;
	ref: string;
	freehand: boolean;
	/** arco del grafo percorso (per tutto o in parte); assente a mano libera */
	edge?: number;
}

export interface Leg {
	points: RoutePoint[];
	parts: Part[];
	freehand: boolean;
	error?: string;
}

const MAX_VISITED = 400_000;
const CLASS_FACTOR = [1.0, 1.08, 1.3, 1.9];

/** Minuti netti di un tratto con salita e discesa note (ripartite sulla lunghezza). */
export function edgeMinutes(len: number, up: number, down: number): number {
	if (up + down <= 0) return swissSegmentMinutes(len, 0);
	const lu = (len * up) / (up + down);
	return swissSegmentMinutes(lu, up) + swissSegmentMinutes(len - lu, -down);
}

/** Tempo netto (minuti) di un arco, o di una sua parte, nella direzione data (a→b se forward). */
export function edgeTime(edge: GEdge, forward: boolean, len = edge.len, share = 1): number {
	const up = (forward ? edge.up : edge.down) * share;
	const down = (forward ? edge.down : edge.up) * share;
	return edgeMinutes(len, up, down);
}

/** Costo di un arco nella direzione data (a→b se forward): tempo × preferenze. */
export function edgeCost(edge: GEdge, forward: boolean, len = edge.len, share = 1): number {
	let factor = CLASS_FACTOR[edge.cls] ?? 1.3;
	if (edge.cls === 0 && !(edge.flags & F_MARKED)) factor *= 1.12;
	if (edge.flags & F_LOW_VIS) factor *= 1.3;
	if (edge.flags & F_ISSUE) factor *= 2;
	return edgeTime(edge, forward, len, share) * factor;
}

export class Heap {
	private items: [number, number][] = [];
	get size(): number {
		return this.items.length;
	}
	push(node: number, f: number): void {
		const a = this.items;
		a.push([node, f]);
		let i = a.length - 1;
		while (i > 0) {
			const p = (i - 1) >> 1;
			if (a[p][1] <= a[i][1]) break;
			[a[p], a[i]] = [a[i], a[p]];
			i = p;
		}
	}
	pop(): [number, number] | undefined {
		const a = this.items;
		const top = a[0];
		const last = a.pop();
		if (a.length && last) {
			a[0] = last;
			let i = 0;
			for (;;) {
				const l = 2 * i + 1;
				const r = l + 1;
				let m = i;
				if (l < a.length && a[l][1] < a[m][1]) m = l;
				if (r < a.length && a[r][1] < a[m][1]) m = r;
				if (m === i) break;
				[a[m], a[i]] = [a[i], a[m]];
				i = m;
			}
		}
		return top;
	}
}

const START = -1;
const END = -2;

interface Step {
	from: number;
	edge: number; // id dell'arco, o -1 per il tratto diretto sullo stesso arco
	forward: boolean;
}

/** Punti di un arco tra due posizioni (metri da a), nella direzione richiesta. */
export function slice(graph: TrailGraph, edge: GEdge, from: number, to: number): RoutePoint[] {
	const pts = graph.coords(edge);
	const forward = to >= from;
	const lo = Math.min(from, to);
	const hi = Math.max(from, to);
	const out: RoutePoint[] = [];
	let along = 0;
	const lerp = (p: RoutePoint, q: RoutePoint, t: number): RoutePoint => [
		p[0] + (q[0] - p[0]) * t,
		p[1] + (q[1] - p[1]) * t,
		p[2] + (q[2] - p[2]) * t
	];
	for (let i = 0; i + 1 < pts.length; i++) {
		const seg = haversineM(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]);
		const s0 = along;
		const s1 = along + seg;
		if (s1 >= lo && s0 <= hi) {
			if (!out.length)
				out.push(seg > 0 ? lerp(pts[i], pts[i + 1], Math.max(0, (lo - s0) / seg)) : pts[i]);
			if (s1 <= hi) out.push(pts[i + 1]);
			else {
				out.push(seg > 0 ? lerp(pts[i], pts[i + 1], (hi - s0) / seg) : pts[i + 1]);
				break;
			}
		}
		along = s1;
	}
	if (!out.length) out.push(pts[0]);
	return forward ? out : out.reverse();
}

function partOf(edge: GEdge, len: number): Part {
	return {
		len,
		diff: edge.diff,
		cls: edge.cls,
		flags: edge.flags,
		ref: edge.ref,
		freehand: false,
		edge: edge.id
	};
}

/** Percorso tra due punti agganciati; null se non esiste entro i limiti. */
export function routeBetween(
	graph: TrailGraph,
	from: Snap,
	to: Snap,
	opts: RouteOptions
): Leg | null {
	const pen = (id: number) => opts.penalty?.get(id) ?? 1;
	const g = new Map<number, number>([[START, 0]]);
	const prev = new Map<number, Step>();
	const open = new Heap();
	const heuristic = (lon: number, lat: number) => (haversineM(lon, lat, to.lon, to.lat) / 1000) * 9;
	open.push(START, heuristic(from.lon, from.lat));

	// uscite dal nodo virtuale di partenza: verso a e verso b lungo l'arco di partenza
	const e1 = from.edge;
	const e2 = to.edge;
	const startOut: [number, number, boolean, number][] = [
		[e1.a, from.pos, false, 1], // verso a: direzione b→a
		[e1.b, e1.len - from.pos, true, 1]
	];
	const endIn = new Map<number, [number, boolean]>([
		[e2.a, [to.pos, true]],
		[e2.b, [e2.len - to.pos, false]]
	]);
	let visited = 0;
	const closed = new Set<number>();
	while (open.size) {
		const [node] = open.pop()!;
		if (node === END) break;
		if (closed.has(node)) continue; // voce superata da una migliore
		closed.add(node);
		const gNode = g.get(node)!;
		if (++visited > MAX_VISITED) return null;
		const relax = (next: number, cost: number, step: Step, lon: number, lat: number) => {
			const ng = gNode + cost;
			if (ng < (g.get(next) ?? Infinity)) {
				g.set(next, ng);
				prev.set(next, step);
				open.push(next, ng + (next === END ? 0 : heuristic(lon, lat)));
			}
		};
		if (node === START) {
			for (const [n, len, forward] of startOut) {
				const share = e1.len > 0 ? len / e1.len : 0;
				const nn = graph.nodes.get(n)!;
				relax(
					n,
					edgeCost(e1, forward, len, share) * pen(e1.id),
					{ from: START, edge: e1.id, forward },
					nn.lon,
					nn.lat
				);
			}
			if (e1.id === e2.id) {
				const forward = to.pos >= from.pos;
				const len = Math.abs(to.pos - from.pos);
				relax(
					END,
					edgeCost(e1, forward, len, e1.len > 0 ? len / e1.len : 0) * pen(e1.id),
					{ from: START, edge: -1, forward },
					to.lon,
					to.lat
				);
			}
			continue;
		}
		const toEnd = endIn.get(node);
		if (toEnd) {
			const [len, forward] = toEnd;
			relax(
				END,
				edgeCost(e2, forward, len, e2.len > 0 ? len / e2.len : 0) * pen(e2.id),
				{ from: node, edge: e2.id, forward },
				to.lon,
				to.lat
			);
		}
		for (const id of graph.adj.get(node) ?? []) {
			const edge = graph.edges[id];
			if (edge.diff > opts.maxDiff) continue;
			const forward = edge.a === node;
			const next = forward ? edge.b : edge.a;
			const nn = graph.nodes.get(next);
			if (!nn) continue;
			relax(
				next,
				edgeCost(edge, forward) * pen(id),
				{ from: node, edge: id, forward },
				nn.lon,
				nn.lat
			);
		}
	}
	if (!prev.has(END)) return null;

	// ricostruzione
	const steps: Step[] = [];
	for (let n = END; n !== START;) {
		const step = prev.get(n)!;
		steps.push(step);
		n = step.from;
	}
	steps.reverse();
	const points: RoutePoint[] = [];
	const parts: Part[] = [];
	const push = (pts: RoutePoint[]) => {
		for (const p of pts) {
			const last = points[points.length - 1];
			if (!last || last[0] !== p[0] || last[1] !== p[1]) points.push(p);
		}
	};
	steps.forEach((step, i) => {
		const first = i === 0;
		const last = i === steps.length - 1;
		if (step.edge === -1) {
			push(slice(graph, e1, from.pos, to.pos));
			parts.push(partOf(e1, Math.abs(to.pos - from.pos)));
			return;
		}
		const edge = graph.edges[step.edge];
		let a = step.forward ? 0 : edge.len;
		let b = step.forward ? edge.len : 0;
		if (first) a = from.pos;
		if (last) b = to.pos;
		push(slice(graph, edge, a, b));
		parts.push(partOf(edge, Math.abs(b - a)));
	});
	return { points, parts, freehand: false };
}

/** Tratto «a mano libera»: linea diretta, quote interpolate tra gli estremi. */
export function freehandLeg(a: RoutePoint, b: RoutePoint): Leg {
	const len = haversineM(a[0], a[1], b[0], b[1]);
	const n = Math.max(1, Math.round(len / 50));
	const points: RoutePoint[] = [];
	for (let i = 0; i <= n; i++) {
		const t = i / n;
		points.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]);
	}
	return {
		points,
		parts: [{ len, diff: null, cls: null, flags: 0, ref: '', freehand: true }],
		freehand: true
	};
}
