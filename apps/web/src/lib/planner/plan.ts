// Piano del planner (SPEC §5.3): punti scelti dall'utente e, per ogni tratto tra due punti, il
// modo («r» sul sentiero, con il routing; «f» a mano libera, con eventuali punti intermedi da una
// traccia importata). Tutto lo stato sta nell'URL: link condivisibile, Indietro = annulla.

export interface PlanPoint {
	lon: number;
	lat: number;
}

/** r: agganciato ai sentieri (routing); f: a mano libera */
export type LegMode = 'r' | 'f';

export interface Plan {
	points: PlanPoint[];
	/** modo del tratto da points[i] a points[i + 1] */
	modes: LegMode[];
	/** punti intermedi dei tratti a mano libera (traccia importata), null se diretto */
	shapes: (PlanPoint[] | null)[];
	/** difficoltà massima ammessa: 0 T, 1 E, 2 EE, 3 EEA */
	maxDiff: number;
	/** andata e ritorno: il ritorno ripercorre l'andata */
	ar: boolean;
	name: string;
}

export const DEFAULT_MAX_DIFF = 1;
const PRECISION = 1e5; // 1e-5° ≈ 1 m

/** Punto arrotondato alla precisione dell'URL: il piano in memoria e quello del link coincidono. */
export function rounded(p: PlanPoint): PlanPoint {
	return {
		lon: Math.round(p.lon * PRECISION) / PRECISION,
		lat: Math.round(p.lat * PRECISION) / PRECISION
	};
}

export function emptyPlan(maxDiff = DEFAULT_MAX_DIFF): Plan {
	return { points: [], modes: [], shapes: [], maxDiff, ar: false, name: '' };
}

// --- codifica compatta: differenze in 1e-5°, zigzag, 5 bit per carattere (base64url) ---

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const VALUE = new Map([...ALPHABET].map((c, i) => [c, i]));

function encodeNumber(v: number): string {
	let u = v < 0 ? ~(v << 1) : v << 1;
	let out = '';
	while (u >= 32) {
		out += ALPHABET[(u & 31) | 32];
		u >>>= 5;
	}
	return out + ALPHABET[u];
}

export function encodePoints(points: PlanPoint[]): string {
	let px = 0;
	let py = 0;
	let out = '';
	for (const p of points) {
		const x = Math.round(p.lon * PRECISION);
		const y = Math.round(p.lat * PRECISION);
		out += encodeNumber(x - px) + encodeNumber(y - py);
		px = x;
		py = y;
	}
	return out;
}

export function decodePoints(text: string): PlanPoint[] {
	const values: number[] = [];
	let shift = 0;
	let acc = 0;
	for (const c of text) {
		const v = VALUE.get(c);
		if (v === undefined) throw new Error(`carattere non valido nel piano: ${c}`);
		acc |= (v & 31) << shift;
		if (v & 32) {
			shift += 5;
			continue;
		}
		values.push(acc & 1 ? ~(acc >>> 1) : acc >>> 1);
		acc = 0;
		shift = 0;
	}
	if (shift !== 0 || values.length % 2) throw new Error('piano troncato');
	const out: PlanPoint[] = [];
	let x = 0;
	let y = 0;
	for (let i = 0; i < values.length; i += 2) {
		x += values[i];
		y += values[i + 1];
		out.push({ lon: x / PRECISION, lat: y / PRECISION });
	}
	return out;
}

/** Parametri dell'URL: p punti, f tratti a mano libera, s forme, d difficoltà, ar, n nome. */
export function planToParams(plan: Plan): URLSearchParams {
	const q = new URLSearchParams();
	if (!plan.points.length) return q;
	q.set('p', encodePoints(plan.points));
	const free = plan.modes.flatMap((m, i) => (m === 'f' ? [i] : []));
	if (free.length) q.set('f', free.join('.'));
	plan.shapes.forEach((s, i) => {
		if (s?.length && plan.modes[i] === 'f') q.append('s', `${i}.${encodePoints(s)}`);
	});
	if (plan.maxDiff !== DEFAULT_MAX_DIFF) q.set('d', String(plan.maxDiff));
	if (plan.ar) q.set('ar', '1');
	if (plan.name) q.set('n', plan.name);
	return q;
}

/** Piano dai parametri dell'URL; parametri mancanti o rovinati danno un piano vuoto o parziale. */
export function planFromParams(q: Pick<URLSearchParams, 'get' | 'getAll' | 'has'>): Plan {
	const plan = emptyPlan();
	const d = Number(q.get('d'));
	if (q.has('d') && Number.isInteger(d) && d >= 0 && d <= 3) plan.maxDiff = d;
	plan.ar = q.get('ar') === '1';
	plan.name = (q.get('n') ?? '').slice(0, 120);
	try {
		plan.points = decodePoints(q.get('p') ?? '');
	} catch {
		return plan;
	}
	const legs = Math.max(0, plan.points.length - 1);
	plan.modes = Array.from({ length: legs }, () => 'r' as LegMode);
	plan.shapes = Array.from({ length: legs }, () => null);
	for (const part of (q.get('f') ?? '').split('.')) {
		const i = Number(part);
		if (part !== '' && Number.isInteger(i) && i >= 0 && i < legs) plan.modes[i] = 'f';
	}
	for (const entry of q.getAll('s')) {
		const dot = entry.indexOf('.');
		const i = Number(entry.slice(0, dot));
		if (dot < 1 || !Number.isInteger(i) || i < 0 || i >= legs || plan.modes[i] !== 'f') continue;
		try {
			plan.shapes[i] = decodePoints(entry.slice(dot + 1));
		} catch {
			plan.shapes[i] = null;
		}
	}
	return plan;
}

// --- operazioni: restituiscono sempre un piano nuovo ---

function clone(plan: Plan): Plan {
	return {
		...plan,
		points: plan.points.map((p) => ({ ...p })),
		modes: [...plan.modes],
		shapes: plan.shapes.map((s) => (s ? s.map((p) => ({ ...p })) : null))
	};
}

export function samePoint(a: PlanPoint, b: PlanPoint): boolean {
	return (
		Math.round(a.lon * PRECISION) === Math.round(b.lon * PRECISION) &&
		Math.round(a.lat * PRECISION) === Math.round(b.lat * PRECISION)
	);
}

export function isLoop(plan: Plan): boolean {
	const n = plan.points.length;
	return n > 2 && samePoint(plan.points[0], plan.points[n - 1]);
}

export function addPoint(plan: Plan, p: PlanPoint, mode: LegMode = 'r'): Plan {
	const next = clone(plan);
	if (next.points.length) {
		next.modes.push(mode);
		next.shapes.push(null);
	}
	next.points.push(rounded(p));
	return next;
}

/** Sposta un punto; in un anello chiuso partenza e arrivo si muovono insieme. */
export function movePoint(plan: Plan, i: number, p: PlanPoint): Plan {
	const next = clone(plan);
	const loop = isLoop(plan);
	next.points[i] = rounded(p);
	if (loop && i === 0) next.points[next.points.length - 1] = rounded(p);
	if (loop && i === next.points.length - 1) next.points[0] = rounded(p);
	return next;
}

/** Inserisce un punto nel tratto `leg` (tra points[leg] e points[leg + 1]). */
export function insertPoint(plan: Plan, leg: number, p: PlanPoint): Plan {
	const next = clone(plan);
	const mode = next.modes[leg] ?? 'r';
	const shape = next.shapes[leg];
	let before: PlanPoint[] | null = null;
	let after: PlanPoint[] | null = null;
	if (shape?.length) {
		// divide la forma nel vertice più vicino al nuovo punto
		let best = 0;
		let bestD = Infinity;
		shape.forEach((s, k) => {
			const d = (s.lon - p.lon) ** 2 + (s.lat - p.lat) ** 2;
			if (d < bestD) {
				bestD = d;
				best = k;
			}
		});
		before = shape.slice(0, best);
		after = shape.slice(best + 1);
	}
	next.points.splice(leg + 1, 0, rounded(p));
	next.modes.splice(leg, 1, mode, mode);
	next.shapes.splice(leg, 1, before?.length ? before : null, after?.length ? after : null);
	return next;
}

export function removePoint(plan: Plan, i: number): Plan {
	const next = clone(plan);
	const n = next.points.length;
	if (i < 0 || i >= n) return next;
	if (isLoop(plan) && (i === 0 || i === n - 1)) {
		// togliere la partenza di un anello: la nuova partenza è il punto successivo
		next.points.splice(n - 1, 1);
		next.modes.splice(n - 2, 1);
		next.shapes.splice(n - 2, 1);
		next.points.splice(0, 1);
		next.modes.splice(0, 1);
		next.shapes.splice(0, 1);
		if (next.points.length > 1) return closeLoop(next);
		return next;
	}
	next.points.splice(i, 1);
	if (n === 1) return next;
	if (i === 0) {
		next.modes.splice(0, 1);
		next.shapes.splice(0, 1);
	} else if (i === n - 1) {
		next.modes.splice(i - 1, 1);
		next.shapes.splice(i - 1, 1);
	} else {
		// i due tratti diventano uno: resta a mano libera solo se lo erano entrambi
		const free = next.modes[i - 1] === 'f' && next.modes[i] === 'f';
		const shape = free ? [...(next.shapes[i - 1] ?? []), ...(next.shapes[i] ?? [])] : null;
		next.modes.splice(i - 1, 2, free ? 'f' : 'r');
		next.shapes.splice(i - 1, 2, shape?.length ? shape : null);
	}
	return next;
}

export function closeLoop(plan: Plan, mode: LegMode = 'r'): Plan {
	if (plan.points.length < 2 || isLoop(plan)) return plan;
	return { ...addPoint(plan, plan.points[0], mode), ar: false };
}

/** Riapre un anello togliendo il tratto di ritorno alla partenza. */
export function openLoop(plan: Plan): Plan {
	if (!isLoop(plan)) return plan;
	const next = clone(plan);
	next.points.pop();
	next.modes.pop();
	next.shapes.pop();
	return next;
}

export function reversePlan(plan: Plan): Plan {
	const next = clone(plan);
	next.points.reverse();
	next.modes.reverse();
	next.shapes = next.shapes.reverse().map((s) => (s ? s.reverse() : null));
	return next;
}

export function setAr(plan: Plan, ar: boolean): Plan {
	if (ar && isLoop(plan)) return plan;
	return { ...clone(plan), ar };
}

export function setMode(plan: Plan, leg: number, mode: LegMode): Plan {
	const next = clone(plan);
	if (leg < 0 || leg >= next.modes.length) return next;
	next.modes[leg] = mode;
	if (mode === 'r') next.shapes[leg] = null;
	return next;
}

export function setMaxDiff(plan: Plan, maxDiff: number): Plan {
	return { ...clone(plan), maxDiff };
}

export function setName(plan: Plan, name: string): Plan {
	return { ...clone(plan), name: name.slice(0, 120) };
}

function haversine(a: PlanPoint, b: PlanPoint): number {
	const r = Math.PI / 180;
	const h =
		Math.sin(((b.lat - a.lat) * r) / 2) ** 2 +
		Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(((b.lon - a.lon) * r) / 2) ** 2;
	return 2 * 6371000 * Math.asin(Math.sqrt(h));
}

/**
 * Punti ogni `spacingM` metri lungo una linea (estremi compresi): servono per aprire nel planner
 * una traccia esistente agganciandola ai sentieri.
 */
export function sampleLine(line: PlanPoint[], spacingM: number): PlanPoint[] {
	if (line.length < 2) return line.map((p) => ({ ...p }));
	const out: PlanPoint[] = [{ ...line[0] }];
	let since = 0;
	for (let i = 1; i < line.length; i++) {
		since += haversine(line[i - 1], line[i]);
		if (since >= spacingM && i < line.length - 1) {
			out.push({ ...line[i] });
			since = 0;
		}
	}
	const last = line[line.length - 1];
	// l'ultimo campione troppo vicino all'arrivo non serve
	if (out.length > 1 && haversine(out[out.length - 1], last) < spacingM / 3) out.pop();
	out.push({ ...last });
	return out;
}

/** Piano agganciato ai sentieri che segue una linea data (scheda → «Modifica nel planner»). */
export function planFromLine(
	line: PlanPoint[],
	opts: { spacingM?: number; maxDiff?: number; name?: string } = {}
): Plan {
	let plan = emptyPlan(opts.maxDiff ?? DEFAULT_MAX_DIFF);
	for (const p of sampleLine(line, opts.spacingM ?? 800)) plan = addPoint(plan, p, 'r');
	return { ...plan, name: opts.name ?? '' };
}

/** Lunghezza in linea d'aria dei tratti tra i punti (per i controlli rapidi). */
export function straightLength(points: PlanPoint[]): number {
	let total = 0;
	for (let i = 1; i < points.length; i++) total += haversine(points[i - 1], points[i]);
	return total;
}
