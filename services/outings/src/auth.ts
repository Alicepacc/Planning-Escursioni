// Accesso con passkey (WebAuthn) e sessioni (ADR 0014: niente email, niente password).

import {
	generateAuthenticationOptions,
	generateRegistrationOptions,
	verifyAuthenticationResponse,
	verifyRegistrationResponse,
	type AuthenticationResponseJSON,
	type RegistrationResponseJSON
} from '@simplewebauthn/server';
import { HttpError, json, randomId, randomToken, readJson, sha256, type Env } from './util';

const SESSION_DAYS = 90;
const CHALLENGE_MINUTES = 5;

export interface Utente {
	id: string;
	nome: string;
}

function inMinutes(minutes: number): string {
	return new Date(Date.now() + minutes * 60_000).toISOString();
}

/** Crea una sessione e restituisce il token (in chiaro solo qui: nel database c'è l'hash). */
export async function createSession(env: Env, utente: string): Promise<string> {
	const token = randomToken(32);
	await env.DB.prepare('INSERT INTO sessioni (hash, utente, scade) VALUES (?, ?, ?)')
		.bind(await sha256(token), utente, inMinutes(SESSION_DAYS * 24 * 60))
		.run();
	return token;
}

/** Utente della sessione (intestazione `Authorization: Bearer …`), o null. */
export async function currentUser(env: Env, request: Request): Promise<Utente | null> {
	const header = request.headers.get('Authorization') ?? '';
	const token = header.startsWith('Bearer ') ? header.slice(7).trim() : '';
	if (!token) return null;
	const row = await env.DB.prepare(
		`SELECT u.id, u.nome FROM sessioni s JOIN utenti u ON u.id = s.utente
		 WHERE s.hash = ? AND s.scade > ?`
	)
		.bind(await sha256(token), new Date().toISOString())
		.first<Utente>();
	return row ?? null;
}

export async function requireUser(env: Env, request: Request): Promise<Utente> {
	const user = await currentUser(env, request);
	if (!user) throw new HttpError(401, 'Serve accedere con una passkey.');
	return user;
}

async function saveChallenge(env: Env, sfida: string, tipo: string, utente: string | null) {
	const id = randomId();
	await env.DB.prepare('INSERT INTO sfide (id, sfida, utente, tipo, scade) VALUES (?, ?, ?, ?, ?)')
		.bind(id, sfida, utente, tipo, inMinutes(CHALLENGE_MINUTES))
		.run();
	return id;
}

/** La sfida si usa una volta sola: la si legge e la si cancella. */
async function takeChallenge(env: Env, id: string, tipo: string) {
	const row = await env.DB.prepare('SELECT sfida, utente, scade FROM sfide WHERE id = ? AND tipo = ?')
		.bind(id, tipo)
		.first<{ sfida: string; utente: string | null; scade: string }>();
	await env.DB.prepare('DELETE FROM sfide WHERE id = ?').bind(id).run();
	if (!row || row.scade < new Date().toISOString()) {
		throw new HttpError(400, 'Sfida scaduta o già usata: riprova.');
	}
	return row;
}

function cleanName(nome: unknown): string {
	const value = typeof nome === 'string' ? nome.trim().replace(/\s+/g, ' ') : '';
	if (value.length < 2 || value.length > 40) {
		throw new HttpError(400, 'Il nome deve avere tra 2 e 40 caratteri.');
	}
	return value;
}

export async function registrationOptions(env: Env, request: Request): Promise<Response> {
	const body = await readJson<{ nome?: string }>(request);
	const nome = cleanName(body.nome);
	const utente = randomId();
	const options = await generateRegistrationOptions({
		rpName: env.RP_NAME,
		rpID: env.RP_ID,
		userName: nome,
		userID: new Uint8Array(new TextEncoder().encode(utente)),
		attestationType: 'none',
		authenticatorSelection: { residentKey: 'required', userVerification: 'preferred' }
	});
	const sfida_id = await saveChallenge(env, options.challenge, 'registrazione', utente);
	return json(env, { sfida_id, opzioni: options });
}

export async function registrationVerify(env: Env, request: Request): Promise<Response> {
	const body = await readJson<{ sfida_id: string; nome: string; risposta: RegistrationResponseJSON }>(
		request
	);
	const nome = cleanName(body.nome);
	const challenge = await takeChallenge(env, body.sfida_id, 'registrazione');
	const result = await verifyRegistrationResponse({
		response: body.risposta,
		expectedChallenge: challenge.sfida,
		expectedOrigin: env.APP_ORIGIN,
		expectedRPID: env.RP_ID
	}).catch(() => ({ verified: false as const, registrationInfo: undefined }));
	if (!result.verified || !result.registrationInfo || !challenge.utente) {
		throw new HttpError(400, 'Passkey non verificata.');
	}
	const { credential } = result.registrationInfo;
	await env.DB.batch([
		env.DB.prepare('INSERT INTO utenti (id, nome) VALUES (?, ?)').bind(challenge.utente, nome),
		env.DB.prepare(
			'INSERT INTO passkey (id, utente, chiave_pubblica, contatore, trasporti) VALUES (?, ?, ?, ?, ?)'
		).bind(
			credential.id,
			challenge.utente,
			credential.publicKey,
			credential.counter,
			JSON.stringify(credential.transports ?? [])
		)
	]);
	const token = await createSession(env, challenge.utente);
	return json(env, { token, utente: { id: challenge.utente, nome } }, 201);
}

export async function loginOptions(env: Env): Promise<Response> {
	const options = await generateAuthenticationOptions({
		rpID: env.RP_ID,
		userVerification: 'preferred'
	});
	const sfida_id = await saveChallenge(env, options.challenge, 'accesso', null);
	return json(env, { sfida_id, opzioni: options });
}

export async function loginVerify(env: Env, request: Request): Promise<Response> {
	const body = await readJson<{ sfida_id: string; risposta: AuthenticationResponseJSON }>(request);
	const challenge = await takeChallenge(env, body.sfida_id, 'accesso');
	const passkey = await env.DB.prepare(
		'SELECT id, utente, chiave_pubblica, contatore, trasporti FROM passkey WHERE id = ?'
	)
		.bind(body.risposta?.id ?? '')
		.first<{ id: string; utente: string; chiave_pubblica: ArrayBuffer; contatore: number; trasporti: string }>();
	if (!passkey) throw new HttpError(400, 'Passkey sconosciuta.');
	const result = await verifyAuthenticationResponse({
		response: body.risposta,
		expectedChallenge: challenge.sfida,
		expectedOrigin: env.APP_ORIGIN,
		expectedRPID: env.RP_ID,
		credential: {
			id: passkey.id,
			publicKey: new Uint8Array(passkey.chiave_pubblica),
			counter: passkey.contatore,
			transports: JSON.parse(passkey.trasporti || '[]')
		}
	}).catch(() => ({ verified: false as const, authenticationInfo: undefined }));
	if (!result.verified || !result.authenticationInfo) {
		throw new HttpError(400, 'Passkey non verificata.');
	}
	await env.DB.prepare('UPDATE passkey SET contatore = ? WHERE id = ?')
		.bind(result.authenticationInfo.newCounter, passkey.id)
		.run();
	const utente = await env.DB.prepare('SELECT id, nome FROM utenti WHERE id = ?')
		.bind(passkey.utente)
		.first<Utente>();
	const token = await createSession(env, passkey.utente);
	return json(env, { token, utente });
}

export async function logout(env: Env, request: Request): Promise<Response> {
	const header = request.headers.get('Authorization') ?? '';
	if (header.startsWith('Bearer ')) {
		await env.DB.prepare('DELETE FROM sessioni WHERE hash = ?')
			.bind(await sha256(header.slice(7).trim()))
			.run();
	}
	return json(env, { ok: true });
}
