# ADR 0004 – Fonte dell'estratto OpenStreetMap

- **Stato**: accettata per l'area pilota; da rivedere per il Tirolo
- **Data**: 13/11/2026

## Contesto

La SPEC indica l'estratto Geofabrik «Nord-Est Italia + Tirolo». Dall'ambiente di sviluppo
Geofabrik chiude la connessione (non verificabile) e l'alternativa OSM-FR vieta i client
automatici nel proprio `robots.txt`.

## Decisione

Usare **Estratti OSM Italia** (`https://osmit-estratti.wmcloud.org`, servizio di Wikimedia
Italia, aggiornamento giornaliero, `robots.txt` senza divieti):

- `output/pbf/regioni/04_Trentino-Alto_Adige-Südtirol.osm.pbf` (113 MB)
- `output/pbf/regioni/05_Veneto.osm.pbf` (242 MB)

Per i test bastano gli estratti comunali (Scurelle: 0,4 MB).

## Conseguenze

- I due estratti regionali vanno uniti prima dell'import (osmium merge): l'area dolomitica
  veneta è a cavallo del confine regionale.
- Il **Tirolo non è coperto**: se servirà (traversate di confine), si userà Geofabrik
  `europe/austria` da una rete in cui è raggiungibile, dopo aver verificato termini e limiti.
- Nota di trasparenza: il primo download di prova è stato fatto da OSM-FR prima di leggerne il
  `robots.txt`; il file è stato cancellato e sostituito.
