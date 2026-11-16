import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
	din33466Hours,
	formatHours,
	formatMinutes,
	personalMinutes,
	swissMinutesPerKm,
	swissSegmentMinutes
} from './time';

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

describe('modello CAI / Sentieri Svizzeri', () => {
	it.each([
		[100, 20],
		[300, 49],
		[-100, 14],
		[-300, 27.5]
	])('1 km con %i m di dislivello ≈ %f min (SPEC §8)', (dh, expected) => {
		expect(Math.abs(swissSegmentMinutes(1000, dh) - expected)).toBeLessThanOrEqual(0.5);
	});

	it('in piano va a 4,2 km/h', () => {
		expect(60 / swissMinutesPerKm(0)).toBeCloseTo(4.2, 2);
	});

	it('limita la pendenza a ±40%', () => {
		expect(swissMinutesPerKm(70)).toBe(swissMinutesPerKm(40));
		expect(swissMinutesPerKm(-70)).toBe(swissMinutesPerKm(-40));
	});

	it('coincide con il modulo Python sugli stessi casi', () => {
		// valori calcolati da services/ingest (cordata_ingest.timing)
		expect(swissSegmentMinutes(1000, 100)).toBeCloseTo(20.0, 1);
		expect(swissSegmentMinutes(1000, 300)).toBeCloseTo(48.8, 1);
		expect(swissSegmentMinutes(1000, -300)).toBeCloseTo(27.5, 1);
	});
});

describe('fattori personali', () => {
	it('moltiplica allenamento, gruppo e soste', () => {
		expect(personalMinutes(100, { fitness: 0.7, group: 1.5, stops: 1.2 })).toBeCloseTo(126);
		expect(() => personalMinutes(100, { fitness: 2 })).toThrow(RangeError);
		expect(() => personalMinutes(100, { stops: 0.9 })).toThrow(RangeError);
	});

	it('formatta i minuti', () => {
		expect(formatMinutes(350)).toBe('5:50');
		expect(formatMinutes(42, 1)).toBe('0:42');
	});
});
