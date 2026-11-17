import { describe, expect, it } from 'vitest';
import {
	keepTrackWhereRoutingDeviates,
	maxDeviationM,
	parseGpx,
	planFromTrack,
	simplifyIndices
} from './gpx-import';
import { isLoop, planFromParams, planToParams, rounded } from './plan';

// 6 km verso est con una curva: un punto ogni ~50 m
const pts = Array.from({ length: 121 }, (_, i) => ({
	lon: 11.5 + i * 0.00065,
	lat: 46.15 + 0.004 * Math.sin(i / 20)
}));
const gpx = `<?xml version="1.0"?>
<gpx version="1.1" creator="prova" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>Metadati</name></metadata>
  <trk><name>Giro &amp; ritorno</name><trkseg>
${pts.map((p, i) => `    <trkpt lon="${p.lon}" lat='${p.lat}'><ele>${1000 + i}</ele></trkpt>`).join('\n')}
    <trkpt lat="${pts[120].lat}" lon="${pts[120].lon}"/>
  </trkseg></trk>
</gpx>`;

describe('import GPX', () => {
	it('legge punti, nome e attributi in qualsiasi ordine; scarta i punti ripetuti', () => {
		const t = parseGpx(gpx);
		expect(t.name).toBe('Giro & ritorno');
		expect(t.points).toHaveLength(121);
		expect(t.points[0]).toEqual(pts[0]);
	});

	it('rifiuta file che non sono GPX o senza tracce', () => {
		expect(() => parseGpx('<kml></kml>')).toThrow(/GPX/);
		expect(() => parseGpx('<gpx><wpt lat="46" lon="11"/></gpx>')).toThrow(/tracce/);
		const rte = parseGpx(
			'<gpx><rte><rtept lat="46" lon="11"/><rtept lat="46.1" lon="11"/></rte></gpx>'
		);
		expect(rte.points).toHaveLength(2);
	});

	it('Douglas–Peucker tiene gli estremi e la forma', () => {
		const straight = Array.from({ length: 50 }, (_, i) => ({ lon: 11 + i * 0.001, lat: 46 }));
		expect(simplifyIndices(straight, 5)).toEqual([0, 49]);
		const kept = simplifyIndices(pts, 6);
		expect(kept[0]).toBe(0);
		expect(kept[kept.length - 1]).toBe(120);
		expect(kept.length).toBeLessThan(80);
		const simple = kept.map((i) => pts[i]);
		expect(
			maxDeviationM(
				pts.map((p) => [p.lon, p.lat, 0]),
				simple
			)
		).toBeLessThan(6.5);
	});

	it('«mantieni»: tratti a mano libera con la forma, e l’URL resta corto', () => {
		const { plan, sections } = planFromTrack(parseGpx(gpx), { snap: false, maxDiff: 1 });
		expect(plan.modes.every((m) => m === 'f')).toBe(true);
		expect(plan.points.length).toBeGreaterThanOrEqual(3);
		expect(plan.points.length).toBeLessThanOrEqual(5);
		expect(sections).toHaveLength(plan.modes.length);
		const back = planFromParams(planToParams(plan));
		expect(back.shapes).toEqual(plan.shapes);
		expect(planToParams(plan).toString().length).toBeLessThan(800);
	});

	it('una traccia che torna alla partenza diventa un anello', () => {
		const ring = Array.from({ length: 80 }, (_, i) => ({
			lon: 11.5 + 0.01 * Math.cos((2 * Math.PI * i) / 79),
			lat: 46.15 + 0.007 * Math.sin((2 * Math.PI * i) / 79) + (i === 79 ? 0.0002 : 0)
		}));
		const { plan, sections } = planFromTrack(
			{ name: '', points: ring },
			{ snap: false, maxDiff: 1 }
		);
		expect(isLoop(plan)).toBe(true);
		expect(sections[sections.length - 1].at(-1)).toEqual(plan.points[0]);
		expect(isLoop(planFromTrack(parseGpx(gpx), { snap: false, maxDiff: 1 }).plan)).toBe(false);
	});

	it('«aggancia»: punti ogni ~600 m; i tratti che deviano tornano sulla traccia', () => {
		const tp = planFromTrack(parseGpx(gpx), { snap: true, maxDiff: 1 });
		expect(tp.plan.modes.every((m) => m === 'r')).toBe(true);
		expect(tp.plan.points.length).toBeGreaterThanOrEqual(9);
		// tratti finti: il primo devia di ~300 m, gli altri coincidono con la traccia
		const legs = tp.sections.map((s, i) => ({
			points: s.map((p) => [p.lon, p.lat + (i === 0 ? 0.0027 : 0), 0] as [number, number, number]),
			freehand: false
		}));
		const { plan, replaced } = keepTrackWhereRoutingDeviates(tp, legs);
		expect(replaced).toBe(1);
		expect(plan.modes[0]).toBe('f');
		expect(plan.modes.slice(1).every((m) => m === 'r')).toBe(true);
		expect(plan.shapes[0]).toEqual(tp.sections[0].slice(1, -1).map(rounded));
	});
});
