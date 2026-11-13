// Stima dei tempi di percorrenza (SPEC §8). Stessa formula di
// services/ingest/src/cordata_ingest/timing.py: i due moduli condividono la fixture golden.

export interface DinOptions {
	ascentRateMPerH?: number;
	descentRateMPerH?: number;
	flatSpeedKmPerH?: number;
}

/**
 * Tempo di cammino netto in ore secondo DIN 33466 (usata da DAV/AVS): 300 m/h in salita,
 * 500 m/h in discesa, 4 km/h in orizzontale; il maggiore tra tempo orizzontale e verticale
 * più metà del minore.
 */
export function din33466Hours(
	distanceKm: number,
	ascentM: number,
	descentM: number,
	{ ascentRateMPerH = 300, descentRateMPerH = 500, flatSpeedKmPerH = 4 }: DinOptions = {}
): number {
	const horizontal = distanceKm / flatSpeedKmPerH;
	const vertical = ascentM / ascentRateMPerH + descentM / descentRateMPerH;
	return Math.max(horizontal, vertical) + Math.min(horizontal, vertical) / 2;
}

/** Formatta le ore come `h:mm`, arrotondando ai minuti indicati (default 5). */
export function formatHours(hours: number, roundToMin = 5): string {
	const minutes = Math.round((hours * 60) / roundToMin) * roundToMin;
	return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`;
}
