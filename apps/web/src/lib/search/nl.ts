// Ricerca in linguaggio naturale (SPEC §5.7 b), senza modelli esterni: la frase diventa filtri
// strutturati, mostrati come chip modificabili. Mai una risposta opaca: ciò che non si capisce
// resta nel testo libero o è segnalato come «non ancora disponibile».

import { EMPTY_FILTERS, type Difficulty, type Filters, type RouteType, type Tag } from './explore';

export interface PlaceQuery {
	query: string;
	km: number;
	approx: string | null;
}

export interface NlResult {
	filters: Filters;
	place: PlaceQuery | null;
	unsupported: string[];
}

const MONTH_WORDS = [
	'gennaio',
	'febbraio',
	'marzo',
	'aprile',
	'maggio',
	'giugno',
	'luglio',
	'agosto',
	'settembre',
	'ottobre',
	'novembre',
	'dicembre'
];

function fold(text: string): string {
	return text.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/’/g, "'");
}

function num(s: string): number {
	return Number(s.replace(',', '.'));
}

const HOURS = String.raw`(\d+(?:[.,]\d+)?)\s*(?:h|ore|ora)\b`;

/** Toglie dal testo i pezzi già interpretati, perché le regole successive non li rileggano. */
function take(text: { value: string }, re: RegExp): RegExpExecArray | null {
	const m = re.exec(text.value);
	if (m) text.value = text.value.slice(0, m.index) + ' ' + text.value.slice(m.index + m[0].length);
	return m;
}

const PLACE_STOP = new Set(['EE', 'EEA', 'EAI', 'CAI', 'SAT', 'T', 'E', 'GPS']);

/** Località citata con una preposizione: «vicino a Bolzano», «da Merano», «in Val di Fassa». */
function placeFrom(original: string): string | null {
	const re =
		/\b(?:vicino (?:a|al|alla|allo|ai|agli)|vicino|nei pressi (?:di|del|della)|(?:attorno|intorno) (?:a|al|alla)|dalle parti di|partenza da|partendo da|da|dal|dalla|nel|nella|nelle|nei|in|a|al|alla|allo|ai|agli|sul|sulla|sopra)\s+((?:[A-ZÀ-Ý][\p{L}'’-]+)(?:\s+(?:di|del|della|dei|delle|d'|de|[A-ZÀ-Ý][\p{L}'’-]+))*)/gu;
	for (const m of original.matchAll(re)) {
		const name = m[1].replace(/\s+(?:di|del|della|dei|delle|d'|de)$/u, '').trim();
		if (!PLACE_STOP.has(name) && !/^[A-Z]{1,3}$/.test(name)) return name;
	}
	// tutto minuscolo («vicino a bolzano»): solo dopo espressioni che introducono un luogo
	const lower = fold(original).match(
		/\b(?:vicino a|nei pressi di|attorno a|intorno a|dalle parti di|partenza da|partendo da|in zona)\s+([a-z' ]+?)(?=\s*(?:,|\.|$)|\s+(?:con|e|entro|niente|senza|per|che|di \d)\b)/
	);
	if (lower) return lower[1].trim().replace(/\b\p{L}/gu, (c) => c.toUpperCase());
	return null;
}

export function parseQuery(input: string, base: Filters = EMPTY_FILTERS): NlResult {
	const f: Filters = {
		...base,
		difficulties: [...base.difficulties],
		types: [...base.types],
		tags: [...base.tags],
		sources: [...base.sources]
	};
	const unsupported: string[] = [];
	const text = { value: ` ${fold(input)} ` };

	// mezzi pubblici: non ancora filtrabili (SPEC §5.1, fase successiva)
	if (
		take(
			text,
			/\b(?:raggiungibil\w*\s+)?(?:in|con il|col|con)\s+(?:treno|bus|autobus|corriera|mezzi pubblici)\b/
		)
	)
		unsupported.push('raggiungibile con i mezzi pubblici: filtro non ancora disponibile');

	// località e raggio
	let place: PlaceQuery | null = null;
	const placeName = placeFrom(input);
	if (placeName) {
		let km = 15;
		let approx: string | null = null;
		const kmM = take(text, /\bentro\s+(\d+)\s*km\b/);
		const minM = kmM ? null : take(text, /\bentro\s+(\d+)\s*(?:minuti|min)\b/);
		if (kmM) km = num(kmM[1]);
		else if (minM) {
			km = Math.round(num(minM[1]) * 0.6);
			approx = `${minM[1]} minuti di auto stimati come ${km} km in linea d'aria`;
		}
		place = { query: placeName, km, approx };
		take(text, new RegExp(fold(placeName).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
	}

	// durata
	let m: RegExpExecArray | null;
	if (
		(m = take(
			text,
			new RegExp(String.raw`\b(?:da|tra)?\s*(\d+(?:[.,]\d+)?)\s*(?:-|–|a|e)\s*${HOURS}`)
		))
	) {
		f.minMinutes = Math.round(num(m[1]) * 60);
		f.maxMinutes = Math.round(num(m[2]) * 60);
	} else if (
		(m = take(
			text,
			new RegExp(
				String.raw`\b(?:al massimo|massimo|max|non piu di|meno di|entro|fino a)\s*${HOURS}`
			)
		))
	) {
		f.maxMinutes = Math.round(num(m[1]) * 60);
	} else if (
		(m = take(text, new RegExp(String.raw`\b(?:almeno|minimo|piu di|oltre)\s*${HOURS}`)))
	) {
		f.minMinutes = Math.round(num(m[1]) * 60);
	} else if ((m = take(text, new RegExp(String.raw`\b${HOURS}`)))) {
		const center = num(m[1]) * 60;
		f.minMinutes = Math.round(center - 30);
		f.maxMinutes = Math.round(center + 30);
	} else if (take(text, /\bmezza giornata\b/)) {
		f.minMinutes = null;
		f.maxMinutes = 210;
	} else if (take(text, /\b(?:giornata intera|tutto il giorno|tutta la giornata)\b/)) {
		f.minMinutes = 240;
		f.maxMinutes = 480;
	} else if (take(text, /\b(?:breve|corta|corto|passeggiata)\b/)) {
		f.maxMinutes = 120;
	}

	// lunghezza
	if ((m = take(text, /\b(?:da|tra)?\s*(\d+)\s*(?:-|–|a|e)\s*(\d+)\s*km\b/))) {
		f.minKm = num(m[1]);
		f.maxKm = num(m[2]);
	} else if (
		(m = take(text, /\b(?:al massimo|massimo|max|non piu di|meno di|fino a)\s*(\d+)\s*km\b/))
	) {
		f.maxKm = num(m[1]);
	} else if ((m = take(text, /\b(?:almeno|piu di|oltre)\s*(\d+)\s*km\b/))) {
		f.minKm = num(m[1]);
	} else if ((m = take(text, /\b(\d+)\s*km\b/))) {
		f.minKm = Math.max(0, num(m[1]) - 2);
		f.maxKm = num(m[1]) + 2;
	}

	// dislivello
	if (
		(m = take(
			text,
			/\b(?:al massimo|massimo|max|non piu di|meno di|fino a)\s*(\d{2,4})\s*(?:m|metri)?\s*(?:di\s*)?(?:dislivello|d\+|salita)\b/
		)) ||
		(m = take(
			text,
			/\b(?:dislivello|d\+|salita)\s*(?:massimo|max|non oltre|fino a)\s*(\d{2,4})\s*(?:m|metri)?/
		))
	) {
		f.maxUp = num(m[1]);
	} else if (
		(m = take(
			text,
			/\b(?:almeno|piu di|oltre)\s*(\d{2,4})\s*(?:m|metri)\s*(?:di\s*)?(?:dislivello|d\+|salita)\b/
		))
	) {
		f.minUp = num(m[1]);
	} else if (
		(m = take(text, /\b(\d{2,4})\s*(?:m|metri)\s*(?:di\s*)?(?:dislivello|d\+|salita)\b/))
	) {
		f.minUp = Math.round(num(m[1]) * 0.8);
		f.maxUp = Math.round(num(m[1]) * 1.2);
	} else if (take(text, /\b(?:poco dislivello|pianeggiante|in piano)\b/)) {
		f.maxUp = 300;
	} else if (take(text, /\b(?:tanto dislivello|molto dislivello)\b/)) {
		f.minUp = 1000;
	}

	// quota
	if ((m = take(text, /\b(?:sopra|oltre)\s*(?:i|ai|gli)?\s*(\d{3,4})\s*(?:m|metri)?\b/)))
		f.minEle = num(m[1]);
	if ((m = take(text, /\b(?:sotto|non oltre)\s*(?:i|ai|gli)?\s*(\d{3,4})\s*(?:m|metri)?\b/)))
		f.maxEle = num(m[1]);

	// difficoltà
	const setDiff = (d: Difficulty[]) => (f.difficulties = d);
	if (
		take(
			text,
			/\b(?:niente|senza|no|evitare|evitando|escluso|esclusi)\s+(?:ee|eea|tratti esposti|escursionisti esperti)\b/
		)
	)
		setDiff(['T', 'E']);
	else if (take(text, /\b(?:ciaspol\w*|racchette da neve|eai)\b/)) setDiff(['EAI']);
	else if (take(text, /\b(?:ferrata|ferrate|eea|attrezzat\w*)\b/)) setDiff(['EEA']);
	else if (take(text, /\b(?:turistic\w*)\b/)) setDiff(['T']);
	else if (take(text, /\b(?:facil\w*|semplic\w*|principianti|tranquill\w*)\b/)) setDiff(['T', 'E']);
	else if (take(text, /\b(?:ee|esperti|impegnativ\w*|difficil\w*)\b/)) setDiff(['EE', 'EEA']);

	// bambini e famiglie (come il preset «Facile con bambini», se non già detto altro)
	if (take(text, /\b(?:con|per)\s+(?:i\s+)?(?:bambin\w*|famigli\w*|ragazzi)\b/)) {
		if (!f.difficulties.length) setDiff(['T', 'E']);
		if (f.maxMinutes == null) f.maxMinutes = 150;
		if (f.maxUp == null) f.maxUp = 400;
	}

	// tipo di percorso
	const addType = (t: RouteType) => !f.types.includes(t) && f.types.push(t);
	if (take(text, /\b(?:ad\s+)?anell\w*\b|\bgiro\b|\bcircolare\b/)) addType('anello');
	if (take(text, /\btraversat\w*\b/)) addType('traversata');
	if (take(text, /\bandata e ritorno\b|\ba\/r\b/)) addType('andata_ritorno');

	// desideri: luoghi lungo il percorso
	const addTag = (t: Tag) => !f.tags.includes(t) && f.tags.push(t);
	if (take(text, /\blag(?:o|hi|hetto|hetti)\b/)) addTag('lago');
	if (take(text, /\b(?:cima|cime|vetta|vette)\b/)) addTag('cima');
	if (take(text, /\b(?:rifugi\w*|malga|malghe|baita|pranzo al rifugio)\b/)) addTag('rifugio');
	if (take(text, /\b(?:acqua|fontan\w*|sorgent\w*)\b/)) addTag('acqua');
	if (take(text, /\b(?:panoram\w*|vista|belvedere)\b/)) addTag('panorama');

	// stagione
	const monthIndex = MONTH_WORDS.findIndex((w) => new RegExp(`\\b${w}\\b`).test(text.value));
	if (monthIndex >= 0) {
		f.month = monthIndex + 1;
		take(text, new RegExp(`\\b(?:a|in|di)?\\s*${MONTH_WORDS[monthIndex]}\\b`));
	} else if (take(text, /\b(?:d'estate|in estate|estiv\w*)\b/)) f.month = 7;
	else if (take(text, /\b(?:in autunno|autunnal\w*)\b/)) f.month = 10;
	else if (take(text, /\b(?:in primavera|primaveril\w*)\b/)) f.month = 5;
	else if (take(text, /\b(?:in inverno|invernal\w*)\b/)) f.month = 1;

	// fonte
	if (take(text, /\b(?:in programma|in calendario|prossim\w*|future)\b/)) f.futureOnly = true;
	if (take(text, /\b(?:attivita|gite?)\s+(?:cai|sat|delle sezioni|sociali)\b|\bgite sociali\b/))
		f.sources = ['attivita', 'archivio'];

	return { filters: f, place, unsupported };
}

export type PlaceRow = [string, string, number, number, number | null];

const KIND_PRIORITY: Record<string, number> = {
	p: 0,
	f: 1,
	r: 2,
	c: 3,
	l: 4,
	s: 5,
	v: 6,
	b: 7,
	g: 8
};

/** Luogo più adatto per un nome: identico prima di simile, poi paesi prima di altri tipi. */
export function resolvePlace(query: string, places: PlaceRow[]): PlaceRow | null {
	const q = fold(query)
		.replace(/[^a-z0-9]+/g, ' ')
		.trim();
	if (!q) return null;
	let best: { row: PlaceRow; score: number } | null = null;
	for (const row of places) {
		const name = fold(row[0])
			.replace(/[^a-z0-9]+/g, ' ')
			.trim();
		const parts = name.split(/\s+-\s+|\s*\/\s*/);
		let score = -1;
		if (name === q || parts.includes(q)) score = 100;
		else if (name.startsWith(q + ' ') || name.endsWith(' ' + q) || name.includes(` ${q} `))
			score = 60;
		else if (name.includes(q)) score = 30;
		if (score < 0) continue;
		score -= KIND_PRIORITY[row[1]] ?? 9;
		if (!best || score > best.score) best = { row, score };
	}
	return best?.row ?? null;
}
