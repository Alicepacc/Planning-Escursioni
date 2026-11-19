import { env, exports } from 'cloudflare:workers';
import { beforeEach, describe, expect, it } from 'vitest';
import { createSession } from '../src/auth';

const BASE = 'https://uscite.example';

async function person(id: string, nome: string): Promise<string> {
	await env.DB.prepare('INSERT OR IGNORE INTO utenti (id, nome) VALUES (?, ?)').bind(id, nome).run();
	return createSession(env, id);
}

function call(method: string, path: string, token?: string, body?: unknown) {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (token) headers.Authorization = `Bearer ${token}`;
	return exports.default.fetch(
		new Request(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined })
	);
}

const USCITA = {
	titolo: 'Lago di Erdemolo',
	itinerario: '/attivita/2020-10-25-lago-di-erdemolo-e-rifugio-sette-selle-sat-trento',
	ritrovo_quando: '2026-07-12T07:00:00Z',
	ritrovo_luogo: 'Parcheggio di Palù del Fersina',
	ritrovo_lon: 11.38,
	ritrovo_lat: 46.11,
	posti: 3,
	attrezzatura: ['scarponi', 'giacca antivento']
};

describe('uscite di gruppo', () => {
	let anna: string, bruno: string, carla: string, dario: string;
	beforeEach(async () => {
		anna = await person('u-anna', 'Anna');
		bruno = await person('u-bruno', 'Bruno');
		carla = await person('u-carla', 'Carla');
		dario = await person('u-dario', 'Dario');
	});

	it('richiede l’accesso per creare un’uscita e valida i campi', async () => {
		expect((await call('POST', '/api/uscite', undefined, USCITA)).status).toBe(401);
		const bad = await call('POST', '/api/uscite', anna, { ...USCITA, posti: 0 });
		expect(bad.status).toBe(400);
		const late = await call('POST', '/api/uscite', anna, {
			...USCITA,
			iscrizioni_entro: '2026-08-01T00:00:00Z'
		});
		expect(late.status).toBe(400);
	});

	it('pagina invito: si legge solo col link, senza nomi dei partecipanti per chi non organizza', async () => {
		const created = await call('POST', '/api/uscite', anna, USCITA);
		expect(created.status).toBe(201);
		const { id, invito } = (await created.json()) as { id: string; invito: string };
		expect((await call('GET', `/api/uscite/${id}`)).status).toBe(404);
		expect((await call('GET', `/api/uscite/${id}?t=sbagliato`)).status).toBe(404);
		const page = (await (await call('GET', `/api/uscite/${id}?t=${invito}`)).json()) as Record<
			string,
			unknown
		>;
		expect(page.titolo).toBe('Lago di Erdemolo');
		expect(page.confermati).toBe(1); // l'organizzatrice
		expect(page.partecipanti).toBeUndefined();
		expect(page.avvertenza).toMatch(/non organizzata dal CAI/);
		expect(page).not.toHaveProperty('invito_hash');
	});

	it('iscrizione, lista d’attesa e scorrimento quando qualcuno rinuncia', async () => {
		const { id, invito } = (await (await call('POST', '/api/uscite', anna, USCITA)).json()) as {
			id: string;
			invito: string;
		};
		const join = async (token: string) =>
			((await (await call('POST', `/api/uscite/${id}/partecipa`, token, { t: invito })).json()) as {
				stato: string;
			}).stato;
		expect(await join(bruno)).toBe('confermato');
		expect(await join(carla)).toBe('confermato');
		expect(await join(dario)).toBe('attesa'); // 3 posti: Anna, Bruno, Carla
		expect(await join(dario)).toBe('attesa'); // iscriversi due volte non cambia nulla

		const left = (await (await call('POST', `/api/uscite/${id}/rinuncia`, bruno)).json()) as {
			promossi: string[];
		};
		expect(left.promossi).toEqual(['u-dario']);

		const org = (await (await call('GET', `/api/uscite/${id}`, anna)).json()) as {
			partecipanti: { nome: string; stato: string }[];
		};
		expect(org.partecipanti.map((p) => `${p.nome}:${p.stato}`)).toEqual([
			'Anna:confermato',
			'Bruno:rinunciato',
			'Carla:confermato',
			'Dario:confermato'
		]);
		// l'organizzatrice non può «rinunciare»: annulla l'uscita
		expect((await call('POST', `/api/uscite/${id}/rinuncia`, anna)).status).toBe(409);
	});

	it('annullamento, rinvio e bacheca dell’organizzatore', async () => {
		const { id, invito } = (await (await call('POST', '/api/uscite', anna, USCITA)).json()) as {
			id: string;
			invito: string;
		};
		await call('POST', `/api/uscite/${id}/partecipa`, bruno, { t: invito });
		expect((await call('POST', `/api/uscite/${id}/stato`, bruno, { stato: 'annullata' })).status).toBe(
			403
		);
		const rinvio = (await (
			await call('POST', `/api/uscite/${id}/stato`, anna, {
				stato: 'rinviata',
				rinviata_a: '2026-07-19T07:00:00Z'
			})
		).json()) as { avvisare: string[]; rinviata_a: string };
		expect(rinvio.avvisare).toEqual(['u-bruno']);
		expect(rinvio.rinviata_a).toBe('2026-07-19T07:00:00.000Z');

		expect((await call('POST', `/api/uscite/${id}/annunci`, anna, { testo: 'Portate i ramponcini' })).status).toBe(201);
		const vista = (await (await call('GET', `/api/uscite/${id}`, bruno)).json()) as {
			annunci: { testo: string }[];
			ritrovo_quando: string;
		};
		expect(vista.annunci.map((a) => a.testo)).toEqual(['Portate i ramponcini']);
		expect(vista.ritrovo_quando).toBe('2026-07-19T07:00:00.000Z');

		await call('POST', `/api/uscite/${id}/stato`, anna, { stato: 'annullata' });
		const closed = await call('POST', `/api/uscite/${id}/partecipa`, carla, { t: invito });
		expect(closed.status).toBe(409);
	});

	it('elenca le uscite della persona e chiude la sessione', async () => {
		const { id } = (await (await call('POST', '/api/uscite', anna, USCITA)).json()) as { id: string };
		const list = (await (await call('GET', '/api/uscite', anna)).json()) as { uscite: { id: string }[] };
		expect(list.uscite.map((u) => u.id)).toContain(id);
		expect((await call('POST', '/api/accesso/esci', anna)).status).toBe(200);
		expect((await call('GET', '/api/io', anna)).status).toBe(401);
	});

	it('passkey: le opzioni di registrazione chiedono un nome e salvano una sfida', async () => {
		expect((await call('POST', '/api/accesso/registrazione/opzioni', undefined, { nome: 'A' })).status).toBe(
			400
		);
		const res = await call('POST', '/api/accesso/registrazione/opzioni', undefined, { nome: 'Elena' });
		const body = (await res.json()) as { sfida_id: string; opzioni: { rp: { id: string }; challenge: string } };
		expect(body.opzioni.rp.id).toBe(env.RP_ID);
		const row = await env.DB.prepare('SELECT sfida FROM sfide WHERE id = ?').bind(body.sfida_id).first();
		expect(row?.sfida).toBe(body.opzioni.challenge);
	});
});
