# services/ingest

Pipeline dei dati di Cordata: verifica delle fonti, sincronizzazioni, calcoli (quote, tempi,
difficoltà) e file statici per la PWA. Gira in fase di build, non in produzione (ADR 0005).

## Prerequisiti

- Python ≥ 3.11 con [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16 con PostGIS 3, `osm2pgsql`, `osmium-tool`, `tippecanoe`
  (Ubuntu: `apt-get install postgresql-16-postgis-3 osm2pgsql osmium-tool tippecanoe`;
  macOS: `brew install postgis osm2pgsql osmium-tool tippecanoe`)
- Database `cordata` raggiungibile; l'indirizzo si imposta con `CORDATA_DB_URL`
  (default `postgresql://cordata:cordata-dev@localhost:5432/cordata`)

```bash
cd services/ingest
uv sync --extra geo
uv run ruff check . && uv run pytest
```

## Pipeline completa

Tutti i comandi partono dalla radice del repository. I dati scaricati finiscono in `data/`
(non versionata), i file per la PWA in `apps/web/static/data` e `apps/web/static/tiles`
(anch'essi non versionati).

```bash
# 1. estratti OSM (Estratti OSM Italia: robots.txt senza divieti, aggiornamento giornaliero)
curl -o data/osm/trentino-alto-adige.osm.pbf "https://osmit-estratti.wmcloud.org/output/pbf/regioni/04_Trentino-Alto_Adige-S%C3%BCdtirol.osm.pbf"
curl -o data/osm/veneto.osm.pbf "https://osmit-estratti.wmcloud.org/output/pbf/regioni/05_Veneto.osm.pbf"
osmium merge data/osm/trentino-alto-adige.osm.pbf data/osm/veneto.osm.pbf -O -o data/osm/taa-veneto.osm.pbf
# fascia di confine (ADR 0013): province confinanti dentro la stessa bbox
for p in 014_Sondrio 017_Brescia 030_Udine 093_Pordenone; do
  curl -o data/osm/confine/$p.osm.pbf "https://osmit-estratti.wmcloud.org/output/pbf/province/$p.osm.pbf"
done
# estratti di date diverse: un oggetto di confine può comparire in due versioni, si tiene l'ultima
osmium merge data/osm/taa-veneto.osm.pbf data/osm/confine/*.osm.pbf -O -o data/osm/confine/merged.osh.pbf
osmium time-filter data/osm/confine/merged.osh.pbf -O -o data/osm/confine/merged-now.osm.pbf
osmium extract --bbox 10.38,45.67,12.75,47.10 --strategy smart -O -o data/osm/pilot.osm.pbf data/osm/confine/merged-now.osm.pbf
```

```bash
# 2. import in PostGIS (≈20 s per l'area pilota)
osm2pgsql -O flex -S services/ingest/osm/flex.lua -d cordata data/osm/pilot.osm.pbf
```

```bash
# 3. catasto CAI: sincronizzazione incrementale (≈1 h la prima volta, poi solo le modifiche)
cd services/ingest && uv run python -m cordata_ingest.osm2cai sync --regions C,B --sda 3,4
```

```bash
# 4. tabelle derivate, tile, schede e itinerario d'esempio
cd services/ingest && uv run python -m cordata_ingest.build all
```

```bash
# 5. calibrazione di dislivello e tempi contro i valori ufficiali (report in reports/phase1)
cd services/ingest && uv run python -m cordata_ingest.calibration
```

### Pipeline attività CAI (Fase 2, pilota)

```bash
cd services/ingest
uv run python -m cordata_ingest.activities discover     # metadati dei PDF delle sezioni pilota
uv run python -m cordata_ingest.activities archive      # solo i candidati di config/pilot/candidates.yaml
uv run python -m cordata_ingest.activities extract      # testo, OCR (tesseract-ocr ita+deu), dati personali rimossi
uv run python -m cordata_ingest.activities gazetteer    # luoghi OSM con nome in PostGIS (osmium)
uv run python -m cordata_ingest.activities reconstruct  # tracce (GraphHopper avviato); --solo-parser
uv run python -m cordata_ingest.activities report       # reports/pilot-<data>/pilot.html
```

Nessun crawler periodico: l'estensione a tutte le sezioni aspetta l'approvazione del pilota.

## Moduli

| Modulo | Cosa fa |
|---|---|
| `http.py` | Client HTTP «educato»: User-Agent, cache, rate limit, backoff, robots.txt (ADR 0003) |
| `probes/` | Verifiche delle fonti (Fase 0): `python -m cordata_ingest.probes` |
| `osm2cai/` | Sincronizzazione incrementale del catasto CAI per regione e `sda` |
| `geo/` | Distanze, ricampionamento lungo la traccia, DEM (SRTM, Mapterhorn), profilo |
| `timing.py` | Tempi: modello CAI / Sentieri Svizzeri e DIN 33466 (ADR 0007) |
| `difficulty.py` | Scala CAI, mappatura indicativa da `sac_scale`, colore del segnavia |
| `build/` | PostGIS → PMTiles e documenti JSON per la PWA |
| `calibration.py` | Calibrazione di dislivello e tempi contro OSM2CAI |
| `activities/` | Locandine CAI: scoperta, archivio privato, testo, parser, gazetteer, ricostruzione, rapporto |
| `osm/flex.lua` | Configurazione di osm2pgsql |
| `sql/derive.sql` | Tabelle `trails` e `trail_ways` |

## Regole

- Tutte le richieste passano da `PoliteClient` (niente chiamate sparse).
- Niente valori inventati: se una fonte non risponde, la verifica lo registra.
- Nessun dato personale (capigita, telefoni, email) nei file salvati o versionati.
