// Statistiche e avvisi del percorso pianificato (SPEC §5.3): km, D+, D−, quota massima, tempo
// stimato (modello CAI, personalizzabile), difficoltà massima incontrata, tratti da segnalare.

import { swissSegmentMinutes } from '../hiking/time';
import { DIFF_LABELS, F_ISSUE, F_LOW_VIS, F_MARKED, haversineM } from './graph';
import type { Leg, RoutePoint } from './router';

export interface RouteStats {
	km: number;
	up: number;
	down: number;
	maxEle: number | null;
	minEle: number | null;
	minutes: number;
	maxDiff: string | null;
	freehandKm: number;
}

export interface Warning {
	kind: 'mano_libera' | 'senza_segnavia' | 'poco_visibile' | 'segnalazione' | 'strada';
	text: string;
	km: number;
}

// stessi parametri delle schede (services/ingest, build/documents.py): passo 15 m, media mobile
// su 5 campioni, isteresi 10 m con il residuo finale, tempo su tratti di 15 m
const STEP_M = 15;
const WINDOW = 5;
const HYSTERESIS_M = 10;

/** Quote ogni `STEP_M` metri lungo il percorso (interpolate tra i punti). */
export function resampleElevations(points: RoutePoint[]): { dist: number[]; ele: number[] } {
	const dist = [0];
	const ele = [points[0]?.[2] ?? 0];
	let along = 0;
	let next = STEP_M;
	for (let i = 1; i < points.length; i++) {
		const [x1, y1, z1] = points[i - 1];
		const [x2, y2, z2] = points[i];
		const d = haversineM(x1, y1, x2, y2);
		while (d > 0 && next <= along + d) {
			const t = (next - along) / d;
			dist.push(next);
			ele.push(z1 + (z2 - z1) * t);
			next += STEP_M;
		}
		along += d;
	}
	if (points.length > 1 && dist[dist.length - 1] < along) {
		dist.push(along);
		ele.push(points[points.length - 1][2]);
	}
	return { dist, ele };
}

/** Media mobile centrata, simmetrica ai bordi (come geo/elevation.py). */
export function movingAverage(values: number[], window = WINDOW): number[] {
	if (window <= 1 || values.length < 3) return [...values];
	const half = Math.floor(window / 2);
	return values.map((_, i) => {
		const h = Math.min(half, i, values.length - 1 - i);
		let sum = 0;
		for (let j = i - h; j <= i + h; j++) sum += values[j];
		return sum / (2 * h + 1);
	});
}

/** Salita e discesa con isteresi e residuo finale (come geo/elevation.py). */
export function ascentDescent(values: number[], threshold = HYSTERESIS_M): [number, number] {
	let up = 0;
	let down = 0;
	if (!values.length) return [0, 0];
	let ref = values[0];
	for (const v of values.slice(1)) {
		const diff = v - ref;
		if (diff >= threshold) {
			up += diff;
			ref = v;
		} else if (diff <= -threshold) {
			down -= diff;
			ref = v;
		}
	}
	const tail = values[values.length - 1] - ref;
	if (tail > 0) up += tail;
	else down -= tail;
	return [up, down];
}

export function routeStats(legs: Leg[], personalFactor = 1): RouteStats {
	const points: RoutePoint[] = legs.flatMap((l) => l.points);
	const { dist, ele } = resampleElevations(points);
	const smooth = movingAverage(ele);
	const [up, down] = ascentDescent(smooth);
	const km = (dist[dist.length - 1] ?? 0) / 1000;
	let minutes = 0;
	for (let i = 1; i < dist.length; i++)
		minutes += swissSegmentMinutes(dist[i] - dist[i - 1], smooth[i] - smooth[i - 1]);
	const eles = smooth;
	const diffs = legs
		.flatMap((l) => l.parts)
		.map((p) => p.diff)
		.filter((d): d is number => d != null);
	const freehandKm = legs
		.flatMap((l) => l.parts)
		.filter((p) => p.freehand)
		.reduce((s, p) => s + p.len / 1000, 0);
	return {
		km,
		up,
		down,
		maxEle: eles.length ? Math.max(...eles) : null,
		minEle: eles.length ? Math.min(...eles) : null,
		minutes: minutes * personalFactor,
		maxDiff: diffs.length ? DIFF_LABELS[Math.max(...diffs)] : null,
		freehandKm
	};
}

/** Avvisi in linea (SPEC §5.3): solo i tratti abbastanza lunghi da contare. */
export function routeWarnings(legs: Leg[], maxDiff: number): Warning[] {
	const sum = (pred: (p: Leg['parts'][number]) => boolean) =>
		legs
			.flatMap((l) => l.parts)
			.filter(pred)
			.reduce((s, p) => s + p.len / 1000, 0);
	const out: Warning[] = [];
	const free = sum((p) => p.freehand);
	if (free > 0.05)
		out.push({
			kind: 'mano_libera',
			text: `${free.toFixed(1).replace('.', ',')} km a mano libera: fuori dai sentieri noti, difficoltà non valutata`,
			km: free
		});
	const over = sum((p) => p.diff != null && p.diff > maxDiff);
	if (over > 0.05)
		out.push({
			kind: 'strada',
			text: `${over.toFixed(1).replace('.', ',')} km oltre la difficoltà scelta`,
			km: over
		});
	const unmarked = sum((p) => !p.freehand && p.cls === 0 && !(p.flags & F_MARKED));
	if (unmarked > 0.3)
		out.push({
			kind: 'senza_segnavia',
			text: `${unmarked.toFixed(1).replace('.', ',')} km di sentiero senza segnavia ufficiale`,
			km: unmarked
		});
	const lowVis = sum((p) => !!(p.flags & F_LOW_VIS));
	if (lowVis > 0.05)
		out.push({
			kind: 'poco_visibile',
			text: `${lowVis.toFixed(1).replace('.', ',')} km di traccia poco visibile`,
			km: lowVis
		});
	const issues = sum((p) => !!(p.flags & F_ISSUE));
	if (issues > 0.05)
		out.push({
			kind: 'segnalazione',
			text: `${issues.toFixed(1).replace('.', ',')} km su sentieri segnalati come non percorribili o percorribili in parte (catasto CAI)`,
			km: issues
		});
	const road = sum((p) => p.cls === 3);
	if (road > 0.3)
		out.push({
			kind: 'strada',
			text: `${road.toFixed(1).replace('.', ',')} km su strade con traffico`,
			km: road
		});
	return out;
}
