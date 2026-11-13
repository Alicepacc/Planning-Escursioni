import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { din33466Hours, formatHours } from './time';

const fixturePath = fileURLToPath(
	new URL('../../../../../fixtures/golden/val-d-inferno.json', import.meta.url)
);
const fixture = JSON.parse(readFileSync(fixturePath, 'utf8'));

describe('DIN 33466', () => {
	it('restituisce 7:00 per la fixture golden Val d’Inferno', () => {
		const hours = din33466Hours(
			fixture.distanza_km,
			fixture.dislivello_salita_m,
			fixture.dislivello_discesa_m
		);
		expect(hours).toBeCloseTo(7.0, 1);
		expect(formatHours(hours)).toBe(fixture.durata_dichiarata);
	});

	it('somma il tempo maggiore e metà del minore', () => {
		expect(din33466Hours(8, 0, 0)).toBeCloseTo(2);
		expect(din33466Hours(2, 600, 0)).toBeCloseTo(2.25);
		expect(din33466Hours(0, 0, 1000)).toBeCloseTo(2);
	});

	it('arrotonda ai cinque minuti', () => {
		expect(formatHours(2.26)).toBe('2:15');
		expect(formatHours(0.99)).toBe('1:00');
		expect(formatHours(3.5, 1)).toBe('3:30');
	});
});
