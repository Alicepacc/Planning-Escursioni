import { describe, expect, it } from 'vitest';
import { fileName, toGpx, toKml, type TrackPoint } from './gpx';

const pts: TrackPoint[] = [
	[11.521522, 46.148609, 1350.4],
	[11.53, 46.15, 1400]
];

describe('esportazione della traccia', () => {
	it('GPX 1.1 con traccia, punti e nome protetto', () => {
		const gpx = toGpx("Anello <Val d'Inferno> & Nassere", pts, [
			{ name: 'Tedon', lon: 11.5215, lat: 46.1486, ele: 1350 }
		]);
		expect(gpx).toContain('<gpx version="1.1"');
		expect(gpx).toContain('<trkpt lat="46.148609" lon="11.521522"><ele>1350</ele></trkpt>');
		expect(gpx).toContain(
			'<wpt lat="46.148600" lon="11.521500"><ele>1350</ele><name>Tedon</name></wpt>'
		);
		expect(gpx).toContain("Anello &lt;Val d'Inferno&gt; &amp; Nassere");
	});

	it('KML con coordinate lon,lat,quota', () => {
		expect(toKml('Prova', pts)).toContain('11.521522,46.148609,1350 11.530000,46.150000,1400');
	});

	it('nome del file leggibile', () => {
		expect(fileName("Anello in Val d'Inferno e Cima Nassere (2253 m)", 'gpx')).toBe(
			'anello-in-val-d-inferno-e-cima-nassere-2253-m.gpx'
		);
	});
});
