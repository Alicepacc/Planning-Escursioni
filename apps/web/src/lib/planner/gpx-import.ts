// Import di una traccia GPX propria (SPEC §5.3) con aggancio facoltativo ai sentieri. La traccia
// resta nel browser: nell'URL vanno solo i punti semplificati; le quote si ricalcolano dal
// modello del terreno, come per il resto del planner.

import { haversineM } from '../routing/graph';
import type { RoutePoint } from '../routing/router';
import { addPoint, emptyPlan, rounded, setMode, type Plan, type PlanPoint } from './plan';

export interface ImportedTrack {
	name: string;
	points: PlanPoint[];
}

const num = (attrs: string, name: string) => {
	const m = attrs.match(new RegExp(`\\b${name}\\s*=\\s*["']([^"']+)["']`));
	return m ? Number(m[1]) : NaN;
};

function decodeEntities(text: string): string {
	return text
		.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&quot;/g, '"')
		.replace(/&apos;/g, "'")
		.replace(/&amp;/g, '&')
		.trim();
}

/** Punti della traccia (trkpt, altrimenti rtept) e nome; errore se il file non ne ha. */
export function parseGpx(text: string): ImportedTrack {
	if (!/<gpx[\s>]/i.test(text)) throw new Error('Il file non sembra un GPX.');
	const read = (tag: string) => {
		const out: PlanPoint[] = [];
		const re = new RegExp(`<${tag}\\b([^>]*?)(?:/>|>)`, 'g');
		for (const m of text.matchAll(re)) {
			const lat = num(m[1], 'lat');
			const lon = num(m[1], 'lon');
			if (
				Number.isFinite(lat) &&
				Number.isFinite(lon) &&
				Math.abs(lat) <= 90 &&
				Math.abs(lon) <= 180
			)
				out.push({ lon, lat });
		}
		return out;
	};
	let points = read('trkpt');
	if (points.length < 2) points = read('rtept');
	if (points.length < 2) throw new Error('Nel file non ci sono tracce né percorsi.');
	const trkName = text.match(/<trk\b[^>]*>[\s\S]*?<name>([\s\S]*?)<\/name>/);
	const metaName = text.match(/<metadata\b[^>]*>[\s\S]*?<name>([\s\S]*?)<\/name>/);
	const name = decodeEntities(trkName?.[1] ?? metaName?.[1] ?? '').slice(0, 120);
	// punti ripetuti (registrazioni ferme) non servono
	const dedup = points.filter(
		(p, i) => i === 0 || p.lon !== points[i - 1].lon || p.lat !== points[i - 1].lat
	);
	return { name, points: dedup };
}

/** Douglas–Peucker in metri (proiezione locale); restituisce gli indici tenuti. */
export function simplifyIndices(points: PlanPoint[], toleranceM: number): number[] {
	if (points.length <= 2) return points.map((_, i) => i);
	const lat0 = (points[0].lat * Math.PI) / 180;
	const kx = 111320 * Math.cos(lat0);
	const ky = 110950;
	const xy = points.map((p) => [p.lon * kx, p.lat * ky]);
	const keep = new Uint8Array(points.length);
	keep[0] = keep[points.length - 1] = 1;
	const stack: [number, number][] = [[0, points.length - 1]];
	while (stack.length) {
		const [i, j] = stack.pop()!;
		const [ax, ay] = xy[i];
		const [bx, by] = xy[j];
		const dx = bx - ax;
		const dy = by - ay;
		const l2 = dx * dx + dy * dy;
		let worst = -1;
		let worstD = toleranceM;
		for (let k = i + 1; k < j; k++) {
			const [px, py] = xy[k];
			const t = l2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0;
			const d = Math.hypot(px - (ax + dx * t), py - (ay + dy * t));
			if (d > worstD) {
				worstD = d;
				worst = k;
			}
		}
		if (worst >= 0) {
			keep[worst] = 1;
			stack.push([i, worst], [worst, j]);
		}
	}
	return [...keep].flatMap((v, i) => (v ? [i] : []));
}

function lengthM(points: PlanPoint[]): number {
	let total = 0;
	for (let i = 1; i < points.length; i++)
		total += haversineM(points[i - 1].lon, points[i - 1].lat, points[i].lon, points[i].lat);
	return total;
}

/** Indici dei punti di controllo: estremi e uno ogni `spacingM` metri. */
function controlIndices(points: PlanPoint[], spacingM: number): number[] {
	const out = [0];
	let since = 0;
	for (let i = 1; i < points.length - 1; i++) {
		since += haversineM(points[i - 1].lon, points[i - 1].lat, points[i].lon, points[i].lat);
		if (since >= spacingM) {
			out.push(i);
			since = 0;
		}
	}
	const last = points.length - 1;
	if (out.length > 1) {
		const tail = lengthM(points.slice(out[out.length - 1], last + 1));
		if (tail < spacingM / 3) out.pop();
	}
	out.push(last);
	return out;
}

export interface TrackPlan {
	plan: Plan;
	/** per ogni tratto del piano, i punti della traccia (semplificata) che copre */
	sections: PlanPoint[][];
}

const KEEP_TOLERANCE_M = 6;
const KEEP_SPACING_M = 2000;
const SNAP_SPACING_M = 600;
const LOOP_M = 50;

/**
 * Piano da una traccia: «mantieni» la riproduce a mano libera (punti di controllo ogni 2 km,
 * forma semplificata a 6 m); «aggancia» mette un punto ogni 600 m sui sentieri.
 */
export function planFromTrack(
	track: ImportedTrack,
	opts: { snap: boolean; maxDiff: number }
): TrackPlan {
	const simple = simplifyIndices(track.points, KEEP_TOLERANCE_M).map((i) => track.points[i]);
	const ctrl = controlIndices(simple, opts.snap ? SNAP_SPACING_M : KEEP_SPACING_M);
	let plan = emptyPlan(opts.maxDiff);
	const sections: PlanPoint[][] = [];
	ctrl.forEach((idx, k) => {
		plan = addPoint(plan, simple[idx], opts.snap ? 'r' : 'f');
		if (k) {
			const section = simple.slice(ctrl[k - 1], idx + 1);
			sections.push(section);
			if (!opts.snap) plan.shapes[k - 1] = section.slice(1, -1).map(rounded);
		}
	});
	// traccia ad anello: arrivo a meno di 50 m dalla partenza → stesso punto (anello del planner)
	const n = plan.points.length;
	if (n > 2) {
		const a = plan.points[0];
		const b = plan.points[n - 1];
		if (haversineM(a.lon, a.lat, b.lon, b.lat) < LOOP_M) {
			plan.points[n - 1] = { ...a };
			sections[n - 2] = [...sections[n - 2].slice(0, -1), a];
		}
	}
	return { plan: { ...plan, name: track.name }, sections };
}

/** Distanza massima (m) dei punti di `route` dalla linea `line`. */
export function maxDeviationM(route: RoutePoint[], line: PlanPoint[]): number {
	if (!route.length || line.length < 2) return 0;
	const lat0 = (line[0].lat * Math.PI) / 180;
	const kx = 111320 * Math.cos(lat0);
	const ky = 110950;
	let worst = 0;
	for (const [lon, lat] of route) {
		const px = lon * kx;
		const py = lat * ky;
		let best = Infinity;
		for (let i = 0; i + 1 < line.length; i++) {
			const ax = line[i].lon * kx;
			const ay = line[i].lat * ky;
			const dx = line[i + 1].lon * kx - ax;
			const dy = line[i + 1].lat * ky - ay;
			const l2 = dx * dx + dy * dy;
			const t = l2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0;
			best = Math.min(best, Math.hypot(px - (ax + dx * t), py - (ay + dy * t)));
		}
		worst = Math.max(worst, best);
	}
	return worst;
}

const MAX_DEVIATION_M = 60;

/**
 * Dopo l'aggancio: i tratti che il routing non riesce a far coincidere con la traccia (deviazione
 * oltre 60 m, o nessun percorso) tornano a mano libera sulla traccia originale.
 */
export function keepTrackWhereRoutingDeviates(
	tp: TrackPlan,
	legs: { points: RoutePoint[]; freehand: boolean }[]
): { plan: Plan; replaced: number } {
	let plan = tp.plan;
	let replaced = 0;
	legs.forEach((leg, i) => {
		const section = tp.sections[i];
		if (!section) return;
		if (leg.freehand || maxDeviationM(leg.points, section) > MAX_DEVIATION_M) {
			plan = setMode(plan, i, 'f');
			plan.shapes[i] = section.slice(1, -1).map(rounded);
			replaced++;
		}
	});
	return { plan, replaced };
}
