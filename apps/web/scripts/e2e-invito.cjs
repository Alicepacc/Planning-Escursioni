/* eslint-disable @typescript-eslint/no-require-imports -- script Node (CommonJS) con il Playwright di sistema */
// Prova end-to-end del link d'invito (Fase 5): codice QR decodificato con una libreria
// indipendente (jsQR), link condiviso con l'anteprima Open Graph letta come farebbe un'app di
// messaggistica (senza JavaScript) e rinvio alla pagina dell'uscita. Prima:
//   cd services/outings && pnpm run db:migrate:local && pnpm exec wrangler dev --port 8787 \
//     --var APP_ORIGIN:http://localhost:4173 --var RP_ID:localhost --var APP_URL:http://localhost:4173
//   cd apps/web && VITE_USCITE_API=http://localhost:8787 pnpm run build && pnpm exec vite preview --port 4173
// poi: node apps/web/scripts/e2e-invito.cjs
const { chromium, devices } = require('playwright');
// CORDATA_URL per provare la demo pubblicata (es. https://alicepacc.github.io/Planning-Escursioni)
const BASE = process.env.CORDATA_URL ?? 'http://localhost:4173';
const JSQR = require.resolve('jsqr/dist/jsQR.js');
const SHOT =
	(process.env.CORDATA_SHOTS ??
		require('path').join(__dirname, '../../../reports/phase5/screenshots')) +
	'/5-qr-invito-telefono.jpg';
(async () => {
	// headless completo: la versione ridotta di Chromium nega sempre i permessi delle notifiche
	const browser = await chromium.launch({ channel: 'chromium' });
	const ctx = await browser.newContext({ ...devices['Pixel 7'], timezoneId: 'Europe/Rome' });
	await ctx.addInitScript(() => localStorage.setItem('cordata.primo-avvio', 'visto'));
	await ctx.grantPermissions(['clipboard-read', 'clipboard-write', 'notifications'], {
		origin: BASE
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
	await page.goto(BASE + '/uscite/nuova');
	await page.getByRole('button', { name: 'Crea un account' }).click();
	await page.getByLabel(/Come ti chiami/).fill('Anna');
	await page.getByRole('button', { name: 'Crea la passkey' }).click();
	await page.getByLabel('Titolo').fill('Lago di Erdemolo & Sette Selle');
	await page.getByLabel('Ritrovo: data e ora').fill('2027-07-12T07:00');
	await page.getByLabel('Ritrovo: luogo').fill('Palù del Fersina');
	await page.getByRole('button', { name: /Crea l’uscita/ }).click();
	await page.waitForURL(/uscita\?id=/);
	const pageUrl = page.url();
	// codice QR: decodificato con una libreria indipendente
	await page.getByText('Mostra il codice QR').click();
	await page.locator('.qr svg').evaluate((el) => el.scrollIntoView({ block: 'center' }));
	const png = await page.locator('.qr svg').screenshot();
	await page.screenshot({ path: SHOT, quality: 80 });

	const dec = await browser.newPage();
	await dec.addScriptTag({ path: JSQR });
	const decoded = await dec.evaluate(async (b64) => {
		const img = new Image();
		img.src = 'data:image/png;base64,' + b64;
		await img.decode();
		const c = document.createElement('canvas');
		c.width = img.width;
		c.height = img.height;
		const g = c.getContext('2d');
		g.drawImage(img, 0, 0);
		const d = g.getImageData(0, 0, c.width, c.height);
		return window.jsQR(d.data, d.width, d.height)?.data ?? null;
	}, png.toString('base64'));
	console.log('QR decodificato = pagina invito:', decoded === pageUrl);
	// link condiviso: in questa emulazione non c'è Web Share, finisce negli appunti
	const hasShare = await page.evaluate(() => typeof navigator.share === 'function');
	await page.getByRole('button', { name: 'Condividi il link d’invito' }).click();
	let shared = '';
	if (!hasShare) {
		await page.getByText('Link d’invito copiato.').waitFor();
		shared = await page.evaluate(() => navigator.clipboard.readText());
	}
	console.log('Web Share:', hasShare, '| link condiviso:', shared.replace(/t=[^&]+/, 't=…'));
	// come lo vede un'app di messaggistica (niente JavaScript)
	const res = await fetch(shared, { headers: { 'User-Agent': 'WhatsApp/2.24 A' } });
	const html = await res.text();
	const meta = (p) => (new RegExp(`<meta property="${p}" content="([^"]*)"`).exec(html) || [])[1];
	console.log(
		'anteprima:',
		res.status,
		'|',
		meta('og:title'),
		'|',
		meta('og:description'),
		'|',
		meta('og:image')
	);
	const img = await fetch(
		meta('og:image').replace('https://alicepacc.github.io/Planning-Escursioni', BASE)
	);
	console.log('immagine (dalla build locale):', img.status, img.headers.get('content-type'));
	// aprendolo nel browser si arriva alla pagina dell'uscita
	const other = await (
		await browser.newContext({ ...devices['Pixel 7'], timezoneId: 'Europe/Rome' })
	).newPage();
	await other.goto(shared);
	await other
		.waitForURL((u) => u.href.startsWith(BASE + '/uscita?id='), { timeout: 10000 })
		.catch(() => {});
	console.log('il link porta a:', other.url().replace(/t=[^&]+/, 't=…'));
	console.log('titolo mostrato:', await other.getByRole('heading', { level: 1 }).textContent());
	console.log('errori pagina:', errors.length ? errors : 'nessuno');
	await browser.close();
})().catch((e) => {
	console.error('FAILED', e.message);
	process.exit(1);
});
