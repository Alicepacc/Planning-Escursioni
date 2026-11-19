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

const inDays = (d: number) => new Date(Date.now() + d * 24 * 3600_000).toISOString();

const BASE_USCITA = {
	ritrovo_luogo: 'Parcheggio di Ponte Conseria',
	ritrovo_lon: 11.62,
	ritrovo_lat: 46.17
};

async function create(token: string, extra: Record<string, unknown>) {
	const res = await call('POST', '/api/uscite', token, { ...BASE_USCITA, ...extra });
	expect(res.status).toBe(201);
	return (await res.json()) as { id: string; invito: string };
}

type Elenco = { uscite: { id: string; titolo: string; confermati: number }[] };

describe('visibilità delle uscite', () => {
	let anna: string, bruno: string, carla: string, dario: string;
	beforeEach(async () => {
		anna = await person('u-anna', 'Anna');
		bruno = await person('u-bruno', 'Bruno');
		carla = await person('u-carla', 'Carla');
		// nessuna uscita in comune con Anna (il database è condiviso tra i test del file)
		dario = await person('u-dario-' + crypto.randomUUID(), 'Dario');
	});

	it('un’uscita pubblica richiede il punto di ritrovo', async () => {
		const res = await call('POST', '/api/uscite', anna, {
			titolo: 'Senza punto',
			ritrovo_quando: inDays(5),
			ritrovo_luogo: 'Predazzo',
			visibilita: 'pubblica'
		});
		expect(res.status).toBe(400);
		expect(((await res.json()) as { errore: string }).errore).toContain('punto di ritrovo');
	});

	it('le uscite pubbliche dei prossimi 30 giorni compaiono nel feed e si leggono senza link', async () => {
		const pub = await create(anna, { titolo: 'Pubblica vicina', ritrovo_quando: inDays(3), visibilita: 'pubblica' });
		await create(anna, { titolo: 'Solo link', ritrovo_quando: inDays(3) });
		await create(anna, { titolo: 'Pubblica lontana nel tempo', ritrovo_quando: inDays(60), visibilita: 'pubblica' });
		const annullata = await create(anna, { titolo: 'Pubblica annullata', ritrovo_quando: inDays(4), visibilita: 'pubblica' });
		await call('POST', `/api/uscite/${annullata.id}/stato`, anna, { stato: 'annullata' });

		const res = await call('GET', '/api/uscite/pubbliche');
		expect(res.headers.get('Cache-Control')).toBe('public, max-age=300');
		const { uscite } = (await res.json()) as Elenco;
		expect(uscite.map((u) => u.titolo)).toEqual(['Pubblica vicina']);
		expect(uscite[0].confermati).toBe(1);

		// chiunque la legge senza account né link; per partecipare basta l'accesso
		expect((await call('GET', `/api/uscite/${pub.id}`)).status).toBe(200);
		const join = await call('POST', `/api/uscite/${pub.id}/partecipa`, carla, {});
		expect(((await join.json()) as { stato: string }).stato).toBe('confermato');

		// anteprima del link anche senza il segreto
		const html = await (await exports.default.fetch(new Request(`${BASE}/invito/${pub.id}`))).text();
		expect(html).toContain('content="Pubblica vicina"');
	});

	it('«contatti»: la vedono e la trovano solo le persone già uscite con l’organizzatrice', async () => {
		// Bruno è già uscito con Anna
		const prima = await create(anna, { titolo: 'Prima uscita', ritrovo_quando: inDays(-20) });
		await call('POST', `/api/uscite/${prima.id}/partecipa`, bruno, { t: prima.invito });

		const nuova = await create(anna, { titolo: 'Per i contatti', ritrovo_quando: inDays(10), visibilita: 'contatti' });

		const perBruno = (await (await call('GET', '/api/uscite/contatti', bruno)).json()) as Elenco;
		expect(perBruno.uscite.map((u) => u.titolo)).toEqual(['Per i contatti']);
		expect((await call('GET', `/api/uscite/${nuova.id}`, bruno)).status).toBe(200);

		// Dario no: niente elenco, niente pagina senza link (ma col link sì)
		const perDario = (await (await call('GET', '/api/uscite/contatti', dario)).json()) as Elenco;
		expect(perDario.uscite).toEqual([]);
		expect((await call('GET', `/api/uscite/${nuova.id}`, dario)).status).toBe(404);
		expect((await call('GET', `/api/uscite/${nuova.id}?t=${nuova.invito}`, dario)).status).toBe(200);

		// Anna non vede le sue; senza accesso l'elenco non c'è
		const perAnna = (await (await call('GET', '/api/uscite/contatti', anna)).json()) as Elenco;
		expect(perAnna.uscite).toEqual([]);
		expect((await call('GET', '/api/uscite/contatti')).status).toBe(401);

		// Bruno partecipa senza link; poi l'uscita esce dalle proposte
		const join = await call('POST', `/api/uscite/${nuova.id}/partecipa`, bruno, {});
		expect(((await join.json()) as { stato: string }).stato).toBe('confermato');
		const dopo = (await (await call('GET', '/api/uscite/contatti', bruno)).json()) as Elenco;
		expect(dopo.uscite).toEqual([]);
		// le uscite «contatti» non finiscono nel feed pubblico
		const feed = (await (await call('GET', '/api/uscite/pubbliche')).json()) as Elenco;
		expect(feed.uscite.find((u) => u.id === nuova.id)).toBeUndefined();
	});
});
