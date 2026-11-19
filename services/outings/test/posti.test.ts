import { describe, expect, it } from 'vitest';
import { iscrizioniAperte, promossi, statoNuovaIscrizione, type Iscrizione } from '../src/posti';

const i = (utente: string, stato: Iscrizione['stato'], iscritto: string): Iscrizione => ({
	utente,
	stato,
	iscritto
});

describe('posti e lista d’attesa', () => {
	it('conferma finché ci sono posti, poi mette in attesa', () => {
		const list = [i('a', 'confermato', '1'), i('b', 'confermato', '2')];
		expect(statoNuovaIscrizione(3, list)).toBe('confermato');
		expect(statoNuovaIscrizione(2, list)).toBe('attesa');
		expect(statoNuovaIscrizione(null, list)).toBe('confermato');
		// chi ha rinunciato non occupa posti
		expect(statoNuovaIscrizione(2, [...list.slice(0, 1), i('b', 'rinunciato', '2')])).toBe('confermato');
	});

	it('fa scorrere la lista d’attesa in ordine di arrivo', () => {
		const list = [
			i('a', 'confermato', '1'),
			i('b', 'rinunciato', '2'),
			i('d', 'attesa', '4'),
			i('c', 'attesa', '3')
		];
		expect(promossi(2, list)).toEqual(['c']);
		expect(promossi(3, list)).toEqual(['c', 'd']);
		expect(promossi(1, list)).toEqual([]);
	});

	it('chiude le iscrizioni se l’uscita è annullata o il termine è passato', () => {
		expect(iscrizioniAperte('aperta', null, '2026-06-01T08:00:00Z')).toBe(true);
		expect(iscrizioniAperte('aperta', '2026-05-30T00:00:00Z', '2026-06-01T08:00:00Z')).toBe(false);
		expect(iscrizioniAperte('annullata', null, '2026-06-01T08:00:00Z')).toBe(false);
		expect(iscrizioniAperte('rinviata', null, '2026-06-01T08:00:00Z')).toBe(true);
	});
});
