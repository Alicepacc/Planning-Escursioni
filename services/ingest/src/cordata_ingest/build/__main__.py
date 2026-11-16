"""`python -m cordata_ingest.build <passo>`: dai dati sincronizzati ai file della PWA.

Passi (in ordine):
  load-osm2cai   carica data/osm2cai in PostGIS (tabella osm2cai_routes)
  derive         tabelle derivate trails e trail_ways (sql/derive.sql)
  tiles          PMTiles di sentieri e POI → apps/web/static/tiles/pilota.pmtiles
  trails         schede JSON dei sentieri → apps/web/static/data/sentieri/
  fixture        itinerario della fixture → apps/web/static/data/itinerari/val-d-inferno.json
  all            tutti i passi
L'import OSM (osm2pgsql) è descritto in services/ingest/README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from ..config import data_dir, repo_root
from ..db import connect, run_sql_file
from ..geo.elevation import TerrariumDem
from ..http import PoliteClient
from ..osm2cai.sync import Osm2caiStore
from . import documents, osm2cai_load, tiles

STEPS = ("load-osm2cai", "derive", "tiles", "trails", "fixture")
WEB_STATIC = repo_root() / "apps" / "web" / "static"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build dei dati statici della PWA")
    parser.add_argument("step", choices=(*STEPS, "all"))
    args = parser.parse_args(argv)
    steps = STEPS if args.step == "all" else (args.step,)
    conn = connect()
    client = PoliteClient(host_intervals={"tiles.mapterhorn.com": 0.25})
    dem = TerrariumDem(data_dir() / "dem" / "mapterhorn", client, zoom=12)
    store = Osm2caiStore(data_dir() / "osm2cai")
    for step in steps:
        t0 = time.time()
        if step == "load-osm2cai":
            result = {"osm2cai_routes": osm2cai_load.load(conn, store)}
        elif step == "derive":
            run_sql_file(conn, repo_root() / "services" / "ingest" / "sql" / "derive.sql")
            counts = conn.execute(
                "SELECT (SELECT count(*) FROM trails),"
                " (SELECT count(*) FROM trails WHERE osm2cai_id IS NOT NULL),"
                " (SELECT count(*) FROM trail_ways)"
            ).fetchone()
            result = {"trails": counts[0], "with_osm2cai": counts[1], "trail_ways": counts[2]}
        elif step == "tiles":
            result = tiles.build(
                conn, WEB_STATIC / "tiles" / "pilota.pmtiles", data_dir() / "build"
            )
        elif step == "trails":
            result = documents.build_trails(store, conn, dem, WEB_STATIC / "data" / "sentieri")
        else:
            fixture = json.loads(
                (repo_root() / "fixtures/golden/val-d-inferno.json").read_text("utf-8")
            )
            waypoints = json.loads(
                (repo_root() / "services/routing/spike/val_inferno_waypoints.json").read_text(
                    "utf-8"
                )
            )
            tracks = json.loads(
                (repo_root() / "reports/phase0/routing-spike/tracks.geojson").read_text("utf-8")
            )["features"]
            route = next(
                f
                for f in tracks
                if f["properties"].get("engine") == "graphhopper"
                and f["properties"].get("scenario") == "rado"
                and f["properties"].get("variant") == "profilo hike"
            )
            doc = documents.fixture_itinerary(
                fixture,
                waypoints,
                route["geometry"]["coordinates"],
                conn,
                dem,
                "Traccia ricostruita con GraphHopper (profilo hike) sui 5 punti chiave principali "
                "della locandina (spike della Fase 0); non ancora verificata sul terreno.",
            )
            out = WEB_STATIC / "data" / "itinerari" / "val-d-inferno.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), "utf-8")
            result = {"stages": len(doc["stages"]), "trails": [t["ref"] for t in doc["trails"]]}
        elapsed = time.time() - t0
        print(f"{step}: {result} ({elapsed:.0f} s; tile DEM scaricati {dem.tiles_downloaded})")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
