// Esplora (SPEC §5.1): filtri, preset, ordinamento e distanze sull'indice generato da
// services/ingest/src/cordata_ingest/build/explore.py. Funzioni pure, testate a parte.

export type ItemKind = 's' | 'a' | 'i';
export type RouteType = 'anello' | 'andata_ritorno' | 'traversata';
export type Tag = 'lago' | 'cima' | 'rifugio' | 'acqua' | 'panorama';
export type Difficulty = 'T' | 'E' | 'EE' | 'EEA' | 'EAI';
export type Source = 'attivita' | 'archivio' | 'itinerari' | 'catasto' | 'osm';
export type SortKey = 'rilevanza' | 'distanza' | 'durata' | 'dislivello' | 'data';
export type BBox = [number, number, number, number];
export type LonLat = [number, number];

/** Voce dell'indice (nomi corti per tenere il file leggero). */
export interface ExploreItem {
	id: string;
	k: ItemKind;
	t: string;
	sub: string;
	src: string;
	date?: string | null;
	fut?: boolean;
	/** null quando il dato non è dichiarato e la traccia non è verificata */
	min: number | null;
	km: number | null;
	up: number | null;
	dn: number | null;
	max: number | null;
	d: string | null;
	ty: string;
	s: LonLat;
	b: BBox;
	p: number[];
	tag: string[];
	mo: number[];
	sda?: number | null;
	iss?: string | null;
	ok?: boolean;
}

export interface ExploreIndex {
	schema: number;
	generated_at: string;
	items: ExploreItem[];
}

export interface NearFilter {
	lon: number;
	lat: number;
	label: string;
	km: number;
}

export interface Filters {
	text: string;
	minMinutes: number | null;
	maxMinutes: number | null;
	minKm: number | null;
	maxKm: number | null;
	maxUp: number | null;
	minUp: number | null;
	minEle: number | null;
	maxEle: number | null;
	difficulties: Difficulty[];
	types: RouteType[];
	tags: Tag[];
	month: number | null;
	sources: Source[];
	futureOnly: boolean;
	near: NearFilter | null;
	area: BBox | null;
}

export const EMPTY_FILTERS: Filters = {
	text: '',
	minMinutes: null,
	maxMinutes: null,
	minKm: null,
	maxKm: null,
	maxUp: null,
	minUp: null,
	minEle: null,
	maxEle: null,
	difficulties: [],
	types: [],
	tags: [],
	month: null,
	sources: [],
	futureOnly: false,
	near: null,
	area: null
};

export const TAG_LABEL: Record<Tag, string> = {
	lago: 'Lago',
	cima: 'Cima',
	rifugio: 'Rifugio',
	acqua: 'Punto acqua',
	panorama: 'Panoramico'
};

export const TYPE_LABEL: Record<RouteType, string> = {
	anello: 'Anello',
	andata_ritorno: 'Andata e ritorno',
	traversata: 'Traversata'
};

export const SOURCE_LABEL: Record<Source, string> = {
	attivita: 'Attività CAI in programma',
	archivio: 'Archivio attività CAI',
	itinerari: 'Itinerari',
	catasto: 'Catasto sentieri CAI',
	osm: 'Rete OSM'
};

export const MONTHS = [
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

export function haversineKm(a: LonLat, b: LonLat): number {
	const r = Math.PI / 180;
	const dLat = (b[1] - a[1]) * r;
	const dLon = (b[0] - a[0]) * r;
	const h =
		Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dLon / 2) ** 2;
	return 2 * 6371 * Math.asin(Math.sqrt(h));
}

export function sourceOf(item: ExploreItem): Source {
	if (item.k === 'a') return item.fut ? 'attivita' : 'archivio';
	if (item.k === 'i') return 'itinerari';
	return item.sda ? 'catasto' : 'osm';
}

/** Le ciaspolate (EAI) sono un'etichetta a parte; "E-EE" vale per entrambe. */
function difficultyMatches(item: ExploreItem, wanted: Difficulty[]): boolean {
	if (!wanted.length) return true;
	if (!item.d) return false;
	const parts = item.d.toUpperCase().startsWith('EAI') ? ['EAI'] : item.d.toUpperCase().split('-');
	return parts.some((p) => wanted.includes(p as Difficulty));
}

/** «Panoramico» vale anche per le tracce che toccano una cima. */
function tagMatches(item: ExploreItem, tag: Tag): boolean {
	if (tag === 'panorama') return item.tag.includes('panorama') || item.tag.includes('cima');
	return item.tag.includes(tag);
}

function normalizeText(text: string): string {
	return text
		.toLowerCase()
		.normalize('NFD')
		.replace(/[̀-ͯ]/g, '')
		.replace(/[^a-z0-9]+/g, ' ')
		.trim();
}

export function textScore(item: ExploreItem, query: string): number {
	const words = normalizeText(query).split(' ').filter(Boolean);
	if (!words.length) return 1;
	const hay = normalizeText(`${item.t} ${item.sub} ${item.src}`);
	const hits = words.filter((w) => hay.includes(w)).length;
	return hits / words.length;
}

function intersects(a: BBox, b: BBox): boolean {
	return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
}

/** Dato sconosciuto (null): escluso quando il filtro su quel dato è attivo. */
function outside(value: number | null, min: number | null, max: number | null): boolean {
	if (min == null && max == null) return false;
	if (value == null) return true;
	return (min != null && value < min) || (max != null && value > max);
}

export function matches(item: ExploreItem, f: Filters): boolean {
	if (f.text && textScore(item, f.text) < 1) return false;
	if (outside(item.min, f.minMinutes, f.maxMinutes)) return false;
	if (outside(item.km, f.minKm, f.maxKm)) return false;
	if (outside(item.up, f.minUp, f.maxUp)) return false;
	if (outside(item.max, f.minEle, f.maxEle)) return false;
	if (!difficultyMatches(item, f.difficulties)) return false;
	if (f.types.length && !f.types.includes(item.ty as RouteType)) return false;
	if (f.tags.some((t) => !tagMatches(item, t))) return false;
	if (f.month != null && !item.mo.includes(f.month)) return false;
	if (f.sources.length && !f.sources.includes(sourceOf(item))) return false;
	if (f.futureOnly && !item.fut) return false;
	if (f.near && haversineKm(item.s, [f.near.lon, f.near.lat]) > f.near.km) return false;
	if (f.area && !intersects(item.b, f.area)) return false;
	return true;
}

export function filterItems(items: ExploreItem[], f: Filters): ExploreItem[] {
	return items.filter((item) => matches(item, f));
}

/** Rilevanza: attività verificate, poi catasto validato (sda 4), poi aderenza al testo. */
function relevance(item: ExploreItem, f: Filters): number {
	let score = textScore(item, f.text);
	if (item.k === 'a') score += item.ok ? 3 : 2;
	if (item.k === 'i') score += 3;
	if (item.sda === 4) score += 1;
	if (item.iss && /percorribile/i.test(item.iss) && !/non/i.test(item.iss)) score += 0.2;
	return score;
}

export function sortItems(
	items: ExploreItem[],
	key: SortKey,
	f: Filters,
	origin: LonLat | null = null
): ExploreItem[] {
	const out = [...items];
	const from = f.near ? ([f.near.lon, f.near.lat] as LonLat) : origin;
	switch (key) {
		case 'distanza':
			if (from) out.sort((a, b) => haversineKm(a.s, from) - haversineKm(b.s, from));
			break;
		case 'durata':
			out.sort((a, b) => (a.min ?? Infinity) - (b.min ?? Infinity));
			break;
		case 'dislivello':
			out.sort((a, b) => (a.up ?? Infinity) - (b.up ?? Infinity));
			break;
		case 'data':
			out.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''));
			break;
		default:
			out.sort((a, b) => relevance(b, f) - relevance(a, f));
	}
	return out;
}

export interface Preset {
	id: string;
	label: string;
	apply: (f: Filters) => Filters;
	active: (f: Filters) => boolean;
}

/** Preset rapidi (§5.1): ogni preset imposta filtri visibili e modificabili. */
export const PRESETS: Preset[] = [
	{
		id: 'mezza',
		label: 'Mezza giornata',
		apply: (f) => ({ ...f, minMinutes: null, maxMinutes: 210 }),
		active: (f) => f.maxMinutes === 210 && f.minMinutes == null
	},
	{
		id: 'intera',
		label: 'Giornata intera',
		apply: (f) => ({ ...f, minMinutes: 240, maxMinutes: 480 }),
		active: (f) => f.minMinutes === 240 && f.maxMinutes === 480
	},
	{
		id: 'bambini',
		label: 'Facile con bambini',
		apply: (f) => ({ ...f, difficulties: ['T', 'E'], maxMinutes: 150, maxUp: 400 }),
		active: (f) => f.maxMinutes === 150 && f.maxUp === 400 && f.difficulties.join() === 'T,E'
	},
	{
		id: 'panorama',
		label: 'Panoramico',
		apply: (f) => ({ ...f, tags: withTag(f.tags, 'panorama') }),
		active: (f) => f.tags.includes('panorama')
	},
	{
		id: 'laghi',
		label: 'Laghi',
		apply: (f) => ({ ...f, tags: withTag(f.tags, 'lago') }),
		active: (f) => f.tags.includes('lago')
	},
	{
		id: 'cima',
		label: 'Cima',
		apply: (f) => ({ ...f, tags: withTag(f.tags, 'cima') }),
		active: (f) => f.tags.includes('cima')
	}
];

function withTag(tags: Tag[], tag: Tag): Tag[] {
	return tags.includes(tag) ? tags : [...tags, tag];
}

export interface Chip {
	key: keyof Filters | `tag:${Tag}` | `type:${RouteType}` | `diff:${Difficulty}` | `src:${Source}`;
	label: string;
}

function hm(minutes: number): string {
	const h = Math.floor(minutes / 60);
	const m = minutes % 60;
	return m ? `${h}:${String(m).padStart(2, '0')} h` : `${h} h`;
}

/** I filtri attivi come chip: ogni chip si può togliere con `removeChip`. */
export function chipsFor(f: Filters): Chip[] {
	const chips: Chip[] = [];
	if (f.text) chips.push({ key: 'text', label: `«${f.text}»` });
	if (f.minMinutes != null || f.maxMinutes != null) {
		const label =
			f.minMinutes != null && f.maxMinutes != null
				? `${hm(f.minMinutes)} – ${hm(f.maxMinutes)}`
				: f.maxMinutes != null
					? `fino a ${hm(f.maxMinutes)}`
					: `almeno ${hm(f.minMinutes!)}`;
		chips.push({ key: 'maxMinutes', label });
	}
	if (f.minKm != null || f.maxKm != null)
		chips.push({
			key: 'maxKm',
			label:
				f.minKm != null && f.maxKm != null
					? `${f.minKm}–${f.maxKm} km`
					: f.maxKm != null
						? `fino a ${f.maxKm} km`
						: `almeno ${f.minKm} km`
		});
	if (f.minUp != null || f.maxUp != null)
		chips.push({
			key: 'maxUp',
			label:
				f.minUp != null && f.maxUp != null
					? `${f.minUp}–${f.maxUp} m D+`
					: f.maxUp != null
						? `D+ fino a ${f.maxUp} m`
						: `D+ almeno ${f.minUp} m`
		});
	if (f.minEle != null) chips.push({ key: 'minEle', label: `sopra i ${f.minEle} m` });
	if (f.maxEle != null) chips.push({ key: 'maxEle', label: `sotto i ${f.maxEle} m` });
	for (const d of f.difficulties) chips.push({ key: `diff:${d}`, label: d });
	for (const t of f.types) chips.push({ key: `type:${t}`, label: TYPE_LABEL[t] });
	for (const t of f.tags) chips.push({ key: `tag:${t}`, label: TAG_LABEL[t] });
	if (f.month != null) chips.push({ key: 'month', label: `adatto a ${MONTHS[f.month - 1]}` });
	for (const s of f.sources) chips.push({ key: `src:${s}`, label: SOURCE_LABEL[s] });
	if (f.futureOnly) chips.push({ key: 'futureOnly', label: 'solo in programma' });
	if (f.near) chips.push({ key: 'near', label: `entro ${f.near.km} km da ${f.near.label}` });
	if (f.area) chips.push({ key: 'area', label: "in quest'area" });
	return chips;
}

export function removeChip(f: Filters, key: Chip['key']): Filters {
	const [kind, value] = key.split(':') as [string, string | undefined];
	switch (kind) {
		case 'tag':
			return { ...f, tags: f.tags.filter((t) => t !== value) };
		case 'type':
			return { ...f, types: f.types.filter((t) => t !== value) };
		case 'diff':
			return { ...f, difficulties: f.difficulties.filter((d) => d !== value) };
		case 'src':
			return { ...f, sources: f.sources.filter((s) => s !== value) };
		case 'maxMinutes':
			return { ...f, minMinutes: null, maxMinutes: null };
		case 'maxKm':
			return { ...f, minKm: null, maxKm: null };
		case 'maxUp':
			return { ...f, minUp: null, maxUp: null };
		case 'futureOnly':
			return { ...f, futureOnly: false };
		case 'text':
			return { ...f, text: '' };
		default:
			return { ...f, [kind]: null };
	}
}
