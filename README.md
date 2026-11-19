# Cordata (nome provvisorio)

Progressive Web App mobile-first per programmare escursioni in montagna con soli dati aperti:
proposte in stile «gita sociale CAI», planner agganciato ai sentieri, uscite di gruppo, meteo
in quota e bollettino valanghe. Specifica completa in [`docs/SPEC.md`](docs/SPEC.md).

**Stato: Fase 4 (planner e generatore di proposte) completata.** Pilota della Fase 2
approvato il 16/11/2026. In corso i blocchi di ingestion delle locandine (78 escursioni in app).
Rapporti: [`reports/ingestion/README.md`](reports/ingestion/README.md) ·
[`reports/phase4/README.md`](reports/phase4/README.md) ·
[`reports/phase3/README.md`](reports/phase3/README.md) ·
[`reports/pilot-2026-11-16/README.md`](reports/pilot-2026-11-16/README.md) ·
[`reports/phase1/README.md`](reports/phase1/README.md) ·
[`reports/phase0/README.md`](reports/phase0/README.md).

## Struttura

| Cartella | Contenuto |
|---|---|
| `apps/web` | PWA SvelteKit: Esplora (escursioni delle sezioni CAI dalle locandine), schede con profilo altimetrico, mappa dei sentieri del catasto con legenda, planner con routing nel browser e «Componi un giro», pagina Fonti e licenze |
| `services/ingest` | Python: verifiche delle fonti, sincronizzazione OSM2CAI, import OSM in PostGIS, quote e tempi, tile e schede per la PWA ([README](services/ingest/README.md)) |
| `services/routing` | GraphHopper: configurazione, Dockerfile, spike sulla fixture |
| `infra` | Docker Compose per lo sviluppo locale |
| `config` | Aree geografiche e sezioni CAI |
| `fixtures` | Fixture golden «Val d'Inferno e Cima Nassere» |
| `docs` | Specifica, registro delle fonti, decisioni (ADR), documenti legali |
| `reports` | Report ripetibili prodotti dagli script |

## Comandi

```bash
# ingestion: lint, test, verifica delle fonti
cd services/ingest
uv sync --extra geo
uv run ruff check . && uv run pytest
CORDATA_CONTACT="https://esempio.it/contatti" uv run python -m cordata_ingest.probes
```

```bash
# web (i dati della mappa si generano con la pipeline di services/ingest)
cd apps/web
pnpm install
pnpm run lint && pnpm run check && pnpm run test && pnpm run build
pnpm run dev
pnpm run eval:generatore   # valutazione del generatore sulle gite reali (dati generati)
```

Routing e spike: vedi [`services/routing/README.md`](services/routing/README.md).

**Demo online** (GitHub Pages, sito statico): https://alicepacc.github.io/Planning-Escursioni/ —
si aggiorna con `scripts/deploy-gh-pages.sh` dopo aver rigenerato i dati.

## Regole del progetto

- Solo dati aperti, con attribuzione visibile: [`docs/data-sources.md`](docs/data-sources.md).
- Rispetto dei server altrui: [`docs/decisions/0003-rispetto-dei-server.md`](docs/decisions/0003-rispetto-dei-server.md).
- Nessun dato personale delle locandine e nessuna credenziale nel repository.
