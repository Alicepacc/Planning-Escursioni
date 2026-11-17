// Luoghi del grafo (cime, laghi, rifugi, bivacchi, punti panoramici, parcheggi) lungo un percorso.

import { haversineM, type Poi, type TrailGraph } from './graph';
import type { RoutePoint } from './router';

export interface PoiAlong {
	poi: Poi;
	/** metri dalla partenza al punto del percorso più vicino al luogo */
	at: number;
	/** distanza del luogo dal percorso (m) */
	dist: number;
}

/** Luoghi entro `maxM` metri dal percorso, in ordine di percorrenza, senza doppioni. */
export function poisAlong(graph: TrailGraph, points: RoutePoint[], maxM = 120): PoiAlong[] {
	if (points.length < 2) return [];
	let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
	for (const [lon, lat] of points) {
		x0 = Math.min(x0, lon);
		y0 = Math.min(y0, lat);
		x1 = Math.max(x1, lon);
		y1 = Math.max(y1, lat);
	}
	const pad = 0.003;
	const cum = [0];
	for (let i = 1; i < points.length; i++)
		cum.push(
			cum[i - 1] + haversineM(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
		);
	const out: PoiAlong[] = [];
	const seen = new Set<string>();
	for (const poi of graph.pois) {
		if (poi.lon < x0 - pad || poi.lon > x1 + pad || poi.lat < y0 - pad || poi.lat > y1 + pad)
			continue;
		const key = `${poi.kind}|${poi.name}|${poi.lon.toFixed(4)}|${poi.lat.toFixed(4)}`;
		if (seen.has(key)) continue; // lo stesso luogo può comparire in più tasselli
		let best = Infinity;
		let at = 0;
		for (let i = 0; i < points.length; i++) {
			const d = haversineM(poi.lon, poi.lat, points[i][0], points[i][1]);
			if (d < best) {
				best = d;
				at = cum[i];
			}
		}
		if (best <= maxM) {
			seen.add(key);
			out.push({ poi, at, dist: best });
		}
	}
	return out.sort((a, b) => a.at - b.at);
}
