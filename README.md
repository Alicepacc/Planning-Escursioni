# Cordata (nome provvisorio)

Progressive Web App mobile-first per programmare escursioni in montagna con soli dati aperti:
proposte in stile «gita sociale CAI», planner agganciato ai sentieri, uscite di gruppo, meteo
in quota e bollettino valanghe. Specifica completa in [`docs/SPEC.md`](docs/SPEC.md).

**Stato: Fase 0 (ricognizione e fondamenta) completata, in attesa del checkpoint.**
Rapporto: [`reports/phase0/README.md`](reports/phase0/README.md).

## Struttura

| Cartella | Contenuto |
|---|---|
| `apps/web` | PWA SvelteKit (per ora: guscio dell'app, i18n, pagina Fonti e licenze) |
| `services/ingest` | Python: client HTTP «educato», verifiche delle fonti, geometria e tempi |
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
# web
cd apps/web
pnpm install
pnpm run lint && pnpm run check && pnpm run test && pnpm run build
pnpm run dev
```

Routing e spike: vedi [`services/routing/README.md`](services/routing/README.md).

## Regole del progetto

- Solo dati aperti, con attribuzione visibile: [`docs/data-sources.md`](docs/data-sources.md).
- Rispetto dei server altrui: [`docs/decisions/0003-rispetto-dei-server.md`](docs/decisions/0003-rispetto-dei-server.md).
- Nessun dato personale delle locandine e nessuna credenziale nel repository.
