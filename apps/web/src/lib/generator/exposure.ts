// Esposizione al sole del percorso dal modello del terreno (solo nel browser): per un campione
// ogni ~250 m si stima la pendenza del versante con quattro quote a ±40 m e si guarda verso dove
// scende. 1 = versanti a sud, 0 = a nord, 0,5 = piano o esposizione neutra.

import { elevations } from '../map/dem';
import { haversineM } from '../routing/graph';
import type { RoutePoint } from '../routing/router';

const STEP_M = 250;
const D_M = 40;

/** Esposizione media da gradienti già misurati: [d quota verso est, d quota verso nord] per metro. */
export function sunFromGradients(gradients: [number, number][]): number | null {
	if (!gradients.length) return null;
	let total = 0;
	for (const [gx, gy] of gradients) {
		const slope = Math.hypot(gx, gy);
		// il terreno sale verso nord (gy > 0) → il versante guarda a sud
		total += slope < 0.09 ? 0.5 : 0.5 + 0.5 * (gy / slope) * Math.min(1, slope / 0.3);
	}
	return total / gradients.length;
}

export async function sunShare(points: RoutePoint[]): Promise<number | null> {
	const samples: [number, number][] = [];
	let since = STEP_M;
	for (let i = 0; i < points.length; i++) {
		if (i) since += haversineM(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1]);
		if (since >= STEP_M) {
			samples.push([points[i][0], points[i][1]]);
			since = 0;
		}
	}
	const queries: [number, number][] = samples.flatMap(([lon, lat]) => {
		const dLon = D_M / (111320 * Math.cos((lat * Math.PI) / 180));
		const dLat = D_M / 110950;
		return [
			[lon + dLon, lat],
			[lon - dLon, lat],
			[lon, lat + dLat],
			[lon, lat - dLat]
		] as [number, number][];
	});
	const z = await elevations(queries);
	const gradients: [number, number][] = [];
	for (let k = 0; k < samples.length; k++) {
		const [e, w, n, s] = z.slice(4 * k, 4 * k + 4);
		if (e == null || w == null || n == null || s == null) continue;
		gradients.push([(e - w) / (2 * D_M), (n - s) / (2 * D_M)]);
	}
	return sunFromGradients(gradients);
}
