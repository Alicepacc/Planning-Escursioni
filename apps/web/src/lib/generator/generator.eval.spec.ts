// Harness del generatore sulle gite reali (SPEC §5.7 a). Lento e legato ai dati generati:
// gira solo con CORDATA_EVAL=1 (npm run eval:generatore) e scrive il rapporto in
// reports/phase4/generatore/.
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import type { ItineraryDoc } from '../data/types';
import { PlannerEngine, bboxOf } from '../planner/engine';
import { searchRadiusKm } from './generator';
import {
	MATCH_COVERAGE,
	MATCH_TOLERANCE_M,
	TOP_K,
	evaluateActivity,
	inputsFor,
	summarize,
	type EvalRow
} from './evaluate';

const DATA = 'static/data';
const OUT = '../../reports/phase4/generatore';
const RUN = !!process.env.CORDATA_EVAL && existsSync(`${DATA}/grafo/index.json`);

function verifiedDocs(): ItineraryDoc[] {
	const docs: ItineraryDoc[] = [];
	for (const f of readdirSync(`${DATA}/attivita`)) {
		if (!f.endsWith('.json') || f === 'index.json') continue;
		const d = JSON.parse(readFileSync(`${DATA}/attivita/${f}`, 'utf8')) as ItineraryDoc;
		if (d.verification?.status === 'auto_ok') docs.push(d);
	}
	const fixture = `${DATA}/itinerari/val-d-inferno.json`;
	if (existsSync(fixture)) docs.push(JSON.parse(readFileSync(fixture, 'utf8')) as ItineraryDoc);
	return docs.sort((a, b) => a.id.localeCompare(b.id));
}

const pct = (x: number, n: number) => `${x}/${n} (${Math.round((100 * x) / Math.max(n, 1))}%)`;
const h = (m: number) => `${Math.floor(m / 60)}:${String(Math.round(m % 60)).padStart(2, '0')}`;

function markdown(rows: EvalRow[]): string {
	const s = summarize(rows);
	const lines = [
		'# Generatore di proposte: valutazione sulle gite reali',
		'',
		`Gite con traccia verificata: ${s.activities}. Una proposta «riscopre» la gita se almeno il ${MATCH_COVERAGE * 100}% di ciascun percorso è entro ${MATCH_TOLERANCE_M} m dall'altro. Al generatore si danno solo i vincoli che chiederebbe un utente (partenza, arrivo per le traversate, tipo, tempo ±20%, dislivello ±25%, difficoltà, mese, tipo di meta), mai la traccia.`,
		'',
		'| Misura | Valore |',
		'|---|---|',
		`| Gite con almeno una proposta | ${pct(s.withProposals, s.activities)} |`,
		`| Riscoperta nella 1ª proposta | ${pct(s.match1, s.activities)} |`,
		`| Riscoperta tra le prime 3 | ${pct(s.match3, s.activities)} |`,
		`| Riscoperta tra le prime ${TOP_K} | ${pct(s.match5, s.activities)} |`,
		`| Meta principale raggiunta da una delle prime ${TOP_K} | ${pct(s.destination5, s.activities)} |`,
		`| Copertura reciproca migliore (media) | ${Math.round(s.meanBestCoverage * 100)}% |`,
		`| Tempo medio di generazione | ${Math.round(s.meanMs)} ms |`,
		'',
		'| Gita | Tipo | Tempo | Diff. max | Meta | Proposte | Riscoperta | Copertura | Meta raggiunta |',
		'|---|---|---|---|---|---|---|---|---|'
	];
	for (const r of rows)
		lines.push(
			`| ${r.title} | ${r.type.replace('_', ' ')} | ${h(r.inputs.minMinutes)}–${h(r.inputs.maxMinutes)} | ${['T', 'E', 'EE', 'EEA'][r.inputs.maxDiff]} | ${r.destination ?? '–'} | ${r.proposals}${r.reason && !r.proposals ? ` (${r.reason})` : ''} | ${r.matchRank ? `sì, n. ${r.matchRank}` : 'no'} | ${Math.round(r.bestCoverage * 100)}% | ${r.destinationHit ? 'sì' : 'no'} |`
		);
	return lines.join('\n') + '\n';
}

describe.skipIf(!RUN)('valutazione del generatore sulle gite reali', () => {
	it('riscopre le gite delle sezioni', async () => {
		const engine = new PlannerEngine({
			fetchJson: async (name) => JSON.parse(readFileSync(`${DATA}/grafo/${name}`, 'utf8'))
		});
		const rows: EvalRow[] = [];
		for (const doc of verifiedDocs()) {
			const g = await engine.load();
			const opts = inputsFor(g!, doc); // la meta si calcola dopo aver caricato l'area
			const pts = [opts.start, ...(opts.end ? [opts.end] : [])];
			await engine.area(bboxOf(pts), searchRadiusKm(opts) + 1);
			const row = evaluateActivity(engine.graph!, doc);
			rows.push(row);
			console.log(
				`${row.title.slice(0, 50).padEnd(50)} prop ${row.proposals} riscoperta ${row.matchRank ?? '-'} cop ${Math.round(row.bestCoverage * 100)}% meta ${row.destinationHit ? 'sì' : 'no'} ${Math.round(row.ms)} ms`
			);
		}
		mkdirSync(OUT, { recursive: true });
		writeFileSync(
			`${OUT}/metrics.json`,
			JSON.stringify({ summary: summarize(rows), rows }, null, 2)
		);
		writeFileSync(`${OUT}/risultati.md`, markdown(rows));
		expect(rows.length).toBeGreaterThan(0);
	}, 900_000);
});
