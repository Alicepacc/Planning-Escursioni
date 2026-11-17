// Locandina della proposta generata (SPEC §5.7 a): titolo, descrizione, tappe con tempi,
// difficoltà, attrezzatura per stagione e quota. Il testo è composto solo dai dati (nomi dei
// luoghi, quote, sentieri, rifugi): niente frasi inventate.

import type { ProfilePoint } from '../data/types';
import { formatDuration, formatKm, formatMeters } from '../hiking/format';
import { routeProfile } from '../routing/stats';
import type { GenOptions, Proposal } from './generator';

export const GENERATED_LABEL = 'Proposta generata, non verificata sul terreno';

export interface PosterStage {
	name: string;
	kind: string;
	km: number;
	ele: number | null;
	minutes: number;
}

export interface Poster {
	title: string;
	label: string;
	description: string[];
	stages: PosterStage[];
	equipment: string[];
	why: string[];
}

const KIND_NAMES: Record<string, string> = {
	c: 'cima',
	l: 'lago',
	r: 'rifugio',
	b: 'bivacco',
	v: 'punto panoramico',
	k: 'parcheggio'
};

const ARTICLES: [RegExp, string][] = [
	[/^(laghi|monti|passi|masi)\b/i, 'dei '],
	[/^(cime|malghe|cascate|torri|crode)\b/i, 'delle '],
	[/^(alpe|altopiano|alpeggio)\b/i, "dell'"],
	[
		/^(cima|malga|forcella|punta|croda|baita|cascata|chiesa|sella|testa|val|valle|torre|croce|bocca|rocca|forca)\b/i,
		'della '
	],
	[
		/^(lago|monte|rifugio|passo|bivacco|sasso|col|colle|dosso|doss|piz|pizzo|corno|giogo|sentiero|ponte|maso|castello|santuario|laghetto|becco|crinale)\b/i,
		'del '
	]
];

/** «del Lago di Erdemolo», «della Cima d'Asta», «di Fravort». */
export function ofName(name: string): string {
	for (const [re, art] of ARTICLES) if (re.test(name)) return `${art}${name}`;
	return `di ${name}`;
}

const pct = (x: number) => `${Math.round(x * 100)}%`;
const kmText = (m: number) => (m / 1000).toFixed(1).replace('.', ',');

function minutesAt(profile: ProfilePoint[], distM: number): number {
	if (!profile.length) return 0;
	let lo = 0;
	let hi = profile.length - 1;
	while (hi - lo > 1) {
		const mid = (lo + hi) >> 1;
		if (profile[mid][0] < distM) lo = mid;
		else hi = mid;
	}
	return profile[hi][0] - distM < distM - profile[lo][0] ? profile[hi][4] : profile[lo][4];
}

/** Titolo dai luoghi del percorso. */
export function posterTitle(p: Proposal, startName: string | null, endName: string | null): string {
	const peaks = p.along
		.filter((a) => a.poi.kind === 'c')
		.sort((a, b) => (b.poi.ele ?? 0) - (a.poi.ele ?? 0));
	const lakes = p.along.filter((a) => a.poi.kind === 'l');
	const huts = p.along.filter((a) => a.poi.kind === 'r');
	const top = peaks[0]?.poi.name;
	const lake = lakes[0]?.poi.name;
	if (p.type === 'anello') {
		if (top && lake) return `Anello ${ofName(top)} e ${ofName(lake)}`;
		if (top) return `Anello ${ofName(top)}`;
		if (lakes.length >= 2) return `Giro dei laghi: ${lake} e ${lakes[1].poi.name}`;
		if (lake) return `Anello ${ofName(lake)}`;
		if (huts[0]) return `Anello ${ofName(huts[0].poi.name)}`;
		if (startName) return `Anello da ${startName}`;
		return p.refs.length ? `Anello sui sentieri ${p.refs.slice(0, 2).join(' e ')}` : 'Anello';
	}
	if (p.type === 'andata_ritorno') {
		const goal = p.vias[0]?.name ?? top ?? lake ?? huts[0]?.poi.name;
		return goal ? `${goal}${startName ? ` da ${startName}` : ''}` : 'Andata e ritorno';
	}
	const via = p.vias[0]?.name ?? top ?? lake;
	return `Da ${startName ?? 'partenza'} a ${endName ?? 'arrivo'}${via ? ` per ${via}` : ''}`;
}

/** Attrezzatura per stagione, quota e difficoltà (stesse regole di build/activities.py). */
export function equipmentFor(month: number, maxEle: number, diff: string | null): string[] {
	const out = [
		'calzature da escursionismo',
		'acqua e cibo',
		'kit di primo soccorso',
		'carta dei sentieri'
	];
	const winter = [12, 1, 2, 3].includes(month);
	if (winter && maxEle > 1200)
		out.push('ciaspole e ramponcini', 'ARTVA, pala e sonda dove il bollettino lo richiede');
	if (maxEle > 2000) out.push('giacca antivento e strato caldo');
	if (diff === 'EE' || diff === 'EEA') out.push('scarponi con suola rigida, passo sicuro');
	if (diff === 'EEA') out.push('set da ferrata dove indicato');
	if ([6, 7, 8].includes(month)) out.push('protezione solare e cappello');
	return out;
}

export function makePoster(
	p: Proposal,
	opts: Pick<GenOptions, 'month' | 'type'>,
	startName: string | null,
	endName: string | null = null
): Poster {
	const profile = routeProfile(p.legs);
	const startEle = profile[0]?.[1] ?? null;
	const stops = p.along.filter((a) => a.poi.kind !== 'k' && a.poi.name).slice(0, 8);
	const stages: PosterStage[] = [
		{ name: startName ?? 'Partenza', kind: 'partenza', km: 0, ele: startEle, minutes: 0 },
		...stops.map((a) => ({
			name: a.poi.name,
			kind: KIND_NAMES[a.poi.kind] ?? a.poi.kind,
			km: a.at / 1000,
			ele: a.poi.ele,
			minutes: minutesAt(profile, a.at)
		})),
		{
			name: p.type === 'traversata' ? (endName ?? 'Arrivo') : 'Rientro alla partenza',
			kind: 'arrivo',
			km: p.stats.km,
			ele: profile[profile.length - 1]?.[1] ?? null,
			minutes: p.stats.minutes
		}
	];

	const typeText =
		p.type === 'anello'
			? 'Anello'
			: p.type === 'andata_ritorno'
				? 'Andata e ritorno'
				: 'Traversata';
	const refs = p.refs.slice(0, 6);
	const description: string[] = [
		`${typeText} di ${formatKm(p.stats.km)} con ${formatMeters(p.stats.up)} di dislivello in salita, ${pct(p.shares.marked)} su sentieri numerati${refs.length ? ` (${refs.join(', ')})` : ''}.`
	];
	const firstStops = stops.slice(0, 3);
	const top = [...p.along]
		.filter((a) => a.poi.kind === 'c')
		.sort((a, b) => (b.poi.ele ?? 0) - (a.poi.ele ?? 0))[0];
	if (firstStops.length) {
		const list = firstStops.map(
			(a) =>
				`${a.poi.name}${a.poi.ele != null ? ` (${formatMeters(a.poi.ele)}, km ${kmText(a.at)})` : ` (km ${kmText(a.at)})`}`
		);
		description.push(
			`Dalla partenza${startName ? ` (${startName}${startEle != null ? `, ${formatMeters(startEle)}` : ''})` : ''} si raggiunge ${list.join(', poi ')}.`
		);
	}
	description.push(
		`Punto più alto a ${formatMeters(p.stats.maxEle)}${top && top.poi.ele != null && Math.abs(top.poi.ele - (p.stats.maxEle ?? 0)) < 60 ? ` (${top.poi.name})` : ''}; tempo netto ${formatDuration(p.stats.minutes)} secondo il modello CAI, soste escluse.`
	);
	if (p.type === 'anello')
		description.push(
			p.shares.overlap < 0.1
				? 'Il rientro segue un percorso diverso dall’andata.'
				: `Circa ${pct(p.shares.overlap)} del percorso si ripete tra andata e ritorno.`
		);
	else if (p.type === 'andata_ritorno') description.push('Il ritorno è per la stessa via.');
	if (p.shares.road + p.shares.track > 0.15)
		description.push(
			`${pct(p.shares.road + p.shares.track)} del percorso è su strade forestali o asfaltate.`
		);
	const huts = p.along.filter((a) => a.poi.kind === 'r');
	if (huts.length)
		description.push(
			`Rifugi lungo il percorso: ${huts.map((h) => `${h.poi.name} (km ${kmText(h.at)})`).join(', ')}; apertura da verificare.`
		);
	if (p.shares.issue > 0)
		description.push(
			'Un tratto ha una segnalazione aperta nel catasto CAI: verifica che sia percorribile prima di partire.'
		);

	const why: string[] = [`${pct(p.shares.marked)} su sentieri numerati`];
	if (p.type === 'anello')
		why.push(
			p.shares.overlap < 0.1
				? 'rientro per un’altra via'
				: `${pct(p.shares.overlap)} di percorso ripetuto`
		);
	const counts = new Map<string, number>();
	for (const a of p.along)
		if (a.poi.kind !== 'k' && a.poi.name) counts.set(a.poi.kind, (counts.get(a.poi.kind) ?? 0) + 1);
	const plural: Record<string, [string, string]> = {
		c: ['cima', 'cime'],
		l: ['lago', 'laghi'],
		r: ['rifugio', 'rifugi'],
		b: ['bivacco', 'bivacchi'],
		v: ['punto panoramico', 'punti panoramici']
	};
	const listed = [...counts].map(([k, n]) => `${n} ${plural[k]?.[n > 1 ? 1 : 0] ?? k}`);
	if (listed.length) why.push(`${listed.join(', ')} lungo il percorso`);
	if (p.factors.partenza > 0) why.push('parcheggio vicino alla partenza');
	if (p.sun != null) {
		if (p.sun > 0.6) why.push('versanti soprattutto al sole');
		else if (p.sun < 0.4) why.push('versanti soprattutto in ombra');
	}
	if (p.shares.issue > 0) why.push('attenzione: tratti con segnalazioni aperte');
	if ([12, 1, 2, 3].includes(opts.month) && p.shares.high > 0.05)
		why.push(`${pct(p.shares.high)} sopra i 1800 m: d’inverno neve probabile`);

	return {
		title: posterTitle(p, startName, endName),
		label: GENERATED_LABEL,
		description,
		stages,
		equipment: equipmentFor(opts.month, p.stats.maxEle ?? 0, p.stats.maxDiff),
		why
	};
}

/** Punti della linea della proposta da tenere comunque: le mete scelte dal generatore. */
export function proposalAnchors(p: Proposal): number[] {
	const line = p.type === 'andata_ritorno' ? p.legs[0].points : p.points;
	const out: number[] = [];
	for (const v of p.vias) {
		let best = -1;
		let bestD = Infinity;
		line.forEach(([lon, lat], i) => {
			const d = (lon - v.lon) ** 2 + (lat - v.lat) ** 2;
			if (d < bestD) {
				bestD = d;
				best = i;
			}
		});
		if (best > 0 && best < line.length - 1) out.push(best);
	}
	// un anello ha bisogno di almeno due punti intermedi per avere un verso
	if (p.type === 'anello' && out.length < 2)
		out.push(Math.round(line.length / 3), Math.round((2 * line.length) / 3));
	return out.sort((a, b) => a - b);
}

/** Linea da riprodurre nel planner: per l'andata e ritorno basta l'andata (il ritorno è A/R). */
export function proposalLine(p: Proposal) {
	return p.type === 'andata_ritorno' ? p.legs[0].points : p.points;
}
