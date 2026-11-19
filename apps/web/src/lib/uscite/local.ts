// Date leggibili e segreti dei link d'invito conservati nel browser dell'organizzatore
// (il servizio conserva solo l'hash: il link completo lo ha solo chi ha creato l'uscita).

const INVITES_KEY = 'cordata.inviti';

export function formatWhen(iso: string): string {
	return new Intl.DateTimeFormat('it-IT', {
		weekday: 'long',
		day: 'numeric',
		month: 'long',
		year: 'numeric',
		hour: '2-digit',
		minute: '2-digit'
	}).format(new Date(iso));
}

/** Da `datetime-local` (ora locale del dispositivo) a ISO. */
export function localToIso(value: string): string | undefined {
	if (!value) return undefined;
	const d = new Date(value);
	return Number.isNaN(d.getTime()) ? undefined : d.toISOString();
}

function readInvites(): Record<string, string> {
	try {
		return JSON.parse(localStorage.getItem(INVITES_KEY) ?? '{}') as Record<string, string>;
	} catch {
		return {};
	}
}

export function rememberInvite(id: string, token: string) {
	try {
		localStorage.setItem(INVITES_KEY, JSON.stringify({ ...readInvites(), [id]: token }));
	} catch {
		// spazio locale non disponibile: il link resta nella barra degli indirizzi
	}
}

export function knownInvite(id: string): string | null {
	return readInvites()[id] ?? null;
}

/** Giorno di calendario in Italia (AAAA-MM-GG) di un istante. */
export function romeDay(iso: string | Date): string {
	return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Rome' }).format(new Date(iso));
}

/**
 * Il fine settimana «di adesso» in Italia: sabato e domenica di questa settimana; se è già
 * sabato o domenica, quelli in corso.
 */
export function weekend(now = new Date()): [string, string] {
	const today = romeDay(now);
	const [y, m, d] = today.split('-').map(Number);
	const day = new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // 0 domenica … 6 sabato
	const toSaturday = day === 0 ? -1 : 6 - day;
	const sat = new Date(Date.UTC(y, m - 1, d + toSaturday));
	const sun = new Date(Date.UTC(y, m - 1, d + toSaturday + 1));
	return [sat.toISOString().slice(0, 10), sun.toISOString().slice(0, 10)];
}
