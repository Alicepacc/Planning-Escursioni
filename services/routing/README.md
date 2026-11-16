# services/routing

Routing escursionistico. Il motore scelto nella Fase 0 è **GraphHopper** (motivazioni e numeri
in `docs/decisions/0002-motore-di-routing.md`); BRouter resta documentato come confronto.

## GraphHopper in locale (senza Docker)

```bash
# 1. estratto OSM (fonte che ammette i download automatici, vedi docs/data-sources.md)
curl -A "Cordata/0.1 (+contatto)" -o data/osm/trentino-alto-adige.osm.pbf \
  "https://osmit-estratti.wmcloud.org/output/pbf/regioni/04_Trentino-Alto_Adige-S%C3%BCdtirol.osm.pbf"

# 2. GraphHopper 11.1 da Maven Central
curl -o data/routing/graphhopper/graphhopper-web-11.1.jar \
  https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/11.1/graphhopper-web-11.1.jar

# 3. avvio (il primo costruisce il grafo: ~25 s per il Trentino-Alto Adige, ~1,3 GB di RAM)
cd data/routing/graphhopper
java -Xmx5g -jar graphhopper-web-11.1.jar server ../../../services/routing/graphhopper/config.yml
```

Il server ascolta su `http://localhost:8989` (`/route`, `/info`, `/health`). L'altimetria usa i
tile SRTM 1" «skadi» di AWS Open Data, scaricati al primo import in `elevation-cache/`.

## Sul Mac di casa (produzione a costo zero, ADR 0005)

> Non ancora provato: questo ambiente di sviluppo non ha macOS. Da verificare insieme quando
> servirà il planner (Fase 4).

1. **Java 21**: `brew install openjdk@21` (oppure il pacchetto Temurin 21 per macOS).
2. **GraphHopper**: stessi passi della sezione precedente in una cartella, ad esempio
   `~/cordata-routing`, con l'estratto `pilot.osm.pbf` (vedi `services/ingest/README.md`).
   Il server ascolta solo su `localhost` (porte 8989 per il routing, 8990 per
   l'amministrazione: quest'ultima non va mai esposta).
3. **Avvio automatico**: un servizio `launchd` (file `.plist` in `~/Library/LaunchAgents`) che
   esegue `java -Xmx4g -jar graphhopper-web-11.1.jar server config.yml` e lo riavvia se si
   ferma. Il Mac non deve andare in stop mentre il planner è in uso.
4. **Esposizione su Internet con Tailscale Funnel**: serve la variante open source del client
   Tailscale per macOS (non quella dell'App Store). Si espone solo la porta del routing:
   `tailscale funnel --bg 8989` → `https://<nome-del-mac>.<tailnet>.ts.net`. Funnel accetta solo
   HTTPS e ha limiti di banda non configurabili ([documentazione](https://tailscale.com/kb/1223/funnel)).
5. **Aggiornamento settimanale del grafo**: nuovo estratto, cancellazione di `graph-cache`,
   riavvio del servizio.

Quando il Mac è spento l'app continua a funzionare: solo il planner «agganciato ai sentieri»
non risponde e lo dice chiaramente.

## BRouter (solo per lo spike)

```bash
cd data/routing/brouter
curl -O https://brouter.de/brouter_bin/brouter-1.6.3.zip && unzip brouter-1.6.3.zip
curl -o segments4/E10_N45.rd5 https://brouter.de/brouter/segments4/E10_N45.rd5
# lookups.dat e profili aggiornati: quelli nello zip sono troppo vecchi per i segmenti attuali
for f in lookups.dat hiking-mountain.brf; do
  curl -o profiles-current/$f https://brouter.de/brouter/profiles2/$f; done
java -Xmx1g -cp brouter-1.6.3/brouter-1.6.3-all.jar btools.server.RouteServer \
  segments4 profiles-current customprofiles 17777 2
```

## Spike sulla fixture Val d'Inferno

Con entrambi i motori avviati:

```bash
cd services/ingest
uv run --extra geo python ../routing/spike/run_spike.py     # → reports/phase0/routing-spike/
node ../routing/spike/render_map.mjs rado                   # mappa + screenshot (Playwright)
```

Lo script ricalcola distanza e dislivello con lo stesso metodo per entrambi i motori (DEM SRTM
1", passo 15 m, media mobile 75 m, isteresi 10 m) e li confronta con i valori dichiarati dalla
locandina. Risultati commentati in `reports/phase0/routing-spike/README.md`.
