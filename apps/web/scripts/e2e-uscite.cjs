/* eslint-disable @typescript-eslint/no-require-imports -- script Node (CommonJS) con il Playwright di sistema */
// Prova end-to-end delle uscite di gruppo (Fase 5) con passkey vere su autenticatori virtuali
// di Chromium. Prima, in due terminali:
//   cd services/outings && pnpm run db:migrate:local && \
//     pnpm exec wrangler dev --port 8787 --var APP_ORIGIN:http://localhost:4173 --var RP_ID:localhost
//   cd apps/web && VITE_USCITE_API=http://localhost:8787 pnpm run build && pnpm exec vite preview --port 4173
// poi: node apps/web/scripts/e2e-uscite.cjs
const { chromium, devices } = require('playwright');
const BASE = 'http://localhost:4173';
const SHOTS = require('path').join(__dirname, '../../../reports/phase5/screenshots/');
async function personContext(browser) {
	const ctx = await browser.newContext({ ...devices['Pixel 7'] });
	const page = await ctx.newPage();
	const cdp = await ctx.newCDPSession(page);
	await cdp.send('WebAuthn.enable');
	await cdp.send('WebAuthn.addVirtualAuthenticator', {
		options: {
			protocol: 'ctap2',
			transport: 'internal',
			hasResidentKey: true,
			hasUserVerification: true,
			isUserVerified: true,
			automaticPresenceSimulation: true
		}
	});
	const errors = [];
	page.on('pageerror', (e) => errors.push(e.message));
	page.on('console', (m) => {
		if (m.type() === 'error') errors.push(m.text());
	});
	return { ctx, page, errors };
}
(async () => {
	require('fs').mkdirSync(SHOTS, { recursive: true });
	const browser = await chromium.launch();
	// Anna organizza dalla scheda di un'attività
	const anna = await personContext(browser);
	await anna.page.goto(BASE + '/attivita/2026-09-20-salita-alla-cima-delle-stellune-feltre');
	await anna.page.getByRole('link', { name: 'Organizza uscita' }).click();
	await anna.page.waitForURL(/uscite\/nuova/);
	await anna.page.getByRole('button', { name: 'Crea un account' }).click();
	await anna.page.getByLabel(/Come ti chiami/).fill('Anna');
	await anna.page.getByRole('button', { name: 'Crea la passkey' }).click();
	await anna.page.getByLabel('Titolo').waitFor();
	console.log('titolo precompilato:', await anna.page.getByLabel('Titolo').inputValue());
	await anna.page.getByLabel('Ritrovo: data e ora').fill('2027-07-12T07:00');
	await anna.page.getByLabel('Ritrovo: luogo').fill('Parcheggio di Ponte Conseria');
	await anna.page.getByLabel(/Posti/).fill('2');
	await anna.page.screenshot({ path: SHOTS + '1-organizza-telefono.jpg', quality: 80 });
	await anna.page.getByRole('button', { name: /Crea l’uscita/ }).click();
	await anna.page.waitForURL(/uscita\?id=/);
	const invite = anna.page.url();
	await anna.page.getByRole('heading', { level: 1 }).waitFor();
	console.log('invito creato:', invite.replace(/t=[^&]+/, 't=…'));

	// Bruno apre il link senza account, poi partecipa creando la sua passkey
	const bruno = await personContext(browser);
	await bruno.page.goto(invite);
	await bruno.page.getByRole('heading', { level: 1 }).waitFor();
	console.log(
		'Bruno vede:',
		await bruno.page.getByRole('heading', { level: 1 }).textContent(),
		'|',
		(await bruno.page.locator('.dati').innerText()).replace(/\s+/g, ' ').slice(0, 120)
	);
	await bruno.page.screenshot({ path: SHOTS + '2-invito-telefono.jpg', quality: 80 });
	await bruno.page.getByRole('button', { name: 'Partecipo' }).click();
	await bruno.page.getByRole('button', { name: 'Crea un account' }).click();
	await bruno.page.getByLabel(/Come ti chiami/).fill('Bruno');
	await bruno.page.getByRole('button', { name: 'Crea la passkey' }).click();
	await bruno.page.getByText(/Partecipi: il tuo posto è confermato/).waitFor();
	console.log('Bruno:', await bruno.page.getByText(/Partecipi/).textContent());

	// Carla: posti finiti (2), va in lista d'attesa
	const carla = await personContext(browser);
	await carla.page.goto(invite);
	await carla.page.getByRole('button', { name: 'Partecipo' }).click();
	await carla.page.getByRole('button', { name: 'Crea un account' }).click();
	await carla.page.getByLabel(/Come ti chiami/).fill('Carla');
	await carla.page.getByRole('button', { name: 'Crea la passkey' }).click();
	await carla.page
		.getByText(/lista d’attesa/)
		.first()
		.waitFor();
	console.log('Carla:', await carla.page.locator('[role=status]').first().textContent());

	// Bruno rinuncia: Carla passa tra i confermati; Anna vede i partecipanti e pubblica un annuncio
	await bruno.page.getByRole('button', { name: 'Rinuncio' }).click();
	await bruno.page.getByText('Hai rinunciato.').first().waitFor();
	await anna.page.reload();
	await anna.page.getByRole('heading', { name: 'Gestisci l’uscita' }).waitFor();
	console.log(
		'Anna vede:',
		(await anna.page.locator('.partecipanti').innerText()).replace(/\s+/g, ' ')
	);
	await anna.page.getByLabel('Annuncio ai partecipanti').fill('Ritrovo anticipato di 15 minuti');
	await anna.page.getByRole('button', { name: 'Pubblica' }).click();
	await anna.page.getByText('Annuncio pubblicato.').waitFor();
	await anna.page.screenshot({
		path: SHOTS + '3-organizzatore-telefono.jpg',
		quality: 80,
		fullPage: true
	});
	await carla.page.reload();
	await carla.page.getByRole('heading', { name: 'Bacheca' }).waitFor();
	console.log(
		'Carla ora:',
		await carla.page.locator('[role=status]').first().textContent(),
		'| bacheca:',
		await carla.page.locator('.annunci').innerText()
	);

	// Anna rientra più tardi: «Le mie uscite»
	await anna.page.goto(BASE + '/uscite');
	await anna.page.getByRole('heading', { name: 'Le mie uscite' }).waitFor();
	console.log(
		'Le mie uscite (Anna):',
		(await anna.page.locator('.elenco').innerText()).replace(/\s+/g, ' ')
	);
	console.log('errori:', [...anna.errors, ...bruno.errors, ...carla.errors].slice(0, 5));
	await browser.close();
})().catch((e) => {
	console.error('FAILED', e);
	process.exit(1);
});
