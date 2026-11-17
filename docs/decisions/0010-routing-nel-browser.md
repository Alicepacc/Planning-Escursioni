# ADR 0010 – Routing del planner nel browser, su tasselli del grafo dei sentieri

- **Stato**: accettata (scelta dell'utente, 17/11/2026)
- **Data**: 17/11/2026

## Contesto

Il planner (SPEC §5.3) aggancia il percorso ai sentieri con un motore di routing. Alla Fase 0
(ADR 0002, 0005) GraphHopper doveva girare sul Mac dell'utente, esposto con Tailscale Funnel; la
demo però è un sito statico su GitHub Pages, senza server, e deve funzionare anche a Mac spento.
I client non possono usare servizi pubblici gratuiti (SPEC §3).

## Decisione

- La pipeline (`services/ingest`, passo `graph`) prepara il **grafo pedonale** dell'area pilota
  dall'estratto OSM in PostGIS: vie percorribili a piedi divise agli incroci, forme semplificate,
  per ogni arco lunghezza, salita e discesa dal DEM (Mapterhorn), difficoltà (scala CAI del
  catasto se il tratto è in un sentiero ufficiale, altrimenti dedotta da `sac_scale`), classe
  della via, segnavia, visibilità della traccia e segnalazioni OSM2CAI.
- Il grafo è diviso in **tasselli** (0,1° × 0,05°, circa 7,7 × 5,6 km): il browser scarica solo
  quelli attorno ai punti del percorso.
- Il **routing gira nel browser** (A* sul tempo stimato con il modello CAI, con preferenza per i
  sentieri segnati e penalità per le strade): i tratti oltre la difficoltà massima scelta sono
  esclusi; i tratti «a mano libera» sono linee dirette segnalate come tali.
- GraphHopper resta il motore della pipeline delle attività (ricostruzione delle tracce).

## Conseguenze

- Costo zero, nessun server, funziona su GitHub Pages e in futuro offline (i tasselli sono
  file statici da mettere in cache).
- Il grafo deve restare leggero: si escludono vie private e vietate ai pedoni e si semplificano
  le forme; i dati derivano da OpenStreetMap (ODbL) e lo si dichiara.
- Le prestazioni dipendono dal dispositivo: percorsi fino a qualche decina di km sono il caso
  d'uso; per tratte più lunghe servono più tasselli e più tempo.
