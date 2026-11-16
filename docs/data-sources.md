# Registro delle fonti dati

Verifica della Fase 0, eseguita il 12-13/11/2026 sull'area campione del Lagorai (fixture
«Val d'Inferno e Cima Nassere»). Ogni riga è prodotta da uno script ripetibile:

```bash
cd services/ingest
uv run --extra geo python -m cordata_ingest.probes            # tutte le fonti
uv run --extra geo python -m cordata_ingest.probes osm2cai    # una sola
```

Gli esiti completi (controlli, URL provati, note) sono in `reports/phase0/sources/<id>.json`; i
campioni scaricati restano in `data/samples/` (non versionati). Stati: **ok** = verificata e
utilizzabile; **parziale** = utilizzabile con i limiti indicati; **da verificare** = serve
un'azione manuale.

Le verifiche sono state fatte da un ambiente cloud: alcuni host bloccano quegli indirizzi IP
(vedi le note). Dove un dato non è stato verificato è scritto esplicitamente.

## Riepilogo

| Fonte (id script) | Cosa fornisce | Licenza letta | Uso nel progetto | Aggiornamento | Stato |
|---|---|---|---|---|---|
| **OpenStreetMap, estratto regionale** (`osm_extract`) | Relazioni `route=hiking`, sentieri con `sac_scale`, POI | ODbL 1.0 | Base di tutto: grafo, sentieri, POI, ricostruzione tracce | Giornaliero alla fonte; import settimanale | ok (con cambio di fonte, vedi sotto) |
| **OSM2CAI** (`osm2cai`) | Catasto sentieri CAI: `cai_scale`, tempi, dislivelli, percorribilità | ODbL 1.0 (confermata dal CAI per email) | Fonte primaria dei metadati dei sentieri CAI | Settimanale (sincronizzazione con OSM) | ok, 3 endpoint secondari rotti |
| **Sezioni CAI** (`cai_sections`) | PDF di locandine e programmi | Contenuti protetti: solo sintesi con data e link alla fonte (indicazione del CAI) | Attività future e archivio (pilota Fase 2) | Irregolare | parziale |
| **SAT sentieri** (`sat_trails`) | 1.080 tracciati GPX/KML/SHP del Trentino | ODbL 1.0, «© Società degli Alpinisti Tridentini (SAT)» | Confronto e arricchimento in Trentino | Mensile | ok |
| **Waymarked Trails** (`waymarked_trails`) | Relazioni escursionistiche con geometria ordinata | ODbL 1.0 (dati OSM) | Verifica incrociata dell'ordinamento | Non verificato | ok (API diversa dalla SPEC) |
| **Overpass API** (`overpass`) | Query puntuali su OSM | ODbL 1.0 | Solo sviluppo e debug | – | parziale (istanza principale irraggiungibile da qui) |
| **Open Data Hub** (`opendatahub`) | Itinerari turistici, webcam | Per record: CC0 oppure «Closed» | Proposte aggiuntive e webcam (Fase 3) | Continuo | parziale: i record aperti non hanno traccia |
| **Mapterhorn** (`mapterhorn`) | Tile del terreno Terrarium (WebP 512 px, PMTiles) | Copernicus GLO-30; TINITALY CC BY 4.0; LiDAR Trentino CC BY 2.5 | Hillshade, 3D, profilo altimetrico | Per versione | ok |
| **DTM provinciali** (`dtm_provinciali`) | DTM 2,5 m e 0,5 m dell'Alto Adige (WCS) | Bolzano CC0; Trento da confermare | Dislivello più preciso in Alto Adige | Pluriennale | parziale (Trento da individuare) |
| **Basemap** (`basemap`) | Protomaps (PMTiles) e OpenFreeMap (tile + stili) | ODbL 1.0 | Mappa di base | Protomaps giornaliero | ok |
| **Open-Meteo** (`open_meteo`) | Previsione oraria con quota, zero termico, CAPE; Elevation API | CC BY 4.0, solo uso non commerciale | Meteo in quota (Fase 6), fallback quote | Orario | ok (attenzione ai limiti per IP) |
| **avalanche.report** (`avalanche_report`) | Bollettino valanghe Euregio CAAMLv6 | CC BY 4.0 | Blocco Condizioni invernale (Fase 6) | Giornaliero in stagione | ok |
| **EAWS regions** (`eaws_regions`) | Poligoni delle micro-regioni | CC0 1.0 | Intersezione traccia ↔ bollettino | Raro | ok |
| **Nominatim** (`nominatim`) | Geocoding | ODbL 1.0 | Solo ripiego lato server | – | ok |
| **GTFS** (`gtfs`) | Orari e fermate STA e Trentino Trasporti | STA CC0; Trentino CC BY 4.0 | Filtro «raggiungibile con i mezzi» (fase successiva) | Per cambio orario | ok |

## Dettaglio per fonte

### OpenStreetMap – estratto regionale
- **Accesso verificato**: `https://osmit-estratti.wmcloud.org/output/pbf/regioni/04_Trentino-Alto_Adige-Südtirol.osm.pbf`
  (113 MB, aggiornato ogni giorno; `robots.txt` senza divieti). Esistono anche estratti per
  provincia e per comune (usati nei test: comune di Scurelle, 0,4 MB).
- **Differenza dalla SPEC**: Geofabrik chiude la connessione da questo ambiente (non
  verificabile da qui) e OSM-FR vieta i client automatici (`Disallow: /`). Un primo download di
  prova da OSM-FR, fatto prima di leggere il suo `robots.txt`, è stato sostituito con
  l'estratto di Estratti OSM Italia. Decisione in `docs/decisions/0004-estratto-osm.md`.
- **Limite**: gli estratti italiani non coprono il Tirolo; per l'area pilota servono
  Trentino-Alto Adige e Veneto, uniti in un unico grafo. La copertura del Tirolo (Geofabrik) è
  da decidere quando servirà.
- **Qualità nella bbox Lagorai**: 59 relazioni `route=hiking` (ref 85%, `cai_scale` 69%,
  `osmc:symbol` 76%, `duration:forward` 63%, `ascent` 59%); `ref:REI` assente, il prefisso SAT
  sta in `reg_ref` (es. `E332`); 67% dei `path` ha `sac_scale`. Tutti i punti chiave e i tre
  sentieri della fixture sono presenti. `name:it`/`name:de` sono vuoti in Trentino (attesi
  solo in Alto Adige: da verificare su un campione altoatesino nella Fase 1).
- **Attenzione**: i numeri dei sentieri non sono univoci (due «332», due «360», due «326»
  nella regione): il filtro per distanza dalla partenza del §7.4 è indispensabile.

### OSM2CAI – catasto sentieri CAI
- **Licenza**: il catasto (INFOMONT) è distribuito dal CAI con licenza **ODbL**; lo conferma la
  risposta scritta del CAI (`docs/legal/2026-11-cai-risposta-uso-dati.md`) e la pagina
  [Copyright e licenza](https://catastorei.gitbook.io/documentazione-osm2cai/informazioni-legali/copyright-e-licenza)
  della documentazione ufficiale. **Attribuzione richiesta**: «© OpenStreetMap contributors» con
  link a `https://www.openstreetmap.org/copyright`; indicazione della licenza ODbL; «© Club
  Alpino Italiano – INFOMONT» con link a `https://infomont.cai.it`. I database derivati vanno
  condivisi con la stessa licenza.
- **Documentazione**: `https://catastorei.gitbook.io/documentazione-osm2cai` (ogni pagina è
  disponibile anche in Markdown aggiungendo `.md`); OpenAPI su
  `https://osm2cai.cai.it/docs?api-docs.json` (30 path). Nessuna chiave. Header
  `X-RateLimit-Limit: 60` (al minuto).
- **Aggiornamento**: OSM2CAI si sincronizza con OpenStreetMap **una volta alla settimana**
  (documentazione, pagina «Modello dati»).
- **Stato di accatastamento (`sda`)**, dalla tabella della documentazione: 0 = non rilevato e
  senza `cai_scale`; 1 = non rilevato, con `cai_scale`; 2 = rilevato (`source=survey:CAI`),
  senza `cai_scale`; 3 = rilevato e con `cai_scale`; 4 = importato in INFOMONT (validato dal
  CAI). Gli stati 0-3 sono assegnati automaticamente dai tag OSM, il 4 a mano dai referenti.
- **Stato di percorribilità**: percorribile, parzialmente percorribile, non percorribile, non
  rilevato, con data e descrizione. Il CAI avverte che non è capillare né in tempo reale.
- **Verificato**: indici `{id: updated_at}`; dettaglio GeoJSON con `cai_scale`, `distance`,
  `ascent`/`descent`, `duration_forward`/`backward`, `ele_*`, `issues_*`, `validation_date`.
  Fixture: 332 → id 12711 (E, 11,9 km, +1428/−958 m, 315/270 min); 360 → id 12692 (E, 7,5 km,
  +821/−630 m, 195/165 min); 326 → id 12729 (E, 7,7 km, +918/−383 m, 210/150 min); tutti
  `sda` 4, validati nel 2023, percorribilità «sconosciuto».
- **Dimensioni**: bbox pilota → 1.844 sentieri `sda` 4 e 858 `sda` 3. Codici regione CAI:
  `C` = Trentino-Alto Adige (1.138 `sda` 4), `B` = Veneto (485 `sda` 4).
- **Sorprese**:
  - l'indice per bbox non funziona per semplice intersezione: il 332 (11,9 km) compare nella
    bbox Lagorai ma non in quella stretta della fixture. Per la sincronizzazione si usano gli
    indici per regione;
  - `/api/v2/itinerary/{id}` risponde 500 e non è documentato (esiste solo
    `/itinerary/list`, 32 itinerari); `/api/v2/ecpois/bb/{bbox}/N` risponde 500;
  - i GPX hanno `<ele>0</ele>`: le quote vanno sempre dal DEM.
- **Backend per i soci**: i soci con profilo MyCAI possono consultarlo in sola lettura. L'app
  non lo usa; eventuali verifiche manuali non vanno ripubblicate (SPEC §13-bis).

### Siti delle sezioni CAI
- **Configurazione**: `config/sources/cai_sections.yaml`.
- **Verificato** (API REST WordPress `/wp-json/wp/v2/media?mime_type=application/pdf`, header
  `X-WP-Total`, filtro `after=` funzionante): Bolzano 116 PDF, Appiano 33, Vipiteno 4 (su
  `organizzazione.cai.it`); Bressanone 194, Brunico 121, Mestre 613, SAT 1.133 (siti propri
  WordPress). `robots.txt` vieta solo `/wp-admin/`.
- **PDF campione**: locandina di Bolzano (1 pagina, 2.750 caratteri) e libretto di Appiano
  (21 pagine, 33.000 caratteri) hanno testo estraibile senza OCR. Il Quaderno n. 1 CCE è
  raggiungibile (104 pagine, testuale): serve per il modello dei tempi della Fase 1.
- **Sorprese**:
  - **esiste un'API strutturata delle attività** (`organizzazione.cai.it/wp-json/cai-activities/v1`:
    ricerca per regione, sezione, difficoltà, date) ma risponde 403 «Origin header mancante»:
    è riservata ai frontend del CAI. Non è stata aggirata e **non verrà usata senza
    un'autorizzazione esplicita** (SPEC §13-bis). Se il CAI la concede diventa la fonte
    primaria delle gite future e i PDF passano a fonte secondaria;
  - il nome del file è un segnale debole (un prefisso con data cattura anche una «Guida
    all'iscrizione online»); il fallback `wp-sitemap.xml` su Bolzano risponde 404;
  - CAI Merano non è su `organizzazione.cai.it` e il dominio `caimerano.it` non sembra più
    della sezione: **sito ufficiale da confermare**;
  - la locandina reale della fixture non è stata trovata (ricerca sul sito di Mestre).
- **Uso consentito** (risposta del CAI): sintesi dei contenuti con data e link alla fonte;
  niente riproduzione sistematica e integrale. Quindi niente PDF ripubblicati: si mostrano i
  fatti estratti e una sintesi propria, con il link all'originale.
- **Pilota**: sezioni scelte il 16/11/2026: Bolzano, Appiano, Vipiteno.
- **Privacy**: nei file versionati non c'è alcun nome o recapito di persone.

### SAT – sentieri del Trentino
- **Accesso**: `https://sentieri.sat.tn.it/download/sentierisat.{gpx,kml,shp}.zip` (GPX: 5 MB,
  1.080 tracce divise in `est/` e `ovest/`, es. `est/E332.gpx`). GPX e KML in WGS84, Shapefile
  in EPSG:25832. Quote assenti.
- **Licenza letta** su `https://www.sat.tn.it/sentieri/mappa-sentieri/`: ODbL; attribuzione
  «© Società degli Alpinisti Tridentini (SAT)» con link a `https://www.sat.tn.it/sentieri/`.
- **Uso**: confronto e arricchimento; non sovrascrive OSM (la pagina stessa avverte che solo
  parte dei tracciati viene da rilievo GPS di precisione).

### Waymarked Trails
- **Verificato**: `/api/v1/list/by_area?bbox=` (la bbox va in **EPSG:3857**), `/list/search`,
  `/details/relation/{id}`.
- **Differenza dalla SPEC**: l'export `/details/relation/{id}/geometry/gpx` risponde 404. Il
  dettaglio JSON contiene già la geometria ordinata (`route.main[].ways[]`, EPSG:3857), che è
  ciò che serve per la verifica dell'ordinamento.

### Overpass API
- L'istanza principale chiude la connessione da questo ambiente; l'istanza
  `maps.mail.ru/osm/tools/overpass` risponde (59 relazioni nella bbox Lagorai).
- **Regole lette** nella documentazione: al massimo circa 10.000 richieste e 1 GB al giorno.
- In produzione non serve: i dati arrivano dall'estratto locale.

### Open Data Hub Alto Adige
- **Accesso**: `https://tourism.api.opendatahub.com/v1/ODHActivityPoi?tagfilter=hiking`, anonimo,
  con filtro `latitude`/`longitude`/`radius` e paginazione.
- **Risultato importante**: nel campione attorno a Merano (50 record su 1.053) i record con
  licenza aperta (CC0, fonte LTS) **non hanno traccia né distanza**; quelli con traccia (rete
  sentieri provinciale) sono «Closed». Nel Lagorai i record (fonte SIAT Provincia di Trento)
  sono tutti «Closed». Il valore di questa fonte per le proposte è quindi più basso di quanto
  ipotizzato: da riesaminare nella Fase 3 su un campione più ampio. Webcam: disponibili,
  licenze miste.

### Mapterhorn
- **Accesso**: `https://tiles.mapterhorn.com/{z}/{x}/{y}.webp` (TileJSON: Terrarium, 512 px);
  PMTiles su `https://download.mapterhorn.com/` (`planet.pmtiles` z0-12, 356 GB; riquadri z13+
  `6-33-22` e `6-34-22` per l'area pilota), da estrarre per bbox con `pmtiles extract`.
- **Verificato**: quota decodificata su Cima Nassere 2.240 m a z14 (OSM: 2.253 m; SRTM 30 m:
  2.232 m). Su quel punto l'endpoint non serve tile oltre z14.
- **Sorgenti sull'area**: LiDAR della Provincia di Trento (CC BY 2.5), TINITALY 10 m (CC BY
  4.0), Copernicus GLO-30. L'Alto Adige non ha una sorgente LiDAR dedicata.
- **Uso nella Fase 1**: è il DEM di riferimento per profili e dislivelli (campionamento a z12,
  13 m per pixel: sui punti chiave della fixture z12, z13 e z14 danno valori identici) e per
  l'ombreggiatura e le isoipse della mappa, calcolate nel browser dagli stessi tile. Scarto
  rispetto alle quote OSM dei punti chiave della fixture: entro ±4 m, tranne la cima (−12 m:
  le vette appuntite si smussano); SRTM 30 m sbaglia la cima di −21 m.

### DTM provinciali
- **Bolzano**: WCS `https://geoservices9.civis.bz.it/geoserver/ows`, coverage
  `p_bz-Elevation__DigitalTerrainModel-2.5m` (anche 0,5 m), EPSG:25832; un riquadro di prova è
  stato scaricato come GeoTIFF. Licenza CC0 nel catalogo provinciale.
- **Trento**: il WCS provinciale non elenca il DTM; il LiDAR è già dentro Mapterhorn. Download
  diretto e licenza **da verificare** alla fonte.

### Basemap
- **Protomaps**: build planetario giornaliero (139 GB) su `https://build.protomaps.com/`, da
  cui estrarre l'area pilota. **OpenFreeMap**: TileJSON e stili pronti (usati per gli
  screenshot dello spike); i termini vietano la raccolta automatica di tile salvo download
  offline fino a 3.000 tile o 50 MB.
- **Uso nella Fase 1**: la mappa usa lo stile OpenFreeMap «liberty» dall'istanza pubblica; i
  sentieri e i POI di Cordata sono un PMTiles proprio (3,1 MB per l'area pilota, generato con
  tippecanoe) servito insieme al sito. L'estrazione di un PMTiles della mappa di base serve
  solo per l'offline (Fase 7) e resta da provare con la CLI `pmtiles`.

### Open-Meteo
- **Verificato**: previsione oraria su Cima Nassere con `elevation=2253` e tutte le variabili
  del §5.5 (`freezing_level_height`, `cape`, raffiche…), senza valori nulli; Elevation API
  (2.227 m sulla cima, 1.371 m a Tedon).
- **Termini letti**: CC BY 4.0, uso gratuito solo non commerciale, meno di 10.000 chiamate al
  giorno, 5.000 l'ora, 600 al minuto.
- **Sorpresa**: i limiti sono **per IP**. Il 12/11 l'API ha risposto 429 «Daily API request
  limit exceeded» perché l'ambiente cloud condivide l'IP con altri. In produzione: cache lato
  server e IP proprio, oppure immagine self-hosted.

### avalanche.report e micro-regioni EAWS
- **Pattern confermato**: `https://static.avalanche.report/bulletins/{data}/{data}_EUREGIO_it_CAAMLv6.json`
  (301 verso `avalanche.report`), disponibile anche in `de` ed `en`.
- **Struttura verificata** sul 10/02/2026: gradi per fascia di quota (`lowerBound`/`upperBound`
  numerici o `treeline`), problemi con esposizioni, tendenza.
- **Fuori stagione**: il file del giorno risponde 404 e `latest` restituisce l'ultimo
  bollettino di maggio: l'app deve controllare `validTime`.
- **Micro-regioni**: `https://regions.avalanches.org/micro-regions/{regione}_micro-regions.geojson.json`
  (CC0). Cima Nassere cade in `IT-32-TN-08`, presente nel bollettino. I file contengono anche
  poligoni storici (`end_date`): vanno filtrati.

### Nominatim
- Policy letta: massimo 1 richiesta al secondo, User-Agent identificativo, niente
  autocomplete. Ricerca e reverse di prova corrette. Resta un ripiego lato server.

### GTFS
- **STA Alto Adige**: `https://gtfs.api.opendatahub.com/v1/dataset/sta-time-tables/raw` (154 MB,
  6.461 fermate, CC0, valido fino al 12/12/2026; anche GTFS-Realtime).
- **Trentino Trasporti extraurbano**: `https://www.trentinotrasporti.it/opendata/google_transit_extraurbano_tte.zip`
  (11 MB, 2.857 fermate di cui 82 nella bbox Lagorai, CC BY 4.0, valido fino al 25/06/2027).

## Regole comuni
- Tutte le chiamate passano da `cordata_ingest.http.PoliteClient` (User-Agent identificativo,
  cache, intervallo minimo per host, backoff su 429/5xx, `robots.txt`). Dettagli e l'unica
  eccezione ammessa in `docs/decisions/0003-rispetto-dei-server.md`.
- Il contatto dello User-Agent è l'URL del repository; `CORDATA_CONTACT` lo può sostituire.
