// Cordata – servizio delle uscite di gruppo (Cloudflare Worker + D1, ADR 0014).

import { loginOptions, loginVerify, logout, registrationOptions, registrationVerify, requireUser } from './auth';
import { announce, create, join, leave, mine, setParticipant, setStatus, show } from './uscite';
import { HttpError, cors, json, type Env } from './util';

type Handler = (env: Env, request: Request, ...params: string[]) => Promise<Response>;

const ROUTES: [string, RegExp, Handler][] = [
	['POST', /^\/api\/accesso\/registrazione\/opzioni$/, registrationOptions],
	['POST', /^\/api\/accesso\/registrazione\/verifica$/, registrationVerify],
	['POST', /^\/api\/accesso\/opzioni$/, (env) => loginOptions(env)],
	['POST', /^\/api\/accesso\/verifica$/, loginVerify],
	['POST', /^\/api\/accesso\/esci$/, logout],
	['GET', /^\/api\/io$/, async (env, request) => json(env, { utente: await requireUser(env, request) })],
	['GET', /^\/api\/uscite$/, mine],
	['POST', /^\/api\/uscite$/, create],
	['GET', /^\/api\/uscite\/([\w-]+)$/, show],
	['POST', /^\/api\/uscite\/([\w-]+)\/partecipa$/, join],
	['POST', /^\/api\/uscite\/([\w-]+)\/rinuncia$/, leave],
	['POST', /^\/api\/uscite\/([\w-]+)\/stato$/, setStatus],
	['POST', /^\/api\/uscite\/([\w-]+)\/annunci$/, announce],
	['POST', /^\/api\/uscite\/([\w-]+)\/partecipanti\/([\w-]+)$/, setParticipant]
];

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(env) });
		const { pathname } = new URL(request.url);
		try {
			for (const [method, pattern, handler] of ROUTES) {
				const m = pattern.exec(pathname);
				if (m && request.method === method) return await handler(env, request, ...m.slice(1));
			}
			return json(env, { errore: 'Indirizzo non trovato.' }, 404);
		} catch (err) {
			if (err instanceof HttpError) return json(env, { errore: err.message }, err.status);
			console.error(err);
			return json(env, { errore: 'Errore interno.' }, 500);
		}
	}
} satisfies ExportedHandler<Env>;
