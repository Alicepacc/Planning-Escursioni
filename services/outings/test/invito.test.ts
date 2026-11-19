import { env, exports } from 'cloudflare:workers';
import { describe, expect, it } from 'vitest';
import { createSession } from '../src/auth';

const BASE = 'https://uscite.example';

async function organizer(): Promise<string> {
	await env.DB.prepare('INSERT OR IGNORE INTO utenti (id, nome) VALUES (?, ?)').bind('u-anna', 'Anna').run();
	return createSession(env, 'u-anna');
}

async function create(token: string, titolo: string) {
	const res = await exports.default.fetch(
		new Request(BASE + '/api/uscite', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
			body: JSON.stringify({
				titolo,
				ritrovo_quando: '2027-07-12T05:00:00Z',
				ritrovo_luogo: 'Parcheggio di Ponte Conseria'
			})
		})
	);
	return (await res.json()) as { id: string; invito: string };
}

const preview = (path: string) => exports.default.fetch(new Request(BASE + path));

describe('anteprima del link d’invito', () => {
	it('mostra titolo, data e luogo solo con il link valido, con escape dell’HTML', async () => {
		const token = await organizer();
		const { id, invito } = await create(token, 'Stellune <script>alert("x")</script> & co');
		const res = await preview(`/invito/${id}?t=${invito}`);
		expect(res.status).toBe(200);
		expect(res.headers.get('Content-Type')).toContain('text/html');
		expect(res.headers.get('Referrer-Policy')).toBe('no-referrer');
		expect(res.headers.get('Cache-Control')).toBe('no-store');
		const html = await res.text();
		expect(html).toContain(
			'<meta property="og:title" content="Stellune &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; co">'
		);
		expect(html).not.toContain('<script>alert');
		expect(html).toContain('Lunedì 12 luglio alle ore 07:00 · Parcheggio di Ponte Conseria.');
		expect(html).toContain('non organizzata dal CAI');
		expect(html).toContain(`/uscita?id=${id}&amp;t=${invito}"`);
		expect(html).toContain('/og/uscita.png');

		// l'unico script è quello consentito dall'hash nella CSP
		const script = /<script>([^<]*)<\/script>/.exec(html)![1];
		const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(script));
		const hash = btoa(String.fromCharCode(...new Uint8Array(digest)));
		expect(res.headers.get('Content-Security-Policy')).toContain(`script-src 'sha256-${hash}'`);
	});

	it('senza link valido non rivela nulla, ma rimanda comunque all’app', async () => {
		const token = await organizer();
		const { id } = await create(token, 'Uscita segreta');
		for (const path of [`/invito/${id}`, `/invito/${id}?t=sbagliato`, '/invito/inesistente?t=x']) {
			const html = await (await preview(path)).text();
			expect(html).toContain('<meta property="og:title" content="Uscita di gruppo su Cordata">');
			expect(html).not.toContain('segreta');
			expect(html).not.toContain('Ponte Conseria');
			expect(html).toContain('/uscita?id=');
		}
	});

	it('segnala le uscite annullate', async () => {
		const token = await organizer();
		const { id, invito } = await create(token, 'Cima Undici');
		await exports.default.fetch(
			new Request(`${BASE}/api/uscite/${id}/stato`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
				body: JSON.stringify({ stato: 'annullata' })
			})
		);
		const html = await (await preview(`/invito/${id}?t=${invito}`)).text();
		expect(html).toContain('content="Annullata: Cima Undici"');
	});
});
