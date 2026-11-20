/* eslint-disable @typescript-eslint/no-require-imports -- script Node (CommonJS) con il Playwright di sistema */
// Prova end-to-end delle notifiche push (Fase 5): Carla organizza e attiva le notifiche, Bruno
// partecipa, il servizio locale manda una push vera tramite il servizio push di Chrome e il
// service worker la mostra. Serve Chromium in modalità headless completa (channel 'chromium') con
// un profilo persistente: in navigazione privata Chrome non offre il Push API.
// Prima, con una chiave VAPID di prova usa e getta (mai nel repository):
//   cd services/outings && pnpm run db:migrate:local && pnpm exec wrangler dev --port 8787 \
//     --var APP_ORIGIN:http://localhost:4173 --var RP_ID:localhost --var "VAPID_PRIVATE_JWK:$VAPID_JWK"
//   cd apps/web && VITE_USCITE_API=http://localhost:8787 pnpm run build && pnpm exec vite preview --port 4173
// poi: node apps/web/scripts/e2e-notifiche.cjs
const { chromium, devices } = require('playwright');
// CORDATA_URL per provare la demo pubblicata (es. https://alicepacc.github.io/Planning-Escursioni)
const BASE = process.env.CORDATA_URL ?? 'http://localhost:4173';
async function person(ctx) {
	await ctx.addInitScript(() => localStorage.setItem('cordata.primo-avvio', 'visto'));
	await ctx.grantPermissions(['notifications'], { origin: BASE });
	const page = ctx.pages()[0] ?? (await ctx.newPage());
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
	return page;
}
async function signup(page, nome) {
	await page.getByRole('button', { name: 'Crea un account' }).click();
	await page.getByLabel(/Come ti chiami/).fill(nome);
	await page.getByRole('button', { name: 'Crea la passkey' }).click();
}
(async () => {
	const dir = require('fs').mkdtempSync(require('os').tmpdir() + '/cordata-push-');
	const cctx = await chromium.launchPersistentContext(dir, {
		channel: 'chromium',
		...devices['Pixel 7']
	});
	await cctx.addInitScript(() => localStorage.setItem('cordata.primo-avvio', 'visto'));
	const carla = await person(cctx);
	await carla.goto(BASE + '/uscite/nuova');
	await signup(carla, 'Carla');
	await carla.getByLabel('Titolo').fill('Giro del lago di Tovel');
	await carla.getByLabel('Ritrovo: data e ora').fill('2027-06-12T08:00');
	await carla.getByLabel('Ritrovo: luogo').fill('Parcheggio del lago');
	await carla.getByRole('button', { name: /Crea l’uscita/ }).click();
	await carla.waitForURL(/uscita\?id=/);
	const invite = carla.url();
	await carla.getByRole('button', { name: 'Attiva le notifiche' }).click();
	await carla.getByRole('button', { name: 'Disattiva le notifiche' }).waitFor();
	console.log('Carla organizza e ha attivato le notifiche');

	const b = await chromium.launch({ channel: 'chromium' });
	const bruno = await person(await b.newContext({ ...devices['Pixel 7'] }));
	await bruno.goto(invite);
	await bruno.getByRole('button', { name: 'Partecipo' }).click();
	await signup(bruno, 'Bruno');
	await bruno.getByText(/Partecipi: il tuo posto è confermato/).waitFor();
	console.log('Bruno partecipa');
	let shown = [];
	for (let i = 0; i < 60 && !shown.length; i++) {
		await carla.waitForTimeout(1000);
		shown = await carla.evaluate(async () =>
			(await (await navigator.serviceWorker.ready).getNotifications()).map(
				(n) => `${n.title} — ${n.body}`
			)
		);
	}
	console.log('notifiche arrivate a Carla:', shown);
	await carla.screenshot({
		path:
			(process.env.CORDATA_SHOTS ??
				require('path').join(__dirname, '../../../reports/phase5/screenshots')) +
			'/4-notifica-telefono.jpg',
		quality: 80
	});
	await b.close();
	await cctx.close();
})().catch((e) => {
	console.error('FAILED', e.message);
	process.exit(1);
});
