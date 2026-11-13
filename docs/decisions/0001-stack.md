# ADR 0001 – Stack e struttura del repository

- **Stato**: proposta, da confermare al checkpoint della Fase 0
- **Data**: 13/11/2026

## Decisione

Monorepo con quattro aree:

| Cartella | Contenuto | Strumenti |
|---|---|---|
| `apps/web` | PWA mobile-first | SvelteKit 3 (Svelte 5), TypeScript, Vitest, ESLint, Prettier, pnpm |
| `services/ingest` | Verifica fonti, sincronizzazioni, pipeline attività CAI | Python ≥ 3.11, uv, httpx, pyosmium, shapely, PyMuPDF, pytest, ruff |
| `services/routing` | Motore di routing e spike | GraphHopper 11 (Java 21) |
| `infra` | Ambiente locale | Docker Compose: PostGIS 16 + GraphHopper |

Dati scaricati e cache stanno in `data/` (non versionata); fixture in `fixtures/`; report
ripetibili in `reports/`.

## Motivazioni

- **SvelteKit invece di Next.js**: bundle più leggero (obiettivo LCP < 2,5 s su 4G), niente
  runtime React da idratare sopra MapLibre, rendering statico o SSR per la pagina invito, e
  gpx.studio (MIT) dimostra che SvelteKit + MapLibre + GraphHopper regge un planner completo.
- **Python per l'ingestion**: le librerie che servono (pyosmium, shapely, PyMuPDF) sono
  mature lì; il frontend non ne dipende.
- **Formule duplicate con fixture condivisa**: DIN 33466 esiste in Python
  (`cordata_ingest.timing`) e in TypeScript (`apps/web/src/lib/hiking/time.ts`) perché serve
  sia nell'ingestion sia nel planner offline. Entrambe sono testate contro
  `fixtures/golden/val-d-inferno.json`.
- **PostGIS / Supabase**: confermato come default della SPEC, ma non ancora installato: la
  Fase 0 non ne ha bisogno. La scelta tra Supabase gestito e PostGIS self-hosted dipende dal
  budget (domanda aperta per l'utente).

## Conseguenze e punti aperti

- L'adapter SvelteKit è ancora `adapter-auto`: si fissa quando è deciso l'hosting.
- `infra/docker-compose.yml` e `services/routing/Dockerfile` non sono stati eseguiti in
  questo ambiente (nessun demone Docker): vanno provati in locale o in CI.
- La CI (`.github/workflows/ci.yml`) esegue lint, type-check, test e build; le verifiche
  delle fonti fanno chiamate di rete e restano manuali.
