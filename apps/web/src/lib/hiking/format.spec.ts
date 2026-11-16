import { describe, expect, it } from 'vitest';
import { scaleInfo } from './difficulty';
import { formatDate, formatDuration, formatKm, formatMeters } from './format';

describe('formattazione', () => {
	it('usa le convenzioni italiane', () => {
		expect(formatKm(15.5)).toBe('15,5 km');
		expect(formatMeters(2253)).toBe('2.253 m');
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
		expect(scaleInfo('EAI')).toBeNull();
		expect(scaleInfo(null)).toBeNull();
	});
});
