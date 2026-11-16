// Stima dei tempi di percorrenza (SPEC §8). Stesse formule di
// services/ingest/src/cordata_ingest/timing.py: i due moduli condividono i casi di test.

/**
 * Coefficienti C0…C15 del modello CAI / Sentieri Svizzeri: minuti per km di distanza
 * orizzontale in funzione della pendenza in percento. Provenienza e verifica contro il
 * diagramma ufficiale: docs/decisions/0007-modelli-dei-tempi.md.
 */
export const SWISS_COEFFICIENTS = [
	14.271, 3.6992e-1, 2.5922e-2, -1.4384e-3, 3.2105e-5, 8.1542e-6, -9.0261e-8, -2.0757e-8,
	1.0192e-10, 2.8588e-11, -5.7466e-14, -2.1842e-14, 1.5176e-17, 8.6894e-18, -1.3584e-21, -1.4026e-21
] as const;

/** Oltre ±40% il manuale svizzero prevede una stima sul terreno: la pendenza viene limitata. */
export const SWISS_MAX_SLOPE_PCT = 40;

/** Minuti per km di distanza orizzontale alla pendenza data (percento, + = salita). */
export function swissMinutesPerKm(slopePct: number): number {
	const s = Math.max(-SWISS_MAX_SLOPE_PCT, Math.min(SWISS_MAX_SLOPE_PCT, slopePct));
	let total = 0;
	for (let i = SWISS_COEFFICIENTS.length - 1; i >= 0; i--)
		total = total * s + SWISS_COEFFICIENTS[i];
	return total;
}

/** Tempo netto (minuti) di un tratto con distanza orizzontale e dislivello in metri. */
export function swissSegmentMinutes(horizontalM: number, heightDiffM: number): number {
	if (horizontalM <= 0) return 0;
	return (horizontalM / 1000) * swissMinutesPerKm((100 * heightDiffM) / horizontalM);
}

export interface PersonalFactors {
	/** allenamento: 0,7 (molto allenato) … 1,4 (poco allenato) */
	fitness?: number;
	/** gruppo: ≥ 1 (es. 1,5 con bambini) */
	group?: number;
	/** soste: ≥ 1 (SPEC §8: +15-20%) */
	stops?: number;
}

/** Applica i fattori personali al tempo netto (SPEC §8). */
export function personalMinutes(
	netMinutes: number,
	{ fitness = 1, group = 1, stops = 1 }: PersonalFactors = {}
): number {
	if (fitness < 0.7 || fitness > 1.4)
		throw new RangeError('fattore di allenamento fuori da 0,7-1,4');
	if (group < 1 || stops < 1) throw new RangeError('gruppo e soste non possono ridurre il tempo');
	return netMinutes * fitness * group * stops;
}

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

/** Come `formatHours`, partendo dai minuti. */
export function formatMinutes(minutes: number, roundToMin = 5): string {
	return formatHours(minutes / 60, roundToMin);
}
