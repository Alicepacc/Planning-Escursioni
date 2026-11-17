// Statistiche e avvisi del percorso pianificato (SPEC §5.3): km, D+, D−, quota massima, tempo
// stimato (modello CAI, personalizzabile), difficoltà massima incontrata, tratti da segnalare.

import type { ProfilePoint } from '../data/types';
import { swissSegmentMinutes } from '../hiking/time';
import { DIFF_LABELS, F_FERRATA, F_ISSUE, F_LOW_VIS, F_MARKED, haversineM } from './graph';
import type { Leg, Part, RoutePoint } from './router';

export interface RouteStats {
	km: number;
	up: number;
	down: number;
	maxEle: number | null;
	minEle: number | null;
	/** tempo netto (modello CAI / Sentieri Svizzeri), senza fattori personali */
	minutes: number;
	maxDiff: string | null;
	freehandKm: number;
}

export type WarningKind =
	| 'mano_libera'
	| 'oltre_difficolta'
	| 'senza_segnavia'
	| 'poco_visibile'
	| 'segnalazione'
	| 'ferrata'
	| 'strada';

export interface Warning {
	kind: WarningKind;
	text: string;
	km: number;
	/** numeri dei sentieri coinvolti */
	refs: string[];
}

// stessi parametri delle schede (services/ingest, build/documents.py): passo 15 m, media mobile
// su 5 campioni, isteresi 10 m con il residuo finale, tempo su tratti di 15 m
const STEP_M = 15;
const WINDOW = 5;
const HYSTERESIS_M = 10;

export interface Resampled {
	dist: number[];
	ele: number[];
	lon: number[];
	lat: number[];
}

/** Punti ogni `STEP_M` metri lungo il percorso (posizione e quota interpolate). */
export function resampleElevations(points: RoutePoint[]): Resampled {
	const out: Resampled = { dist: [], ele: [], lon: [], lat: [] };
	if (!points.length) return out;
	const push = (d: number, p: RoutePoint) => {
		out.dist.push(d);
		out.lon.push(p[0]);
		out.lat.push(p[1]);
		out.ele.push(p[2]);
	};
	push(0, points[0]);
	let along = 0;
	let next = STEP_M;
	for (let i = 1; i < points.length; i++) {
		const [x1, y1, z1] = points[i - 1];
		const [x2, y2, z2] = points[i];
		const d = haversineM(x1, y1, x2, y2);
		while (d > 0 && next <= along + d) {
			const t = (next - along) / d;
			push(next, [x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, z1 + (z2 - z1) * t]);
			next += STEP_M;
		}
		along += d;
	}
	if (points.length > 1 && out.dist[out.dist.length - 1] < along)
		push(along, points[points.length - 1]);
	return out;
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

/** Profilo come nelle schede: [distanza m, quota m, lon, lat, minuti cumulati]. */
export function routeProfile(legs: Leg[]): ProfilePoint[] {
	const r = resampleElevations(legs.flatMap((l) => l.points));
	const smooth = movingAverage(r.ele);
	let minutes = 0;
	return r.dist.map((d, i) => {
		if (i) minutes += swissSegmentMinutes(d - r.dist[i - 1], smooth[i] - smooth[i - 1]);
		return [d, smooth[i], r.lon[i], r.lat[i], minutes];
	});
}

export function profileStats(legs: Leg[], profile: ProfilePoint[]): RouteStats {
	const eles = profile.map((p) => p[1]);
	const [up, down] = ascentDescent(eles);
	const parts = legs.flatMap((l) => l.parts);
	const diffs = parts.map((p) => p.diff).filter((d): d is number => d != null);
	return {
		km: (profile[profile.length - 1]?.[0] ?? 0) / 1000,
		up,
		down,
		maxEle: eles.length ? Math.max(...eles) : null,
		minEle: eles.length ? Math.min(...eles) : null,
		minutes: profile[profile.length - 1]?.[4] ?? 0,
		maxDiff: diffs.length ? DIFF_LABELS[Math.max(...diffs)] : null,
		freehandKm: parts.filter((p) => p.freehand).reduce((s, p) => s + p.len / 1000, 0)
	};
}

export function routeStats(legs: Leg[]): RouteStats {
	return profileStats(legs, routeProfile(legs));
}

/** Percorso inverso (per l'andata e ritorno): stessi punti e tratti, in ordine opposto. */
export function reverseLeg(leg: Leg): Leg {
	return { ...leg, points: [...leg.points].reverse(), parts: [...leg.parts].reverse() };
}

/** «300 m» sotto il chilometro, «1,2 km» sopra. */
export function lengthText(km: number): string {
	if (km < 1) return `${Math.max(10, Math.round((km * 1000) / 10) * 10)} m`;
	return `${km.toFixed(1).replace('.', ',')} km`;
}

function refsOf(parts: Part[]): string[] {
	const seen = new Set<string>();
	for (const p of parts) for (const r of p.ref.split(';')) if (r.trim()) seen.add(r.trim());
	return [...seen].slice(0, 4);
}

function trailText(refs: string[]): string {
	if (!refs.length) return '';
	return refs.length === 1 ? ` (sentiero ${refs[0]})` : ` (sentieri ${refs.join(', ')})`;
}

/** Avvisi in linea (SPEC §5.3): solo i tratti abbastanza lunghi da contare. */
export function routeWarnings(legs: Leg[], maxDiff: number): Warning[] {
	const parts = legs.flatMap((l) => l.parts);
	const pick = (pred: (p: Part) => boolean) => {
		const sel = parts.filter(pred);
		return { km: sel.reduce((s, p) => s + p.len / 1000, 0), refs: refsOf(sel) };
	};
	const out: Warning[] = [];
	const add = (
		kind: WarningKind,
		min: number,
		sel: { km: number; refs: string[] },
		text: string
	) => {
		if (sel.km > min) out.push({ kind, km: sel.km, refs: sel.refs, text });
	};

	const free = pick((p) => p.freehand);
	add(
		'mano_libera',
		0.05,
		free,
		`${lengthText(free.km)} a mano libera: fuori dai sentieri noti, difficoltà non valutata`
	);
	const over = pick((p) => p.diff != null && p.diff > maxDiff);
	const worst = Math.max(-1, ...parts.map((p) => p.diff ?? -1));
	add(
		'oltre_difficolta',
		0.02,
		over,
		`${lengthText(over.km)} del percorso sono ${DIFF_LABELS[Math.max(0, worst)]}${trailText(over.refs)}, oltre la difficoltà scelta (${DIFF_LABELS[maxDiff]})`
	);
	const ferrata = pick((p) => !!(p.flags & F_FERRATA));
	add(
		'ferrata',
		0.02,
		ferrata,
		`${lengthText(ferrata.km)} di via ferrata${trailText(ferrata.refs)}: servono imbrago, set da ferrata e casco`
	);
	const issues = pick((p) => !!(p.flags & F_ISSUE));
	add(
		'segnalazione',
		0.02,
		issues,
		`${lengthText(issues.km)} su sentieri con una segnalazione aperta nel catasto CAI${trailText(issues.refs)}: percorribili in parte o non percorribili, verifica prima di partire`
	);
	const lowVis = pick((p) => !!(p.flags & F_LOW_VIS));
	add(
		'poco_visibile',
		0.05,
		lowVis,
		`${lengthText(lowVis.km)} di traccia poco visibile sul terreno`
	);
	const unmarked = pick((p) => !p.freehand && p.cls === 0 && !(p.flags & F_MARKED));
	add(
		'senza_segnavia',
		0.3,
		unmarked,
		`${lengthText(unmarked.km)} di sentiero senza segnavia ufficiale: orientamento a cura tua`
	);
	const road = pick((p) => p.cls === 3);
	add('strada', 0.3, road, `${lengthText(road.km)} su strade con traffico`);
	return out;
}
