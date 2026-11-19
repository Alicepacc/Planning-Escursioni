// Uscite di gruppo: creazione, pagina invito, iscrizione con lista d'attesa, azioni
// dell'organizzatore (SPEC §5.4). Le notifiche (Web Push) arriveranno in un passo successivo:
// qui si restituisce chi va avvisato.

import { currentUser, requireUser, type Utente } from './auth';
import { iscrizioniAperte, promossi, statoNuovaIscrizione, type Iscrizione } from './posti';
import { HttpError, json, nowIso, randomId, randomToken, readJson, sha256, type Env } from './util';

const VISIBILITA = ['link', 'contatti', 'pubblica'] as const;
export const DISCLAIMER =
	"Uscita privata tra persone, non organizzata dal CAI: nessuna copertura assicurativa CAI, " +
	'ognuno partecipa sotto la propria responsabilità.';

interface UscitaRow {
	id: string;
	invito_hash: string;
	organizzatore: string;
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
	attrezzatura: string;
	note: string | null;
	visibilita: string;
	stato: string;
	rinviata_a: string | null;
}

interface NuovaUscita {
	titolo?: string;
	itinerario?: string;
	ritrovo_quando?: string;
	ritrovo_luogo?: string;
	ritrovo_lon?: number;
	ritrovo_lat?: number;
	mezzi?: string;
	posti?: number | null;
	iscrizioni_entro?: string | null;
	difficolta?: string;
	requisiti?: string;
	attrezzatura?: string[];
	note?: string;
	visibilita?: string;
}

function text(value: unknown, field: string, max: number, required = false): string | null {
	if (value == null || value === '') {
		if (required) throw new HttpError(400, `Manca il campo «${field}».`);
		return null;
	}
	if (typeof value !== 'string' || value.length > max) {
		throw new HttpError(400, `Campo «${field}» non valido (al massimo ${max} caratteri).`);
	}
	return value.trim();
}

function isoDate(value: unknown, field: string, required = false): string | null {
	const s = text(value, field, 40, required);
	if (s == null) return null;
	if (Number.isNaN(Date.parse(s))) throw new HttpError(400, `Data non valida in «${field}».`);
	return new Date(s).toISOString();
}

export function validate(body: NuovaUscita) {
	const posti = body.posti ?? null;
	if (posti != null && (!Number.isInteger(posti) || posti < 1 || posti > 200)) {
		throw new HttpError(400, 'I posti devono essere un numero intero tra 1 e 200.');
	}
	const visibilita = body.visibilita ?? 'link';
	if (!VISIBILITA.includes(visibilita as (typeof VISIBILITA)[number])) {
		throw new HttpError(400, 'Visibilità non valida.');
	}
	const attrezzatura = body.attrezzatura ?? [];
	if (!Array.isArray(attrezzatura) || attrezzatura.some((a) => typeof a !== 'string' || a.length > 80)) {
		throw new HttpError(400, "L'attrezzatura è un elenco di voci brevi.");
	}
	const lon = body.ritrovo_lon ?? null;
	const lat = body.ritrovo_lat ?? null;
	if ((lon == null) !== (lat == null) || (lon != null && (Math.abs(lon) > 180 || Math.abs(lat!) > 90))) {
		throw new HttpError(400, 'Coordinate del ritrovo non valide.');
	}
	const quando = isoDate(body.ritrovo_quando, 'ritrovo_quando', true)!;
	const entro = isoDate(body.iscrizioni_entro, 'iscrizioni_entro');
	if (entro && entro > quando) {
		throw new HttpError(400, 'Il termine delle iscrizioni è dopo il ritrovo.');
	}
	return {
		titolo: text(body.titolo, 'titolo', 120, true)!,
		itinerario: text(body.itinerario, 'itinerario', 300),
		ritrovo_quando: quando,
		ritrovo_luogo: text(body.ritrovo_luogo, 'ritrovo_luogo', 200, true)!,
		ritrovo_lon: lon,
		ritrovo_lat: lat,
		mezzi: text(body.mezzi, 'mezzi', 200),
		posti,
		iscrizioni_entro: entro,
		difficolta: text(body.difficolta, 'difficolta', 20),
		requisiti: text(body.requisiti, 'requisiti', 1000),
		attrezzatura: JSON.stringify(attrezzatura.map((a) => a.trim()).filter(Boolean)),
		note: text(body.note, 'note', 2000),
		visibilita
	};
}

async function load(env: Env, id: string): Promise<UscitaRow> {
	const row = await env.DB.prepare('SELECT * FROM uscite WHERE id = ?').bind(id).first<UscitaRow>();
	if (!row) throw new HttpError(404, 'Uscita non trovata.');
	return row;
}

async function iscrizioni(env: Env, id: string): Promise<(Iscrizione & { nome: string })[]> {
	const { results } = await env.DB.prepare(
		`SELECT p.utente, p.stato, p.iscritto, u.nome FROM partecipanti p JOIN utenti u ON u.id = p.utente
		 WHERE p.uscita = ? ORDER BY p.iscritto`
	)
		.bind(id)
		.all<Iscrizione & { nome: string }>();
	return results;
}

/** Il link d'invito apre la pagina; l'organizzatore e chi è già iscritto la vedono anche senza. */
async function canRead(env: Env, row: UscitaRow, token: string | null, user: Utente | null) {
	if (token && (await sha256(token)) === row.invito_hash) return true;
	if (user && user.id === row.organizzatore) return true;
	if (user) {
		const p = await env.DB.prepare('SELECT 1 FROM partecipanti WHERE uscita = ? AND utente = ?')
			.bind(row.id, user.id)
			.first();
		if (p) return true;
	}
	return false;
}

export async function create(env: Env, request: Request): Promise<Response> {
	const user = await requireUser(env, request);
	const v = validate(await readJson<NuovaUscita>(request));
	const id = randomId();
	const invito = randomToken(18);
	await env.DB.batch([
		env.DB.prepare(
			`INSERT INTO uscite (id, invito_hash, organizzatore, titolo, itinerario, ritrovo_quando,
			   ritrovo_luogo, ritrovo_lon, ritrovo_lat, mezzi, posti, iscrizioni_entro, difficolta,
			   requisiti, attrezzatura, note, visibilita)
			 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
		).bind(
			id,
			await sha256(invito),
			user.id,
			v.titolo,
			v.itinerario,
			v.ritrovo_quando,
			v.ritrovo_luogo,
			v.ritrovo_lon,
			v.ritrovo_lat,
			v.mezzi,
			v.posti,
			v.iscrizioni_entro,
			v.difficolta,
			v.requisiti,
			v.attrezzatura,
			v.note,
			v.visibilita
		),
		// l'organizzatore partecipa e occupa un posto
		env.DB.prepare(
			"INSERT INTO partecipanti (uscita, utente, stato, iscritto) VALUES (?, ?, 'confermato', ?)"
		).bind(id, user.id, nowIso())
	]);
	return json(env, { id, invito }, 201);
}

export async function show(env: Env, request: Request, id: string): Promise<Response> {
	const row = await load(env, id);
	const user = await currentUser(env, request);
	const token = new URL(request.url).searchParams.get('t');
	if (!(await canRead(env, row, token, user))) throw new HttpError(404, 'Uscita non trovata.');
	const list = await iscrizioni(env, id);
	const mine = user ? (list.find((i) => i.utente === user.id)?.stato ?? null) : null;
	const organizer = user?.id === row.organizzatore;
	const insider = organizer || mine === 'confermato' || mine === 'attesa';
	const annunci = insider
		? (
				await env.DB.prepare('SELECT id, testo, creato FROM annunci WHERE uscita = ? ORDER BY creato DESC')
					.bind(id)
					.all()
			).results
		: [];
	const organizzatore = list.find((i) => i.utente === row.organizzatore)?.nome ?? '';
	const { invito_hash: _hash, attrezzatura, ...pub } = row;
	return json(env, {
		...pub,
		attrezzatura: JSON.parse(attrezzatura),
		organizzatore_nome: organizzatore,
		confermati: list.filter((i) => i.stato === 'confermato').length,
		in_attesa: list.filter((i) => i.stato === 'attesa').length,
		iscrizioni_aperte: iscrizioniAperte(row.stato, row.iscrizioni_entro, nowIso()),
		mio_stato: mine,
		sono_organizzatore: organizer,
		// i nomi dei partecipanti li vede solo l'organizzatore
		partecipanti: organizer ? list.map(({ utente, nome, stato }) => ({ utente, nome, stato })) : undefined,
		annunci,
		avvertenza: DISCLAIMER
	});
}

export async function join(env: Env, request: Request, id: string): Promise<Response> {
	const user = await requireUser(env, request);
	const row = await load(env, id);
	const body = await readJson<{ t?: string }>(request);
	if (!(await canRead(env, row, body.t ?? null, user))) throw new HttpError(404, 'Uscita non trovata.');
	if (!iscrizioniAperte(row.stato, row.iscrizioni_entro, nowIso())) {
		throw new HttpError(409, 'Le iscrizioni sono chiuse.');
	}
	const list = await iscrizioni(env, id);
	const current = list.find((i) => i.utente === user.id);
	if (current && current.stato !== 'rinunciato') return json(env, { stato: current.stato });
	const stato = statoNuovaIscrizione(row.posti, list.filter((i) => i.utente !== user.id));
	await env.DB.prepare(
		`INSERT INTO partecipanti (uscita, utente, stato, iscritto) VALUES (?, ?, ?, ?)
		 ON CONFLICT (uscita, utente) DO UPDATE SET stato = excluded.stato,
		   iscritto = excluded.iscritto, aggiornato = datetime('now')`
	)
		.bind(id, user.id, stato, nowIso())
		.run();
	return json(env, { stato });
}

/** Aggiorna gli stati e fa scorrere la lista d'attesa; restituisce chi è stato promosso. */
async function promote(env: Env, row: UscitaRow): Promise<string[]> {
	const list = await iscrizioni(env, row.id);
	const ids = promossi(row.posti, list);
	if (ids.length) {
		await env.DB.batch(
			ids.map((u) =>
				env.DB.prepare(
					"UPDATE partecipanti SET stato = 'confermato', aggiornato = datetime('now') WHERE uscita = ? AND utente = ?"
				).bind(row.id, u)
			)
		);
	}
	return ids;
}

export async function leave(env: Env, request: Request, id: string): Promise<Response> {
	const user = await requireUser(env, request);
	const row = await load(env, id);
	if (user.id === row.organizzatore) {
		throw new HttpError(409, "L'organizzatore non rinuncia: può annullare l'uscita.");
	}
	await env.DB.prepare(
		"UPDATE partecipanti SET stato = 'rinunciato', aggiornato = datetime('now') WHERE uscita = ? AND utente = ?"
	)
		.bind(id, user.id)
		.run();
	return json(env, { stato: 'rinunciato', promossi: await promote(env, row) });
}

async function requireOrganizer(env: Env, request: Request, id: string) {
	const user = await requireUser(env, request);
	const row = await load(env, id);
	if (user.id !== row.organizzatore) throw new HttpError(403, "Solo l'organizzatore può farlo.");
	return { user, row };
}

/** L'organizzatore sposta qualcuno tra confermati e lista d'attesa. */
export async function setParticipant(env: Env, request: Request, id: string, utente: string) {
	const { row } = await requireOrganizer(env, request, id);
	const { stato } = await readJson<{ stato?: string }>(request);
	if (stato !== 'confermato' && stato !== 'attesa') throw new HttpError(400, 'Stato non valido.');
	const res = await env.DB.prepare(
		"UPDATE partecipanti SET stato = ?, aggiornato = datetime('now') WHERE uscita = ? AND utente = ? AND stato != 'rinunciato'"
	)
		.bind(stato, id, utente)
		.run();
	if (!res.meta.changes) throw new HttpError(404, 'Partecipante non trovato.');
	const promoted = stato === 'attesa' ? await promote(env, row) : [];
	return json(env, { stato, promossi: promoted });
}

/** Annullare, rinviare (con la nuova data) o riaprire l'uscita. */
export async function setStatus(env: Env, request: Request, id: string): Promise<Response> {
	const { row } = await requireOrganizer(env, request, id);
	const body = await readJson<{ stato?: string; rinviata_a?: string }>(request);
	if (body.stato !== 'annullata' && body.stato !== 'rinviata' && body.stato !== 'aperta') {
		throw new HttpError(400, 'Stato non valido.');
	}
	const nuova = body.stato === 'rinviata' ? isoDate(body.rinviata_a, 'rinviata_a', true) : null;
	await env.DB.prepare(
		`UPDATE uscite SET stato = ?, rinviata_a = ?, ritrovo_quando = COALESCE(?, ritrovo_quando),
		   aggiornato = datetime('now') WHERE id = ?`
	)
		.bind(body.stato, nuova, nuova, row.id)
		.run();
	const avvisare = (await iscrizioni(env, id))
		.filter((i) => i.stato !== 'rinunciato' && i.utente !== row.organizzatore)
		.map((i) => i.utente);
	return json(env, { stato: body.stato, rinviata_a: nuova, avvisare });
}

export async function announce(env: Env, request: Request, id: string): Promise<Response> {
	await requireOrganizer(env, request, id);
	const { testo } = await readJson<{ testo?: string }>(request);
	const value = text(testo, 'testo', 1000, true)!;
	const annuncio = randomId();
	await env.DB.prepare('INSERT INTO annunci (id, uscita, testo) VALUES (?, ?, ?)')
		.bind(annuncio, id, value)
		.run();
	return json(env, { id: annuncio }, 201);
}

/** Le uscite della persona: organizzate e a cui partecipa. */
export async function mine(env: Env, request: Request): Promise<Response> {
	const user = await requireUser(env, request);
	const { results } = await env.DB.prepare(
		`SELECT u.id, u.titolo, u.ritrovo_quando, u.stato, u.organizzatore = ? AS organizzo, p.stato AS mio_stato
		 FROM uscite u JOIN partecipanti p ON p.uscita = u.id AND p.utente = ?
		 WHERE p.stato != 'rinunciato' ORDER BY u.ritrovo_quando`
	)
		.bind(user.id, user.id)
		.all();
	return json(env, { uscite: results });
}
