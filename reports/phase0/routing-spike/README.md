# Spike di routing – fixture «Val d'Inferno e Cima Nassere»

Confronto GraphHopper 11.1 / BRouter 1.6.3 sull'anello della locandina (dichiarati: 15,5 km,
±950 m, quota massima 2.253 m, 7:00 h). Decisione in `docs/decisions/0002-motore-di-routing.md`.

| File | Contenuto |
|---|---|
| `table.md` | Tabella completa di tutti gli scenari |
| `results.json` | Tutte le metriche (dislivello grezzo e filtrato, quote, sequenza dei sentieri, scostamenti dei waypoint) |
| `tracks.geojson` | Tracce calcolate, sentieri citati, punti chiave |
| `map-rado.png`, `map-completo.png` | Screenshot delle tracce su mappa (MapLibre + OpenFreeMap) |
| `map-*.html` | Le stesse mappe, navigabili |

## Cosa mostrano le mappe

Le due tracce seguono la sequenza della locandina: Tedon → strada forestale Campivelo →
Caldenave e rifugio → laghi della Val d'Inferno → Lago Nassere → Cima Nassere (andata e ritorno
dal bivio) → Laghetto del Cengello → Cucuzzolo dei Morti → Malga Conseria → Ponte Conseria →
Tedon. GraphHopper e BRouter divergono solo in due brevi tratti (accesso al rifugio e una
variante tra Ponte Conseria e Tedon).

## Limiti dello spike

- Il DEM di confronto è SRTM 1" (30 m): sottostima la cima di 21 m. La calibrazione della
  soglia di isteresi con un DEM più fine è della Fase 1.
- La «traccia fuori sentiero» verso Cima Nassere citata dalla locandina in OSM è mappata come
  sentiero: lo spike non ha quindi provato i tratti a mano libera.
- La quota di traccia «sui sentieri citati» è circa il 50%: il resto dell'anello percorre
  strade forestali e altri sentieri segnati, coerenti con le reti che la locandina nomina
  senza numero (Sentiero Italia, Translagorai…): quali esattamente va verificato nella Fase 2.
- Geocodifica dei punti chiave fatta a mano sugli oggetti OSM
  (`services/routing/spike/val_inferno_waypoints.json`): quella automatica è della Fase 2.
