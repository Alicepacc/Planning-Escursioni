// Funzioni di servizio: identificativi casuali, hash, risposte JSON con CORS.

export interface Env {
	DB: D1Database;
	APP_ORIGIN: string;
	/** indirizzo della PWA, per i link nelle notifiche (es. …/Planning-Escursioni) */
	APP_URL: string;
	RP_ID: string;
	RP_NAME: string;
	/** segreto: chiave privata VAPID in JWK; senza, le notifiche push sono spente */
	VAPID_PRIVATE_JWK?: string;
	VAPID_SUBJECT?: string;
}

const B64URL = /[+/=]/g;

export function base64url(bytes: Uint8Array): string {
	let s = '';
	for (const b of bytes) s += String.fromCharCode(b);
	return btoa(s).replace(B64URL, (c) => (c === '+' ? '-' : c === '/' ? '_' : ''));
}

/** Segreto casuale non indovinabile (per sessioni e link d'invito). */
export function randomToken(bytes = 24): string {
	return base64url(crypto.getRandomValues(new Uint8Array(bytes)));
}

/** Identificativo breve e leggibile negli indirizzi. */
export function randomId(): string {
	return randomToken(9);
}

export async function sha256(text: string): Promise<string> {
	const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
	return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function cors(env: Env): Record<string, string> {
	return {
		'Access-Control-Allow-Origin': env.APP_ORIGIN,
		'Access-Control-Allow-Headers': 'Authorization, Content-Type',
		'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
		Vary: 'Origin'
	};
}

export function json(env: Env, body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(env) }
	});
}

export class HttpError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

export async function readJson<T>(request: Request): Promise<T> {
	try {
		return (await request.json()) as T;
	} catch {
		throw new HttpError(400, 'Richiesta non valida: serve un corpo JSON.');
	}
}

export function nowIso(): string {
	return new Date().toISOString();
}
