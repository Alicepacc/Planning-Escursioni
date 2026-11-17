// Salvataggio locale (SPEC §5.3): l'ultimo piano si riapre da solo; i piani salvati finiscono
// nella stessa lista «Salvati» delle schede (chiave cordata:salvati). Solo nel browser.

const LAST = 'cordata:piano';
const SAVED = 'cordata:salvati';
const PACE = 'cordata:passo';

export interface SavedEntry {
	key: string;
	title: string;
	href: string;
}

export interface Pace {
	/** allenamento: 0,7 (molto allenato) … 1,4 (poco allenato) */
	fitness: number;
	/** soste: 1, 1,15 o 1,2 (SPEC §8) */
	stops: number;
	/** gruppo: 1, 1,25 o 1,5 con bambini */
	group: number;
}

export const DEFAULT_PACE: Pace = { fitness: 1, stops: 1, group: 1 };

function read<T>(key: string, fallback: T): T {
	try {
		const raw = localStorage.getItem(key);
		return raw == null ? fallback : (JSON.parse(raw) as T);
	} catch {
		return fallback;
	}
}

function write(key: string, value: unknown): boolean {
	try {
		localStorage.setItem(key, JSON.stringify(value));
		return true;
	} catch {
		return false;
	}
}

/** Query dell'ultimo piano aperto (senza «?»), o stringa vuota. */
export function loadLast(): string {
	const v = read<unknown>(LAST, '');
	return typeof v === 'string' ? v : '';
}

export function saveLast(query: string): void {
	write(LAST, query);
}

/** Chiave stabile di un piano: dipende dai punti e dalle opzioni, non dal nome. */
export function planKey(query: string): string {
	const q = new URLSearchParams(query);
	q.delete('n');
	let h = 5381;
	for (const c of q.toString()) h = ((h * 33) ^ c.charCodeAt(0)) >>> 0;
	return `piano:${h.toString(36)}`;
}

export function savedList(): SavedEntry[] {
	const v = read<unknown>(SAVED, []);
	return Array.isArray(v) ? (v as SavedEntry[]).filter((e) => e && typeof e.key === 'string') : [];
}

export function isSaved(key: string): boolean {
	return savedList().some((e) => e.key === key);
}

/** Salva o toglie dai salvati; restituisce il nuovo stato, o null se il browser non salva. */
export function toggleSaved(entry: SavedEntry): boolean | null {
	const list = savedList();
	const was = list.some((e) => e.key === entry.key);
	const next = list.filter((e) => e.key !== entry.key);
	if (!was) next.unshift(entry);
	return write(SAVED, next.slice(0, 100)) ? !was : null;
}

export function loadPace(): Pace {
	const v = read<Partial<Pace>>(PACE, {});
	const ok = (x: unknown, lo: number, hi: number, d: number) =>
		typeof x === 'number' && x >= lo && x <= hi ? x : d;
	return {
		fitness: ok(v.fitness, 0.7, 1.4, 1),
		stops: ok(v.stops, 1, 1.5, 1),
		group: ok(v.group, 1, 2, 1)
	};
}

export function savePace(p: Pace): void {
	write(PACE, p);
}
