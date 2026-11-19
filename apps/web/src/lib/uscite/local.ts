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
