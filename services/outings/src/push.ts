// Notifiche Web Push senza librerie: cifratura del contenuto (RFC 8291, aes128gcm) e firma
// VAPID (RFC 8292) con WebCrypto. La chiave privata VAPID è un segreto di Cloudflare
// (VAPID_PRIVATE_JWK), mai nel repository.

import { base64url } from './util';

export interface PushEnv {
	DB: D1Database;
	VAPID_PRIVATE_JWK?: string;
	VAPID_SUBJECT?: string;
}

export interface Subscription {
	endpoint: string;
	p256dh: string;
	auth: string;
}

export interface Message {
	titolo: string;
	testo: string;
	/** pagina da aprire toccando la notifica */
	url?: string;
}

const enc = new TextEncoder();
const utf8 = (text: string): Uint8Array<ArrayBuffer> => new Uint8Array(enc.encode(text));

export function fromBase64url(s: string): Uint8Array<ArrayBuffer> {
	const b64 = s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4);
	return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

function concat(...parts: Uint8Array[]): Uint8Array<ArrayBuffer> {
	const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
	let i = 0;
	for (const p of parts) {
		out.set(p, i);
		i += p.length;
	}
	return out;
}

async function hkdf(salt: Uint8Array<ArrayBuffer>, ikm: Uint8Array<ArrayBuffer>, info: Uint8Array<ArrayBuffer>, bytes: number) {
	const key = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits']);
	const bits = await crypto.subtle.deriveBits({ name: 'HKDF', hash: 'SHA-256', salt, info }, key, bytes * 8);
	return new Uint8Array(bits);
}

/**
 * Cifra `payload` per un'iscrizione (RFC 8291): chiave effimera ECDH P-256, segreto `auth` del
 * browser, un solo record aes128gcm. `salt` e chiave effimera si possono passare per i test.
 */
export async function encrypt(
	sub: Pick<Subscription, 'p256dh' | 'auth'>,
	payload: Uint8Array,
	options: { salt?: Uint8Array<ArrayBuffer>; ephemeral?: CryptoKeyPair } = {}
): Promise<Uint8Array<ArrayBuffer>> {
	const uaPublic = fromBase64url(sub.p256dh);
	const authSecret = fromBase64url(sub.auth);
	const ephemeral =
		options.ephemeral ??
		((await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, [
			'deriveBits'
		])) as CryptoKeyPair);
	const asPublic = new Uint8Array((await crypto.subtle.exportKey('raw', ephemeral.publicKey)) as ArrayBuffer);
	const uaKey = await crypto.subtle.importKey('raw', uaPublic, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
	const ecdh = new Uint8Array(
		await crypto.subtle.deriveBits(
			// i tipi dei Workers chiamano `$public` il campo `public` dello standard WebCrypto
			{ name: 'ECDH', public: uaKey, $public: uaKey } as unknown as SubtleCryptoDeriveKeyAlgorithm,
			ephemeral.privateKey,
			256
		)
	);
	const ikm = await hkdf(authSecret, ecdh, concat(utf8('WebPush: info\0'), uaPublic, asPublic), 32);
	const salt = options.salt ?? crypto.getRandomValues(new Uint8Array(16));
	const cek = await hkdf(salt, ikm, utf8('Content-Encoding: aes128gcm\0'), 16);
	const nonce = await hkdf(salt, ikm, utf8('Content-Encoding: nonce\0'), 12);
	const key = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
	// un solo record: contenuto seguito dal delimitatore 0x02, senza riempimento
	const cipher = new Uint8Array(
		await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, key, concat(payload, new Uint8Array([2])))
	);
	const header = new Uint8Array(21);
	header.set(salt, 0);
	new DataView(header.buffer).setUint32(16, 4096);
	header[20] = asPublic.length;
	return concat(header, asPublic, cipher);
}

/** Intestazione `Authorization: vapid t=…, k=…` per l'origine del servizio push (RFC 8292). */
export async function vapidAuthorization(endpoint: string, jwkJson: string, subject: string): Promise<string> {
	const jwk = JSON.parse(jwkJson) as JsonWebKey;
	const key = await crypto.subtle.importKey('jwk', jwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
	const header = base64url(enc.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
	const claims = base64url(
		enc.encode(
			JSON.stringify({
				aud: new URL(endpoint).origin,
				exp: Math.floor(Date.now() / 1000) + 12 * 3600,
				sub: subject
			})
		)
	);
	const signature = new Uint8Array(
		await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, enc.encode(`${header}.${claims}`))
	);
	return `vapid t=${header}.${claims}.${base64url(signature)}, k=${publicKeyFromJwk(jwk)}`;
}

/** Chiave pubblica VAPID (65 byte, base64url) da dare al browser come `applicationServerKey`. */
export function publicKeyFromJwk(jwk: JsonWebKey): string {
	return base64url(concat(new Uint8Array([4]), fromBase64url(jwk.x!), fromBase64url(jwk.y!)));
}

/**
 * Manda il messaggio a tutte le iscrizioni push delle persone indicate. Le iscrizioni scadute
 * (404/410) si cancellano. Senza chiave VAPID non manda nulla: il servizio funziona lo stesso.
 */
export async function notify(
	env: PushEnv,
	utenti: string[],
	message: Message,
	fetcher: typeof fetch = fetch
): Promise<number> {
	if (!env.VAPID_PRIVATE_JWK || !utenti.length) return 0;
	const placeholders = utenti.map(() => '?').join(', ');
	const { results } = await env.DB.prepare(
		`SELECT endpoint, p256dh, auth FROM notifiche_push WHERE utente IN (${placeholders})`
	)
		.bind(...utenti)
		.all<Subscription>();
	const payload = enc.encode(JSON.stringify(message));
	let sent = 0;
	for (const sub of results) {
		try {
			const res = await fetcher(sub.endpoint, {
				method: 'POST',
				headers: {
					Authorization: await vapidAuthorization(
						sub.endpoint,
						env.VAPID_PRIVATE_JWK,
						env.VAPID_SUBJECT ?? 'https://alicepacc.github.io/Planning-Escursioni/'
					),
					'Content-Encoding': 'aes128gcm',
					'Content-Type': 'application/octet-stream',
					TTL: String(24 * 3600),
					Urgency: 'normal'
				},
				body: await encrypt(sub, payload)
			});
			if (res.status === 404 || res.status === 410) {
				await env.DB.prepare('DELETE FROM notifiche_push WHERE endpoint = ?').bind(sub.endpoint).run();
			} else if (res.ok) {
				sent += 1;
			} else {
				// 400/401/403: firma VAPID o cifratura rifiutate; 413: troppo lungo; 429: troppe richieste
				console.warn('push rifiutata', new URL(sub.endpoint).host, res.status);
			}
		} catch (err) {
			console.error('push non inviata', err);
		}
	}
	return sent;
}
