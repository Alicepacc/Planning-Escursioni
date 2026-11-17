// Piano che riproduce una linea data (proposta del generatore) con pochi punti: si parte dalle
// mete e si aggiunge un punto solo dove il percorso del planner si scosta dalla linea.

import type { RoutePoint } from '../routing/router';
import type { PlannerEngine } from './engine';
import { maxDeviationM } from './gpx-import';
import { addPoint, emptyPlan, type Plan, type PlanPoint } from './plan';

const TOLERANCE_M = 40;
const MIN_SPAN = 4; // punti della linea: sotto questa distanza non si divide più
const MAX_POINTS = 40;

/**
 * `anchors`: indici della linea da tenere comunque (partenza, mete, arrivo), in ordine crescente.
 * Restituisce un piano agganciato ai sentieri che segue la linea entro ~40 m.
 */
export async function fitLine(
	engine: PlannerEngine,
	line: RoutePoint[],
	anchors: number[],
	opts: { maxDiff: number; name: string; ar?: boolean }
): Promise<Plan> {
	const pt = (i: number): PlanPoint => ({ lon: line[i][0], lat: line[i][1] });
	const section = (a: number, b: number) =>
		line.slice(a, b + 1).map(([lon, lat]) => ({ lon, lat }));
	let idx = [...new Set([0, ...anchors, line.length - 1])].sort((a, b) => a - b);
	for (let round = 0; round < 12 && idx.length < MAX_POINTS; round++) {
		const legs = await Promise.all(
			idx.slice(1).map((b, k) => engine.leg(pt(idx[k]), pt(b), 'r', null, opts.maxDiff))
		);
		const split: number[] = [];
		legs.forEach((leg, k) => {
			const a = idx[k];
			const b = idx[k + 1];
			if (b - a < MIN_SPAN) return;
			if (leg.freehand || maxDeviationM(leg.points, section(a, b)) > TOLERANCE_M)
				split.push(Math.round((a + b) / 2));
		});
		if (!split.length) break;
		idx = [...new Set([...idx, ...split])].sort((a, b) => a - b);
	}
	let plan = emptyPlan(opts.maxDiff);
	for (const i of idx) plan = addPoint(plan, pt(i));
	return { ...plan, name: opts.name, ar: !!opts.ar };
}
