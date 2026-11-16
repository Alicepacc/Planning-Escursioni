import { describe, expect, it } from 'vitest';
import { parseQuery, resolvePlace, type PlaceRow } from './nl';

describe('ricerca in linguaggio naturale', () => {
	it("l'esempio della SPEC diventa filtri visibili", () => {
		const r = parseQuery(
			'anello di 5-6 ore con un lago, partenza raggiungibile in treno da Bolzano, niente EE'
		);
		expect(r.filters.types).toEqual(['anello']);
		expect([r.filters.minMinutes, r.filters.maxMinutes]).toEqual([300, 360]);
		expect(r.filters.tags).toEqual(['lago']);
		expect(r.filters.difficulties).toEqual(['T', 'E']);
		expect(r.place).toEqual({ query: 'Bolzano', km: 15, approx: null });
		expect(r.unsupported[0]).toMatch(/mezzi pubblici/);
	});

	it('durate, dislivelli, quote e stagioni', () => {
		const r = parseQuery(
			'giornata intera sopra i 2000 metri, massimo 900 m di dislivello, ad agosto'
		);
		expect([r.filters.minMinutes, r.filters.maxMinutes]).toEqual([240, 480]);
		expect(r.filters.minEle).toBe(2000);
		expect(r.filters.maxUp).toBe(900);
		expect(r.filters.month).toBe(8);
	});

	it('bambini, ciaspole e raggio in minuti', () => {
		const kids = parseQuery('qualcosa di facile con i bambini e una malga');
		expect(kids.filters.difficulties).toEqual(['T', 'E']);
		expect(kids.filters.maxMinutes).toBe(150);
		expect(kids.filters.tags).toEqual(['rifugio']);
		const snow = parseQuery('ciaspolata entro 40 minuti da Merano');
		expect(snow.filters.difficulties).toEqual(['EAI']);
		expect(snow.place?.query).toBe('Merano');
		expect(snow.place?.km).toBe(24);
		expect(snow.place?.approx).toMatch(/40 minuti/);
	});

	it('luoghi scritti in minuscolo e nomi con «Lago»', () => {
		expect(parseQuery('traversata vicino a bressanone').place?.query).toBe('Bressanone');
		const garda = parseQuery('giro panoramico vicino al Lago di Garda');
		expect(garda.place?.query).toBe('Lago di Garda');
		expect(garda.filters.tags).toEqual(['panorama']);
	});

	it('risolve il luogo preferendo il nome identico e i paesi', () => {
		const places: PlaceRow[] = [
			['Rifugio Bolzano - Schlernhaus', 'r', 11.6, 46.5, 2457],
			['Bozen - Bolzano', 'p', 11.35, 46.5, 262]
		];
		expect(resolvePlace('Bolzano', places)?.[1]).toBe('p');
		expect(resolvePlace('Schlernhaus', places)?.[1]).toBe('r');
		expect(resolvePlace('Trento', places)).toBeNull();
	});
});
