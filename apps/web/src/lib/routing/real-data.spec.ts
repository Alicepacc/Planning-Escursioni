// Prova sul grafo vero (solo dove la pipeline ha generato i tasselli; in CI si salta).
import { existsSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { TrailGraph, loadArea, snap, type GraphIndex, type RawTile } from './graph';
import { routeBetween } from './router';
import { routeStats } from './stats';

const DIR = 'static/data/grafo';
const hasData = existsSync(`${DIR}/index.json`);

describe.skipIf(!hasData)("grafo vero: fixture Val d'Inferno", () => {
	it('anello lungo i punti chiave entro le tolleranze di auto_ok (±10% km, ±15% D+)', async () => {
		const index = JSON.parse(readFileSync(`${DIR}/index.json`, 'utf8')) as GraphIndex;
		const g = new TrailGraph(index);
		// punti chiave della fixture (geocodificati dalla pipeline della Fase 2)
		const pts: [number, number][] = [
			[11.5218, 46.149], // Tedon
			[11.5445, 46.1347], // Rifugio Caldenave
			[11.5522, 46.1421], // Laghi della Val d'Inferno
			[11.5505, 46.1508], // Cima Nassere
			[11.5577, 46.1583], // Laghetto del Cengello
			[11.5452, 46.1722], // Cucuzzolo dei Morti
			[11.54, 46.1704], // Malga Conseria
			[11.5293, 46.1619], // Ponte Conseria
			[11.5218, 46.149] // Tedon
		];
		const lons = pts.map((p) => p[0]);
		const lats = pts.map((p) => p[1]);
		const t0 = performance.now();
		await loadArea(
			g,
			[Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)],
			async (k) => JSON.parse(readFileSync(`${DIR}/${k}.json`, 'utf8')) as RawTile
		);
		const legs = [];
		for (let i = 0; i + 1 < pts.length; i++) {
			const a = snap(g, ...pts[i], 2)!;
			const b = snap(g, ...pts[i + 1], 2)!;
			const leg = routeBetween(g, a, b, { maxDiff: 2 });
			expect(leg).not.toBeNull();
			legs.push(leg!);
		}
		const st = routeStats(legs);
		console.log(
			`fixture: ${st.km.toFixed(1)} km, +${Math.round(st.up)}/-${Math.round(st.down)} m, max ${Math.round(st.maxEle!)} m, ${Math.round(st.minutes)} min, ${Math.round(performance.now() - t0)} ms, ${g.loaded.size} tasselli`
		);
		expect(Math.abs(st.km - 15.5) / 15.5).toBeLessThan(0.1);
		expect(Math.abs(st.up - 950) / 950).toBeLessThan(0.15);
		expect(Math.abs(st.maxEle! - 2253)).toBeLessThan(50);
	});
});
