import { describe, expect, it } from 'vitest';
import { scaleInfo } from './difficulty';
import { formatDate, formatDuration, formatKm, formatMeters } from './format';

describe('formattazione', () => {
	it('usa le convenzioni italiane', () => {
		expect(formatKm(15.5)).toBe('15,5 km');
		// in italiano (CLDR) le cifre si raggruppano da 5 in su: 2253 m, 12.345 m
		expect(formatMeters(2253)).toBe('2253 m');
		expect(formatMeters(12345)).toBe('12.345 m');
		expect(formatDuration(350)).toBe('5:50 h');
		expect(formatDate('2026-11-15')).toBe('15 novembre 2026');
	});

	it('gestisce i valori mancanti', () => {
		expect(formatKm(null)).toBe('–');
		expect(formatMeters(undefined)).toBe('–');
		expect(formatDuration(null)).toBe('–');
		expect(formatDate('')).toBe('–');
	});
});

describe('scala CAI', () => {
	it('riconosce le varianti e scarta i valori sconosciuti', () => {
		expect(scaleInfo('EEA:PD')?.code).toBe('EEA');
		expect(scaleInfo('ee')?.label).toBe('Escursionisti esperti');
		expect(scaleInfo('EAI-F')?.code).toBe('EAI'); // ciaspolate (SPEC §5.1)
		expect(scaleInfo('E-EE')?.code).toBe('EE'); // si mostra il grado più alto
		expect(scaleInfo('XYZ')).toBeNull();
		expect(scaleInfo(null)).toBeNull();
	});
});
