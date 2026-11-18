// Sentieri del catasto come livello della mappa (ADR 0012): l'elenco dei sentieri si scarica
// solo al primo tocco su un sentiero, per mostrarne le informazioni.

import { generatedAsset } from './paths';
import type { TrailIndexEntry, TrailWayProps } from './types';

let index: Promise<Map<string, TrailIndexEntry>> | undefined;

export function loadTrailIndex(): Promise<Map<string, TrailIndexEntry>> {
	index ??= fetch(generatedAsset('data/sentieri/index.json'))
		.then((r) => (r.ok ? r.json() : { trails: [] }))
		.then((d: { trails: TrailIndexEntry[] }) => new Map(d.trails.map((t) => [t.id, t] as const)))
		.catch(() => {
			index = undefined; // riprova al prossimo tocco
			return new Map<string, TrailIndexEntry>();
		});
	return index;
}

/** Identificativi OSM2CAI dei tratti toccati (senza doppioni, nell'ordine). */
export function trailIds(ways: TrailWayProps[]): string[] {
	const out: string[] = [];
	for (const w of ways)
		for (const id of (w.cai ?? '').split(',').map((x) => x.trim()))
			if (id && !out.includes(id)) out.push(id);
	return out;
}

/** Segnalazione da mettere in evidenza (non per «sconosciuto» o «percorribile»). */
export function issueWarning(status: string | null | undefined): string | null {
	if (!status) return null;
	const s = status.toLowerCase();
	if (s.includes('non percorribile')) return 'Segnalato come non percorribile nel catasto CAI';
	if (s.includes('parzialmente'))
		return 'Segnalato come percorribile solo in parte nel catasto CAI';
	return null;
}
