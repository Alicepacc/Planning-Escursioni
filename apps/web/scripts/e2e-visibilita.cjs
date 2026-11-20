/* eslint-disable @typescript-eslint/no-require-imports -- script Node (CommonJS) con il Playwright di sistema */
// Prova end-to-end della visibilità delle uscite (Fase 5): Anna pubblica un'uscita dalla scheda
// delle Stellune con il punto di ritrovo proposto dalla partenza e una seconda solo per i suoi
// contatti; Bruno, senza account, trova la prima nell'elenco pubblico vicino a lui, partecipa e
// poi vede la seconda tra le proposte dei contatti. Prima: servizio e app come in e2e-uscite.cjs.
const { chromium, devices } = require('playwright');
// CORDATA_URL per provare la demo pubblicata (es. https://alicepacc.github.io/Planning-Escursioni)
const BASE = process.env.CORDATA_URL ?? 'http://localhost:4173';
const SHOTS =
	(process.env.CORDATA_SHOTS ??
		require('path').join(__dirname, '../../../reports/phase5/screenshots')) + '/';

// prossimo sabato in ora italiana (per il filtro «questo fine settimana») e uno più avanti
function isoDay(offset) {
	const d = new Date(Date.now() + offset * 24 * 3600_000);
	return d.toISOString().slice(0, 10);
}
const sat = (() => {
	for (let i = 0; i < 7; i++) {
		const d = new Date(Date.now() + i * 24 * 3600_000);
		if (d.getUTCDay() === 6) return d.toISOString().slice(0, 10);
	}
})();

async function person(browser, geo) {
	const ctx = await browser.newContext({
		...devices['Pixel 7'],
		timezoneId: 'Europe/Rome',
		...(geo ? { geolocation: geo, permissions: ['geolocation'] } : {})
	});
	const page = await ctx.newPage();
	const errors = [];
	page.on('pageerror', (e) => errors.push(e.message));
	page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
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
	return { page, errors };
}

(async () => {
	const browser = await chromium.launch({ channel: 'chromium' });
	const anna = await person(browser, { latitude: 46.2186, longitude: 11.7972 });
	await anna.page.goto(BASE + '/attivita/2026-09-20-salita-alla-cima-delle-stellune-feltre');
	await anna.page.getByRole('link', { name: 'Organizza uscita' }).click();
	await anna.page.getByRole('button', { name: 'Crea un account' }).click();
	await anna.page.getByLabel(/Come ti chiami/).fill('Anna');
	await anna.page.getByRole('button', { name: 'Crea la passkey' }).click();
	await anna.page.getByLabel('Titolo').waitFor();
	console.log('punto proposto:', await anna.page.getByText(/^Punto di ritrovo:/).textContent());
	await anna.page.getByLabel('Ritrovo: data e ora').fill(`${sat}T07:00`);
	await anna.page.getByLabel('Ritrovo: luogo').fill('Parcheggio di Ponte Conseria');
	await anna.page.getByLabel(/Pubblica \(compare/).check();
	await anna.page.locator('.riquadro').scrollIntoViewIfNeeded();
	await anna.page.waitForTimeout(1500);
	// toccare la mappa sposta il punto
	const before = await anna.page.getByText(/^Punto di ritrovo:/).textContent();
	await anna.page.locator('.riquadro canvas').click({ position: { x: 200, y: 140 } });
	await anna.page.waitForTimeout(300);
	const after = await anna.page.getByText(/^Punto di ritrovo:/).textContent();
	console.log('tocco sulla mappa sposta il punto:', before !== after, '→', after);
	await anna.page.screenshot({ path: SHOTS + '6-punto-di-ritrovo-telefono.jpg', quality: 80 });
	await anna.page.getByRole('button', { name: /Crea l’uscita/ }).click();
	await anna.page.waitForURL(/uscita\?id=/);
	console.log('uscita pubblica creata');

	// un'altra pubblica tra due settimane, fuori dal fine settimana
	await anna.page.goto(BASE + '/uscite/nuova');
	await anna.page.getByLabel('Titolo').fill('Anello del lago di Calaita');
	await anna.page.getByLabel('Ritrovo: data e ora').fill(`${isoDay(15)}T08:30`);
	await anna.page.getByLabel('Ritrovo: luogo').fill('Lago di Calaita');
	await anna.page.getByRole('button', { name: 'Usa la mia posizione' }).click();
	await anna.page.getByLabel(/Pubblica \(compare/).check();
	await anna.page.getByRole('button', { name: /Crea l’uscita/ }).click();
	await anna.page.waitForURL(/uscita\?id=/);

	// seconda uscita, solo per i contatti, più avanti
	await anna.page.goto(BASE + '/uscite/nuova');
	await anna.page.getByLabel('Titolo').fill('Giro dei laghi di Colbricon');
	await anna.page.getByLabel('Ritrovo: data e ora').fill(`${isoDay(16)}T08:00`);
	await anna.page.getByLabel('Ritrovo: luogo').fill('Passo Rolle');
	await anna.page.getByLabel(/I miei contatti/).check();
	await anna.page.getByRole('button', { name: /Crea l’uscita/ }).click();
	await anna.page.waitForURL(/uscita\?id=/);
	console.log('uscita per i contatti creata');

	// Bruno, a Feltre, senza account
	const bruno = await person(browser, { latitude: 46.0186, longitude: 11.9105 });
	await bruno.page.goto(BASE + '/uscite');
	await bruno.page.getByRole('heading', { name: /Uscite pubbliche/ }).waitFor();
	await bruno.page.getByRole('button', { name: 'Vicino a me' }).click();
	await bruno.page
		.locator('section[aria-labelledby=pubbliche] li', { hasText: /· a [\d,]+ km/ })
		.first()
		.waitFor();
	const feed = () =>
		bruno.page
			.locator('section[aria-labelledby=pubbliche] li')
			.allInnerTexts()
			.then((t) => t.map((x) => x.replace(/\s+/g, ' ')));
	console.log('elenco pubblico vicino a Bruno:', await feed());
	await bruno.page.getByLabel('Questo fine settimana').check();
	console.log('solo questo fine settimana:', (await feed()).length, 'uscite');
	await bruno.page.screenshot({ path: SHOTS + '7-uscite-pubbliche-telefono.jpg', quality: 80 });
	const titoli = await feed();
	console.log('la per-contatti non è nel feed:', !titoli.some((t) => t.includes('Colbricon')));

	// apre l'uscita pubblica (senza segreto nel link) e partecipa creando l'account
	await bruno.page.getByLabel('Questo fine settimana').uncheck();
	await bruno.page.locator('section[aria-labelledby=pubbliche] li a').first().click();
	await bruno.page.waitForURL(/uscita\?id=[^&]+$/);
	await bruno.page.getByRole('button', { name: 'Partecipo' }).click();
	await bruno.page.getByRole('button', { name: 'Crea un account' }).click();
	await bruno.page.getByLabel(/Come ti chiami/).fill('Bruno');
	await bruno.page.getByRole('button', { name: 'Crea la passkey' }).click();
	await bruno.page.getByText(/Partecipi: il tuo posto è confermato/).waitFor();
	console.log('Bruno partecipa all’uscita pubblica');

	// ora Bruno è un contatto di Anna: vede la seconda uscita in «Uscite»
	await bruno.page.goto(BASE + '/uscite');
	await bruno.page.getByRole('heading', { name: 'Proposte dai tuoi contatti' }).waitFor();
	console.log(
		'proposte dai contatti per Bruno:',
		(await bruno.page.locator('h2:has-text("Proposte") ~ ul').first().innerText()).replace(
			/\s+/g,
			' '
		)
	);
	console.log('errori:', [...anna.errors, ...bruno.errors].slice(0, 5));
	await browser.close();
})().catch((e) => {
	console.error('FAILED', e);
	process.exit(1);
});
