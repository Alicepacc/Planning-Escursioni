# Fase 0 – Ricognizione e fondamenta: rapporto di checkpoint

Data: 13/11/2026. Tutto ciò che è scritto qui è stato eseguito e osservato; ciò che non è
stato possibile verificare è indicato come tale.

## 1. Cosa è stato fatto

| Voce della SPEC (§11, Fase 0) | Esito |
|---|---|
| Monorepo `apps/web`, `services/ingest`, `services/routing`, `infra/` | fatto |
| Linting, test, CI | fatto: 28 test Python, 8 test web, lint e build verdi in locale e nella CI di GitHub Actions (prima esecuzione riuscita il 13/11) |
| Verifica di ogni fonte del §6 con script di campionamento | fatto: 15 script, registro in `docs/data-sources.md` |
| Spike di routing GraphHopper vs BRouter sulla fixture | fatto: `reports/phase0/routing-spike/` |
| Scelta dello stack | proposta in `docs/decisions/0001-stack.md` |

## 2. Stato delle fonti

**Utilizzabili così come sono (9):** SAT sentieri, Waymarked Trails, Mapterhorn, basemap
(Protomaps / OpenFreeMap), Open-Meteo, avalanche.report, micro-regioni EAWS, Nominatim, GTFS.

**Utilizzabili con riserve (6):**

| Fonte | Riserva |
|---|---|
| Estratto OSM | Geofabrik non raggiungibile da qui e OSM-FR vieta i client automatici: si usa Estratti OSM Italia (non copre il Tirolo) |
| OSM2CAI | Funziona per sentieri e metadati; dettaglio itinerari e POI per bbox rispondono 500; legenda `sda` 0-2 non documentata; l'indice per bbox non lavora per intersezione |
| Sezioni CAI | 7 siti su 8 espongono i PDF via API WordPress; sito di CAI Merano da confermare; locandina della fixture non trovata |
| Open Data Hub | Nel campione i record con licenza aperta non hanno traccia né distanza; quelli completi sono «Closed» |
| DTM provinciali | Bolzano ok (WCS, CC0); Trento da individuare (il LiDAR è comunque dentro Mapterhorn) |
| Overpass | Istanza principale non raggiungibile da qui; serve solo in sviluppo |

**Nessuna fonte è del tutto inutilizzabile.**

### Le quattro scoperte che cambiano i piani

1. **Esiste un'API strutturata delle attività CAI** (`organizzazione.cai.it/wp-json/cai-activities/v1`:
   ricerca per regione, sezione, difficoltà e date). È riservata ai frontend del CAI (risponde
   403 senza header `Origin`) e non è stata aggirata. Se il CAI ne autorizza l'uso diventa la
   fonte primaria delle gite future e i PDF servono solo per i dettagli e per l'archivio: il
   pilota della Fase 2 cambierebbe forma. **Vale la pena chiederlo insieme alla conferma
   scritta sui dati.**
2. **I numeri dei sentieri non sono univoci** (due «332», due «360» e due «326» nella sola
   regione) e **l'indice per bbox di OSM2CAI non lavora per intersezione**: la ricostruzione
   delle tracce deve filtrare per distanza dalla partenza e la sincronizzazione deve usare gli
   indici per regione.
3. **Open-Meteo limita per indirizzo IP** (10.000 chiamate al giorno): da un IP cloud
   condiviso il limite era già esaurito. In produzione servono cache lato server e IP proprio.
4. **Open Data Hub vale meno del previsto** per le proposte: i dati aperti sono «ridotti».

## 3. Spike di routing

Entrambi i motori ricostruiscono l'anello della locandina entro le tolleranze del §2:

| | Dichiarato | GraphHopper | BRouter |
|---|---|---|---|
| Distanza | 15,5 km | 15,62 km (+0,8%) | 15,72 km (+1,4%) |
| Dislivello (DEM, isteresi 10 m) | 950 m | 980 m (+3,1%) | 989 m (+4,1%) |
| Quota massima (SRTM 30 m) | 2.253 m | 2.232 m | 2.232 m |
| Tempo DIN 33466 sui valori calcolati | 7:00 | 7:10 | 7:15 |

(scenario con 5 waypoint; con tutti i 12 punti chiave la distanza sale a +6%).
La mappa `routing-spike/map-rado.png` mostra le due tracce sovrapposte ai sentieri citati.

**Scelta proposta: GraphHopper**, per i modelli personalizzabili a ogni richiesta e perché
restituisce l'identificativo OSM di ogni tratto. Dettagli, numeri e conseguenze in
`docs/decisions/0002-motore-di-routing.md`.

Tre lezioni per le fasi successive: il dislivello va ricalcolato dal DEM (quello nativo di
GraphHopper è +35-41%); i punti chiave vanno trattati come «passa vicino»; la difficoltà
calcolata dai tag (E) è più bassa di quella dichiarata dalla sezione (EE), che deve prevalere.

## 4. Stack proposto

SvelteKit + TypeScript + MapLibre per il frontend; Python (uv) per l'ingestion; GraphHopper
per il routing; PostGIS (Supabase o self-hosted, da decidere con il budget). Motivazioni in
`docs/decisions/0001-stack.md`.

## 5. Cosa non è stato verificato

- I file Docker (`infra/docker-compose.yml`, `services/routing/Dockerfile`): scritti ma mai
  eseguiti (in questo ambiente non c'è Docker).
- Geofabrik e l'istanza principale di Overpass: irraggiungibili da questo ambiente.
- L'estrazione dei PMTiles con la CLI `pmtiles` (binario non scaricabile da qui).
- La copertura di `name:de` in Alto Adige (il campione è trentino).
- I tratti «a mano libera» fuori sentiero: nella fixture la salita alla cima è mappata in OSM.
- La legenda completa di `sda` (0-2).

## 6. Come è stato condotto il lavoro

La SPEC chiede subagenti in parallelo: i quattro lanciati per la ricognizione si sono
interrotti dopo pochi minuti per il limite d'uso dell'account. Le verifiche sono state quindi
completate in sequenza, riusando le risposte che avevano già scaricato.

## 7. Domande per l'utente

Vedi il messaggio di checkpoint: nome e dominio, budget, uso commerciale o no, sezioni del
pilota, contatto per lo User-Agent, conferma scritta del CAI, account da socia.
