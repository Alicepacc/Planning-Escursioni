// Client del servizio delle uscite di gruppo (services/outings, ADR 0014).
// L'indirizzo del servizio arriva da VITE_USCITE_API al momento della build: senza, le pagine
// delle uscite dicono che il servizio non è ancora attivo.

import { startAuthentication, startRegistration } from '@simplewebauthn/browser';

export const API: string = (import.meta.env.VITE_USCITE_API ?? '').replace(/\/$/, '');
export const SERVICE_ON = API !== '';

const TOKEN_KEY = 'cordata.sessione';

export interface Utente {
	id: string;
	nome: string;
}

export interface Uscita {
	id: string;
	titolo: string;
	itinerario: string | null;
	ritrovo_quando: string;
	ritrovo_luogo: string;
	ritrovo_lon: number | null;
	ritrovo_lat: number | null;
	mezzi: string | null;
	posti: number | null;
	iscrizioni_entro: string | null;
	difficolta: string | null;
	requisiti: string | null;
	attrezzatura: string[];
	note: string | null;
	visibilita: 'link' | 'contatti' | 'pubblica';
	stato: 'aperta' | 'annullata' | 'rinviata';
	rinviata_a: string | null;
	organizzatore: string;
	organizzatore_nome: string;
	confermati: number;
	in_attesa: number;
	iscrizioni_aperte: boolean;
	mio_stato: 'confermato' | 'attesa' | 'rinunciato' | null;
	sono_organizzatore: boolean;
	partecipanti?: { utente: string; nome: string; stato: string }[];
	annunci: { id: string; testo: string; creato: string }[];
	avvertenza: string;
}

export type NuovaUscita = Partial<
	Pick<
		Uscita,
		| 'titolo'
		| 'itinerario'
		| 'ritrovo_quando'
		| 'ritrovo_luogo'
		| 'ritrovo_lon'
		| 'ritrovo_lat'
		| 'mezzi'
		| 'posti'
		| 'iscrizioni_entro'
		| 'difficolta'
		| 'requisiti'
		| 'attrezzatura'
		| 'note'
		| 'visibilita'
	>
>;

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

// la sessione resta nel browser: se lo spazio locale non è disponibile, vale solo per la visita
let memoryToken: string | null = null;

export function getToken(): string | null {
	try {
		return localStorage.getItem(TOKEN_KEY) ?? memoryToken;
	} catch {
		return memoryToken;
	}
}

function setToken(token: string | null) {
	memoryToken = token;
	try {
		if (token) localStorage.setItem(TOKEN_KEY, token);
		else localStorage.removeItem(TOKEN_KEY);
	} catch {
		// spazio locale non disponibile (navigazione privata): resta in memoria
	}
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
	if (!SERVICE_ON) throw new ApiError(503, 'Il servizio delle uscite non è ancora attivo.');
	const headers: Record<string, string> = {};
	const token = getToken();
	if (token) headers.Authorization = `Bearer ${token}`;
	if (body !== undefined) headers['Content-Type'] = 'application/json';
	let res: Response;
	try {
		res = await fetch(API + path, {
			method,
			headers,
			body: body === undefined ? undefined : JSON.stringify(body)
		});
	} catch {
		throw new ApiError(0, 'Servizio non raggiungibile: controlla la connessione e riprova.');
	}
	const data = (await res.json().catch(() => ({}))) as T & { errore?: string };
	if (!res.ok) {
		if (res.status === 401) setToken(null);
		throw new ApiError(res.status, data.errore ?? `Errore ${res.status}`);
	}
	return data;
}

export async function me(): Promise<Utente | null> {
	if (!SERVICE_ON || !getToken()) return null;
	try {
		return (await call<{ utente: Utente }>('GET', '/api/io')).utente;
	} catch {
		return null;
	}
}

/** Nuovo account: un nome e una passkey creata dal dispositivo (impronta, volto, PIN). */
export async function register(nome: string): Promise<Utente> {
	const { sfida_id, opzioni } = await call<{
		sfida_id: string;
		opzioni: Parameters<typeof startRegistration>[0]['optionsJSON'];
	}>('POST', '/api/accesso/registrazione/opzioni', { nome });
	const risposta = await startRegistration({ optionsJSON: opzioni });
	const res = await call<{ token: string; utente: Utente }>(
		'POST',
		'/api/accesso/registrazione/verifica',
		{ sfida_id, nome, risposta }
	);
	setToken(res.token);
	return res.utente;
}

/** Accesso con una passkey già creata su questo dispositivo (o sincronizzata). */
export async function login(): Promise<Utente> {
	const { sfida_id, opzioni } = await call<{
		sfida_id: string;
		opzioni: Parameters<typeof startAuthentication>[0]['optionsJSON'];
	}>('POST', '/api/accesso/opzioni', {});
	const risposta = await startAuthentication({ optionsJSON: opzioni });
	const res = await call<{ token: string; utente: Utente }>('POST', '/api/accesso/verifica', {
		sfida_id,
		risposta
	});
	setToken(res.token);
	return res.utente;
}

export async function logout(): Promise<void> {
	await call('POST', '/api/accesso/esci').catch(() => undefined);
	setToken(null);
}

export const createOuting = (data: NuovaUscita) =>
	call<{ id: string; invito: string }>('POST', '/api/uscite', data);
export const getOuting = (id: string, t: string | null) =>
	call<Uscita>(
		'GET',
		`/api/uscite/${encodeURIComponent(id)}${t ? `?t=${encodeURIComponent(t)}` : ''}`
	);
export const joinOuting = (id: string, t: string | null) =>
	call<{ stato: string }>('POST', `/api/uscite/${encodeURIComponent(id)}/partecipa`, { t });
export const leaveOuting = (id: string) =>
	call<{ stato: string; promossi: string[] }>(
		'POST',
		`/api/uscite/${encodeURIComponent(id)}/rinuncia`
	);
export const setOutingStatus = (id: string, stato: string, rinviata_a?: string) =>
	call('POST', `/api/uscite/${encodeURIComponent(id)}/stato`, { stato, rinviata_a });
export const setParticipant = (id: string, utente: string, stato: 'confermato' | 'attesa') =>
	call('POST', `/api/uscite/${encodeURIComponent(id)}/partecipanti/${encodeURIComponent(utente)}`, {
		stato
	});
export const announce = (id: string, testo: string) =>
	call('POST', `/api/uscite/${encodeURIComponent(id)}/annunci`, { testo });
export const myOutings = () =>
	call<{
		uscite: {
			id: string;
			titolo: string;
			ritrovo_quando: string;
			stato: string;
			organizzo: number;
			mio_stato: string;
		}[];
	}>('GET', '/api/uscite');

// notifiche push (ADR 0014): chiave pubblica VAPID e iscrizione del browser
export const pushKey = () => call<{ chiave: string }>('GET', '/api/notifiche/chiave');
export const savePush = (sub: PushSubscriptionJSON) => call('POST', '/api/notifiche', sub);
export const removePush = (endpoint: string) =>
	call('POST', '/api/notifiche/rimuovi', { endpoint });

// elenchi: uscite pubbliche dei prossimi 30 giorni (senza accesso) e proposte dei contatti
export interface UscitaInElenco {
	id: string;
	titolo: string;
	itinerario: string | null;
	ritrovo_quando: string;
	ritrovo_luogo: string;
	ritrovo_lon: number | null;
	ritrovo_lat: number | null;
	difficolta: string | null;
	posti: number | null;
	confermati: number;
	stato: 'aperta' | 'rinviata';
}
export const publicOutings = () =>
	call<{ uscite: UscitaInElenco[]; avvertenza: string }>('GET', '/api/uscite/pubbliche');
export const contactOutings = () =>
	call<{ uscite: UscitaInElenco[] }>('GET', '/api/uscite/contatti');
