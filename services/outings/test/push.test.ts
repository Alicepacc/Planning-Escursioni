import { env } from 'cloudflare:workers';
import { describe, expect, it } from 'vitest';
import { reminders } from '../src/notifiche';
import { encrypt, fromBase64url, notify, publicKeyFromJwk, vapidAuthorization } from '../src/push';
import { base64url } from '../src/util';

const enc = new TextEncoder();

async function ecdhPair(): Promise<CryptoKeyPair> {
	return (await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, [
		'deriveBits'
	])) as CryptoKeyPair;
}

async function hkdf(salt: Uint8Array, ikm: Uint8Array, info: Uint8Array, bytes: number) {
	const key = await crypto.subtle.importKey('raw', new Uint8Array(ikm), 'HKDF', false, ['deriveBits']);
	return new Uint8Array(
		await crypto.subtle.deriveBits(
			{ name: 'HKDF', hash: 'SHA-256', salt: new Uint8Array(salt), info: new Uint8Array(info) },
			key,
			bytes * 8
		)
	);
}

/** Decifra come farebbe il browser (RFC 8291): serve a provare la cifratura dall'altra parte. */
async function decrypt(body: Uint8Array, ua: CryptoKeyPair, auth: Uint8Array) {
	const salt = body.slice(0, 16);
	const idlen = body[20];
	const asPublic = body.slice(21, 21 + idlen);
	const uaPublic = new Uint8Array((await crypto.subtle.exportKey('raw', ua.publicKey)) as ArrayBuffer);
	const asKey = await crypto.subtle.importKey('raw', asPublic, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
	const ecdh = new Uint8Array(
		await crypto.subtle.deriveBits(
			{ name: 'ECDH', public: asKey, $public: asKey } as unknown as SubtleCryptoDeriveKeyAlgorithm,
			ua.privateKey,
			256
		)
	);
	const info = new Uint8Array([...enc.encode('WebPush: info\0'), ...uaPublic, ...asPublic]);
	const ikm = await hkdf(auth, ecdh, info, 32);
	const cek = await hkdf(salt, ikm, enc.encode('Content-Encoding: aes128gcm\0'), 16);
	const nonce = await hkdf(salt, ikm, enc.encode('Content-Encoding: nonce\0'), 12);
	const key = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['decrypt']);
	const plain = new Uint8Array(
		await crypto.subtle.decrypt({ name: 'AES-GCM', iv: nonce }, key, body.slice(21 + idlen))
	);
	expect(plain[plain.length - 1]).toBe(2); // delimitatore dell'ultimo record
	return new TextDecoder().decode(plain.slice(0, -1));
}

async function browserSubscription() {
	const ua = await ecdhPair();
	const auth = crypto.getRandomValues(new Uint8Array(16));
	const p256dh = base64url(new Uint8Array((await crypto.subtle.exportKey('raw', ua.publicKey)) as ArrayBuffer));
	return { ua, auth, sub: { p256dh, auth: base64url(auth) } };
}

async function vapidJwk(): Promise<string> {
	const pair = (await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, [
		'sign',
		'verify'
	])) as CryptoKeyPair;
	return JSON.stringify(await crypto.subtle.exportKey('jwk', pair.privateKey));
}

describe('notifiche Web Push', () => {
	it('cifra come RFC 8291, appendice A', async () => {
		// chiavi, segreto e sale dell'esempio dell'RFC
		const asPublic = fromBase64url(
			'BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8'
		);
		const privateKey = await crypto.subtle.importKey(
			'jwk',
			{
				kty: 'EC',
				crv: 'P-256',
				d: 'yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw',
				x: base64url(asPublic.slice(1, 33)),
				y: base64url(asPublic.slice(33))
			},
			{ name: 'ECDH', namedCurve: 'P-256' },
			true,
			['deriveBits']
		);
		const publicKey = await crypto.subtle.importKey('raw', asPublic, { name: 'ECDH', namedCurve: 'P-256' }, true, []);
		const body = await encrypt(
			{
				p256dh: 'BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4',
				auth: 'BTBZMqHH6r4Tts7J_aSIgg'
			},
			enc.encode('When I grow up, I want to be a watermelon'),
			{ salt: fromBase64url('DGv6ra1nlYgDCS1FRnbzlw'), ephemeral: { privateKey, publicKey } }
		);
		expect(base64url(body)).toBe(
			'DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN'
		);
	});

	it('il browser decifra il messaggio', async () => {
		const { ua, auth, sub } = await browserSubscription();
		const body = await encrypt(sub, enc.encode('{"titolo":"Prova"}'));
		expect(await decrypt(body, ua, auth)).toBe('{"titolo":"Prova"}');
	});

	it('firma VAPID verificabile con la chiave pubblica', async () => {
		const jwk = await vapidJwk();
		const header = await vapidAuthorization('https://push.example.com/abc', jwk, 'https://cordata.example/');
		const [, jwt, k] = /^vapid t=([^,]+), k=(.+)$/.exec(header)!;
		expect(k).toBe(publicKeyFromJwk(JSON.parse(jwk)));
		const [h, c, s] = jwt.split('.');
		const claims = JSON.parse(new TextDecoder().decode(fromBase64url(c)));
		expect(claims.aud).toBe('https://push.example.com');
		expect(claims.sub).toBe('https://cordata.example/');
		const pub = await crypto.subtle.importKey('raw', fromBase64url(k), { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']);
		const ok = await crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, pub, fromBase64url(s), enc.encode(`${h}.${c}`));
		expect(ok).toBe(true);
	});

	it('manda a tutte le iscrizioni della persona e cancella quelle scadute', async () => {
		await env.DB.prepare("INSERT OR IGNORE INTO utenti (id, nome) VALUES ('u-push', 'Pia')").run();
		const a = await browserSubscription();
		const b = await browserSubscription();
		for (const [endpoint, s] of [
			['https://push.example.com/vivo', a.sub],
			['https://push.example.com/scaduto', b.sub]
		] as const) {
			await env.DB.prepare("INSERT INTO notifiche_push (endpoint, utente, p256dh, auth) VALUES (?, 'u-push', ?, ?)")
				.bind(endpoint, s.p256dh, s.auth)
				.run();
		}
		const seen: { url: string; headers: Headers; body: Uint8Array }[] = [];
		const fetcher = (async (url: string, init: RequestInit) => {
			seen.push({ url, headers: new Headers(init.headers), body: init.body as Uint8Array });
			return new Response(null, { status: url.endsWith('scaduto') ? 410 : 201 });
		}) as unknown as typeof fetch;
		const pushEnv = { ...env, VAPID_PRIVATE_JWK: await vapidJwk() };
		const sent = await notify(pushEnv, ['u-push'], { titolo: 'Uscita', testo: 'Ciao' }, fetcher);
		expect(sent).toBe(1);
		expect(seen.map((r) => r.headers.get('Content-Encoding'))).toEqual(['aes128gcm', 'aes128gcm']);
		const vivo = seen.find((r) => r.url.endsWith('vivo'))!;
		expect(JSON.parse(await decrypt(vivo.body, a.ua, a.auth))).toEqual({ titolo: 'Uscita', testo: 'Ciao' });
		const rimaste = await env.DB.prepare("SELECT endpoint FROM notifiche_push WHERE utente = 'u-push'").all();
		expect(rimaste.results.map((r) => r.endpoint)).toEqual(['https://push.example.com/vivo']);
		// senza chiave VAPID non si manda nulla
		expect(await notify(env, ['u-push'], { titolo: 'x', testo: 'y' }, fetcher)).toBe(0);
	});

	it('promemoria della sera prima solo per le uscite di domani non annullate', async () => {
		await env.DB.prepare("INSERT OR IGNORE INTO utenti (id, nome) VALUES ('u-org', 'Olga')").run();
		const { sub } = await browserSubscription();
		await env.DB.prepare("INSERT INTO notifiche_push (endpoint, utente, p256dh, auth) VALUES ('https://push.example.com/olga', 'u-org', ?, ?)")
			.bind(sub.p256dh, sub.auth)
			.run();
		const insert = (id: string, quando: string, stato = 'aperta') =>
			env.DB.prepare(
				`INSERT INTO uscite (id, invito_hash, organizzatore, titolo, ritrovo_quando, ritrovo_luogo, stato)
				 VALUES (?, 'h', 'u-org', ?, ?, 'Piazza', ?)`
			)
				.bind(id, `Gita ${id}`, quando, stato)
				.run()
				.then(() =>
					env.DB.prepare("INSERT INTO partecipanti (uscita, utente, stato) VALUES (?, 'u-org', 'confermato')").bind(id).run()
				);
		await insert('domani', '2026-07-12T05:00:00Z'); // 7:00 ora italiana
		await insert('dopodomani', '2026-07-13T05:00:00Z');
		await insert('annullata', '2026-07-12T06:00:00Z', 'annullata');
		const titles: string[] = [];
		const fetcher = (async () => {
			titles.push('x');
			return new Response(null, { status: 201 });
		}) as unknown as typeof fetch;
		const count = await reminders(
			{ ...env, VAPID_PRIVATE_JWK: await vapidJwk() },
			new Date('2026-07-11T16:00:00Z'),
			fetcher
		);
		expect(count).toBe(1);
		expect(titles.length).toBe(1);
	});
});
