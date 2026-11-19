// Anteprima del link d'invito per le app di messaggistica (Open Graph) e rinvio alla pagina
// dell'app. L'app è statica e le anteprime non eseguono JavaScript: per questo la pagina con i
// meta tag la serve il Worker. I dettagli compaiono solo con un link d'invito valido.

import { formatRome } from './uscite';
import { sha256, type Env } from './util';

const ESC: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const escapeHtml = (text: string): string => text.replace(/[&<>"']/g, (c) => ESC[c]);

// unico script della pagina, senza dati: consentito dalla CSP con il suo hash
const SCRIPT = "location.replace(document.getElementById('apri').href)";
let scriptHash: Promise<string> | null = null;
function hashOf(text: string): Promise<string> {
	return crypto.subtle
		.digest('SHA-256', new TextEncoder().encode(text))
		.then((d) => btoa(String.fromCharCode(...new Uint8Array(d))));
}

interface Anteprima {
	titolo: string;
	ritrovo_quando: string;
	ritrovo_luogo: string;
	stato: string;
	invito_hash: string;
}

export async function invitePreview(env: Env, request: Request, id: string): Promise<Response> {
	const t = new URL(request.url).searchParams.get('t') ?? '';
	const app = env.APP_URL.replace(/\/$/, '');
	const target = `${app}/uscita?id=${encodeURIComponent(id)}${t ? `&t=${encodeURIComponent(t)}` : ''}`;
	const row = await env.DB.prepare(
		'SELECT titolo, ritrovo_quando, ritrovo_luogo, stato, invito_hash FROM uscite WHERE id = ?'
	)
		.bind(id)
		.first<Anteprima>();
	let title = 'Uscita di gruppo su Cordata';
	let description = 'Apri il link per vedere i dettagli e partecipare.';
	if (row && t && (await sha256(t)) === row.invito_hash) {
		const prefix = row.stato === 'annullata' ? 'Annullata: ' : row.stato === 'rinviata' ? 'Rinviata: ' : '';
		const when = formatRome(row.ritrovo_quando);
		title = prefix + row.titolo;
		description =
			`${when.charAt(0).toUpperCase()}${when.slice(1)} · ${row.ritrovo_luogo}. ` +
			'Uscita privata tra persone, non organizzata dal CAI.';
	}
	const e = escapeHtml;
	const html = `<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${e(title)} – Cordata</title>
<meta name="robots" content="noindex, nofollow">
<meta name="description" content="${e(description)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Cordata">
<meta property="og:locale" content="it_IT">
<meta property="og:title" content="${e(title)}">
<meta property="og:description" content="${e(description)}">
<meta property="og:image" content="${e(app)}/og/uscita.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Cordata · uscita di gruppo">
<meta name="twitter:card" content="summary_large_image">
<style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.5}a{color:#1f5f3f}</style>
</head>
<body>
<p><a id="apri" href="${e(target)}">Apri l’uscita su Cordata</a></p>
<script>${SCRIPT}</script>
</body>
</html>
`;
	scriptHash ??= hashOf(SCRIPT);
	return new Response(html, {
		headers: {
			'Content-Type': 'text/html; charset=utf-8',
			'Content-Security-Policy': `default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-${await scriptHash}'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`,
			// il link contiene il segreto dell'invito: niente referrer, niente cache, niente indici
			'Referrer-Policy': 'no-referrer',
			'Cache-Control': 'no-store',
			'X-Robots-Tag': 'noindex, nofollow',
			'X-Content-Type-Options': 'nosniff'
		}
	});
}
