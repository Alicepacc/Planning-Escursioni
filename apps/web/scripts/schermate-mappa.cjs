/* eslint-disable @typescript-eslint/no-require-imports -- script Node (CommonJS) con il Playwright di sistema */
// Schermate di pagine con mappa WebGL: nel browser headless la cattura dell'intera vista perde
// il disegno della mappa; a strisce invece viene. Le strisce si ricompongono con PIL.
const { chromium, devices } = require('playwright');
const [, , url, out, scheme = 'light', wait = '7000'] = process.argv;
(async () => {
	const b = await chromium.launch();
	const ctx = await b.newContext({
		...devices['iPhone 15 Pro'],
		deviceScaleFactor: 2,
		colorScheme: scheme
	});
	const p = await ctx.newPage();
	await p.goto(url);
	await p.waitForTimeout(Number(wait));
	const { width, height } = p.viewportSize();
	const parts = [];
	for (let y = 0; y < height; y += 280) {
		const h = Math.min(280, height - y);
		const f = `${out}.part${parts.length}.png`;
		await p.screenshot({ path: f, clip: { x: 0, y, width, height: h } });
		parts.push(f);
	}
	console.log(parts.join(' '));
	await b.close();
})();
