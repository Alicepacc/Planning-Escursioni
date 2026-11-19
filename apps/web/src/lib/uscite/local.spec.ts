import { describe, expect, it } from 'vitest';
import { romeDay, weekend } from './local';

describe('fine settimana in ora italiana', () => {
	it('da lunedì a venerdì: il sabato e la domenica che arrivano', () => {
		expect(weekend(new Date('2026-11-16T10:00:00Z'))).toEqual(['2026-11-21', '2026-11-22']); // lunedì
		expect(weekend(new Date('2026-11-20T22:30:00Z'))).toEqual(['2026-11-21', '2026-11-22']); // venerdì sera
	});
	it('di sabato o domenica: quello in corso, anche a cavallo della mezzanotte UTC', () => {
		expect(weekend(new Date('2026-11-21T08:00:00Z'))).toEqual(['2026-11-21', '2026-11-22']);
		// domenica 22 alle 00:30 in Italia è ancora sabato 21 in UTC
		expect(weekend(new Date('2026-11-21T23:30:00Z'))).toEqual(['2026-11-21', '2026-11-22']);
		expect(weekend(new Date('2026-11-22T20:00:00Z'))).toEqual(['2026-11-21', '2026-11-22']);
	});
	it('cambio di mese', () => {
		expect(weekend(new Date('2026-12-29T09:00:00Z'))).toEqual(['2027-01-02', '2027-01-03']);
		expect(romeDay('2026-12-31T23:30:00Z')).toBe('2027-01-01');
	});
});
