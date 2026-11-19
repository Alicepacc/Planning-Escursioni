// Cordata – servizio delle uscite di gruppo (Cloudflare Worker + D1, ADR 0014).

import {
	loginOptions,
	loginVerify,
	logout,
	registrationOptions,
	registrationVerify,
	requireUser
} from './auth';
import { invitePreview } from './invito';
import { publicKey, reminders, subscribe, unsubscribe } from './notifiche';
import {
	announce,
	contactsList,
	create,
	join,
	leave,
	mine,
	publicList,
	setParticipant,
	setStatus,
	show
} from './uscite';
import { HttpError, cors, json, type Env } from './util';

type Handler = (
	env: Env,
	request: Request,
	ctx: ExecutionContext,
	...params: string[]
) => Promise<Response>;

// gestori senza contesto (non mandano notifiche)
const plain =
	(fn: (env: Env, request: Request, ...params: string[]) => Promise<Response>): Handler =>
	(env, request, _ctx, ...params) =>
		fn(env, request, ...params);

const ROUTES: [string, RegExp, Handler][] = [
	['POST', /^\/api\/accesso\/registrazione\/opzioni$/, plain(registrationOptions)],
	['POST', /^\/api\/accesso\/registrazione\/verifica$/, plain(registrationVerify)],
	['POST', /^\/api\/accesso\/opzioni$/, plain((env) => loginOptions(env))],
	['POST', /^\/api\/accesso\/verifica$/, plain(loginVerify)],
	['POST', /^\/api\/accesso\/esci$/, plain(logout)],
	[
		'GET',
		/^\/api\/io$/,
		plain(async (env, request) => json(env, { utente: await requireUser(env, request) }))
	],
	['GET', /^\/api\/notifiche\/chiave$/, plain((env) => publicKey(env))],
	['POST', /^\/api\/notifiche$/, plain(subscribe)],
	['POST', /^\/api\/notifiche\/rimuovi$/, plain(unsubscribe)],
	['GET', /^\/api\/uscite$/, plain(mine)],
	['POST', /^\/api\/uscite$/, create],
	// prima di /api/uscite/:id
	['GET', /^\/api\/uscite\/pubbliche$/, plain((env) => publicList(env))],
	['GET', /^\/api\/uscite\/contatti$/, plain(contactsList)],
	['GET', /^\/api\/uscite\/([\w-]+)$/, plain(show)],
	['POST', /^\/api\/uscite\/([\w-]+)\/partecipa$/, join],
	['POST', /^\/api\/uscite\/([\w-]+)\/rinuncia$/, leave],
	['POST', /^\/api\/uscite\/([\w-]+)\/stato$/, setStatus],
	['POST', /^\/api\/uscite\/([\w-]+)\/annunci$/, announce],
	['POST', /^\/api\/uscite\/([\w-]+)\/partecipanti\/([\w-]+)$/, setParticipant],
	// link da condividere: anteprima per le app di messaggistica, poi la pagina dell'app
	['GET', /^\/invito\/([\w-]+)$/, plain(invitePreview)]
];

export default {
	async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
		if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(env) });
		const { pathname } = new URL(request.url);
		try {
			for (const [method, pattern, handler] of ROUTES) {
				const m = pattern.exec(pathname);
				if (m && request.method === method) return await handler(env, request, ctx, ...m.slice(1));
			}
			return json(env, { errore: 'Indirizzo non trovato.' }, 404);
		} catch (err) {
			if (err instanceof HttpError) return json(env, { errore: err.message }, err.status);
			console.error(err);
			return json(env, { errore: 'Errore interno.' }, 500);
		}
	},

	// promemoria della sera prima (cron in wrangler.jsonc)
	async scheduled(_controller: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
		ctx.waitUntil(reminders(env));
	}
} satisfies ExportedHandler<Env>;
