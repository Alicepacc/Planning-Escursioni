import { describe, expect, it } from 'vitest';
import {
	EMPTY_FILTERS,
	PRESETS,
	chipsFor,
	filterItems,
	haversineKm,
	removeChip,
	sortItems,
	sourceOf,
	type ExploreItem
} from './explore';

function item(over: Partial<ExploreItem>): ExploreItem {
	return {
		id: 'x',
		k: 's',
		t: 'Sentiero',
		sub: '',
		src: 'Catasto CAI (OSM2CAI)',
		min: 180,
		km: 8,
		up: 500,
		dn: 500,
		max: 1800,
		d: 'E',
		ty: 'anello',
		s: [11.35, 46.5],
		b: [11.3, 46.45, 11.4, 46.55],
		p: [],
		tag: [],
		mo: [6, 7, 8, 9, 10],
		sda: 4,
		...over
	};
}

describe('filtri di Esplora', () => {
	const lago = item({ id: 'lago', tag: ['lago'], min: 120, up: 300 });
	const ee = item({ id: 'ee', d: 'EE', min: 420, up: 1200, max: 2700, mo: [7, 8, 9] });
	const eai = item({
		id: 'eai',
		k: 'a',
		d: 'EAI',
		fut: true,
		mo: [12, 1, 2, 3],
		date: '2026-12-20'
	});
	const items = [lago, ee, eai];

	it('preset «Facile con bambini»', () => {
		const f = PRESETS.find((p) => p.id === 'bambini')!.apply(EMPTY_FILTERS);
		expect(filterItems(items, f).map((i) => i.id)).toEqual(['lago']);
	});

	it('difficoltà, stagione e solo attività in programma', () => {
		expect(filterItems(items, { ...EMPTY_FILTERS, difficulties: ['EE'] })).toEqual([ee]);
		expect(filterItems(items, { ...EMPTY_FILTERS, month: 1 })).toEqual([eai]);
		expect(filterItems(items, { ...EMPTY_FILTERS, futureOnly: true })).toEqual([eai]);
		expect(sourceOf(eai)).toBe('attivita');
	});

	it('«Panoramico» vale anche per chi tocca una cima', () => {
		const cima = item({ id: 'cima', tag: ['cima'] });
		expect(filterItems([cima, lago], { ...EMPTY_FILTERS, tags: ['panorama'] })).toEqual([cima]);
	});

	it('distanza da un luogo e area della mappa', () => {
		const far = item({ id: 'far', s: [12.5, 46.9], b: [12.4, 46.8, 12.6, 47.0] });
		const near = { lon: 11.35, lat: 46.5, label: 'Bolzano', km: 10 };
		expect(filterItems([lago, far], { ...EMPTY_FILTERS, near })).toEqual([lago]);
		expect(filterItems([lago, far], { ...EMPTY_FILTERS, area: [12, 46.7, 13, 47.1] })).toEqual([
			far
		]);
		expect(Math.round(haversineKm([11.35, 46.5], [11.35, 46.6]))).toBe(11);
	});

	it('ordinamenti e chip removibili', () => {
		expect(sortItems(items, 'durata', EMPTY_FILTERS)[0].id).toBe('lago');
		expect(sortItems(items, 'rilevanza', EMPTY_FILTERS)[0].id).toBe('eai');
		const f = { ...EMPTY_FILTERS, tags: ['lago' as const], maxMinutes: 210 };
		const chips = chipsFor(f);
		expect(chips.map((c) => c.label)).toEqual(['fino a 3:30 h', 'Lago']);
		expect(removeChip(f, 'tag:lago').tags).toEqual([]);
		expect(removeChip(f, 'maxMinutes').maxMinutes).toBeNull();
	});
});
