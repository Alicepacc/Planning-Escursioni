// Iscrizione del browser alle notifiche push e promemoria del giorno prima (cron).

import { requireUser } from './auth';
import { notify, publicKeyFromJwk } from './push';
import { formatRome } from './uscite';
import { HttpError, json, readJson, type Env } from './util';

/** Chiave pubblica VAPID per `pushManager.subscribe`; 404 se le notifiche non sono attive. */
export async function publicKey(env: Env): Promise<Response> {
	if (!env.VAPID_PRIVATE_JWK) throw new HttpError(404, 'Notifiche non ancora attive.');
	return json(env, { chiave: publicKeyFromJwk(JSON.parse(env.VAPID_PRIVATE_JWK) as JsonWebKey) });
}

interface PushSubscriptionJSON {
	endpoint?: string;
	keys?: { p256dh?: string; auth?: string };
}

export async function subscribe(env: Env, request: Request): Promise<Response> {
	const user = await requireUser(env, request);
	const sub = await readJson<PushSubscriptionJSON>(request);
	const endpoint = sub.endpoint ?? '';
	if (!/^https:\/\//.test(endpoint) || endpoint.length > 1000 || !sub.keys?.p256dh || !sub.keys.auth) {
		throw new HttpError(400, 'Iscrizione alle notifiche non valida.');
	}
	await env.DB.prepare(
		`INSERT INTO notifiche_push (endpoint, utente, p256dh, auth) VALUES (?, ?, ?, ?)
		 ON CONFLICT (endpoint) DO UPDATE SET utente = excluded.utente, p256dh = excluded.p256dh,
		   auth = excluded.auth`
	)
		.bind(endpoint, user.id, sub.keys.p256dh, sub.keys.auth)
		.run();
	return json(env, { ok: true }, 201);
}

export async function unsubscribe(env: Env, request: Request): Promise<Response> {
	const user = await requireUser(env, request);
	const { endpoint } = await readJson<{ endpoint?: string }>(request);
	await env.DB.prepare('DELETE FROM notifiche_push WHERE endpoint = ? AND utente = ?')
		.bind(endpoint ?? '', user.id)
		.run();
	return json(env, { ok: true });
}

function romeDate(d: Date): string {
	return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Rome' }).format(d);
}

/**
 * Promemoria della sera prima: le uscite non annullate che si tengono domani (ora italiana),
 * a chi è confermato e all'organizzatore. Restituisce quante uscite sono state ricordate.
 */
export async function reminders(
	env: Env,
	now = new Date(),
	fetcher: typeof fetch = fetch
): Promise<number> {
	const tomorrow = romeDate(new Date(now.getTime() + 24 * 3600_000));
	const { results } = await env.DB.prepare(
		`SELECT id, titolo, ritrovo_quando, ritrovo_luogo FROM uscite
		 WHERE stato != 'annullata' AND ritrovo_quando BETWEEN ? AND ?`
	)
		.bind(now.toISOString(), new Date(now.getTime() + 48 * 3600_000).toISOString())
		.all<{ id: string; titolo: string; ritrovo_quando: string; ritrovo_luogo: string }>();
	let count = 0;
	for (const u of results.filter((r) => romeDate(new Date(r.ritrovo_quando)) === tomorrow)) {
		const { results: people } = await env.DB.prepare(
			"SELECT utente FROM partecipanti WHERE uscita = ? AND stato = 'confermato'"
		)
			.bind(u.id)
			.all<{ utente: string }>();
		await notify(
			env,
			people.map((p) => p.utente),
			{
				titolo: `Domani: ${u.titolo}`,
				testo: `Ritrovo ${formatRome(u.ritrovo_quando)} · ${u.ritrovo_luogo}. Controlla meteo e attrezzatura.`,
				url: `${env.APP_URL.replace(/\/$/, '')}/uscita?id=${encodeURIComponent(u.id)}`
			},
			fetcher
		);
		count += 1;
	}
	return count;
}
