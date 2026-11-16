import { describe, expect, it } from 'vitest';
import { seasonMonths, seasonText } from './season';

describe('periodo consigliato', () => {
	it('dipende dalla quota massima, le ciaspolate in inverno', () => {
		expect(seasonText(seasonMonths(2253, 'EE'))).toBe('da giugno a ottobre');
		expect(seasonText(seasonMonths(2600, 'E'))).toBe('da luglio a settembre');
		expect(seasonText(seasonMonths(2490, 'EAI'))).toBe('da dicembre a marzo');
	});
});
