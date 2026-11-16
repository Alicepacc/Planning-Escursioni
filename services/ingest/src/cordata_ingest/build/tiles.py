"""Tile vettoriali dei sentieri e dei POI dell'area pilota (PMTiles via tippecanoe).

Due layer:
- `sentieri`: un elemento per way, con i numeri di tutti i sentieri che la percorrono;
- `poi`: rifugi, bivacchi, cime, selle, laghi, acqua, parcheggi, punti panoramici, paline.
Lo zoom minimo di ogni elemento dipende dalla sua importanza (rete, tipo di POI).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import psycopg

from ..config import areas
from ..difficulty import RANK_CAI, cai_from_sac, cai_rank, osmc_color

MAX_BYTES = 25 * 1024 * 1024  # limite per file di Cloudflare Pages (ADR 0005)

POI_MINZOOM = {
    "rifugio": 10,
    "bivacco": 11,
    "cima": 11,
    "sella": 12,
    "lago": 12,
    "localita": 12,
    "acqua_potabile": 13,
    "sorgente": 13,
    "panorama": 13,
    "cascata": 13,
    "riparo": 13,
    "parcheggio": 14,
    "palina": 14,
}

TRAIL_SQL = """
SELECT way_id, highway, sac_scale, trail_visibility, refs, relation_ids, osm2cai_ids,
       cai_scales, network_rank, sda, osmc_symbol, ST_AsGeoJSON(geom, 6)
FROM trail_ways
WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
"""

POI_SQL = """
SELECT osm_type, osm_id, kind, COALESCE(name_it, name), name_de, ele, ST_AsGeoJSON(geom, 6)
FROM osm_pois
WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
  AND (kind NOT IN ('parcheggio', 'palina', 'localita') OR name IS NOT NULL)
"""


def trail_features(conn: psycopg.Connection, bbox) -> list[dict]:
    out = []
    for (
        way_id,
        highway,
        sac,
        vis,
        refs,
        rels,
        cai_ids,
        scales,
        net_rank,
        sda,
        osmc,
        geom,
    ) in conn.execute(TRAIL_SQL, bbox):
        scale_rank = max((cai_rank(s) for s in scales or []), default=0)
        derived = False
        if scale_rank == 0:
            scale_rank = cai_rank(cai_from_sac(sac, highway))
            derived = scale_rank > 0
        props = {
            "refs": refs or "",
            "scale": RANK_CAI.get(scale_rank, ""),
            "scale_rank": scale_rank,
            "scale_derived": derived,  # True: stimata da sac_scale, non dichiarata
            "sac": sac or "",
            "vis": vis or "",
            "hw": highway,
            "net": int(net_rank),
            "cai": ",".join(str(i) for i in sorted(cai_ids or [])),
            "rel": ",".join(str(i) for i in sorted(rels or [])),
            "sda": int(sda),
            "color": osmc_color(osmc) or "red",
        }
        out.append(
            {
                "type": "Feature",
                "id": way_id,
                "properties": props,
                "geometry": json.loads(geom),
                "tippecanoe": {"layer": "sentieri"},
            }
        )
    return out


def poi_features(conn: psycopg.Connection, bbox) -> list[dict]:
    out = []
    for osm_type, osm_id, kind, name, name_de, ele, geom in conn.execute(POI_SQL, bbox):
        props = {"kind": kind, "name": name or "", "osm": f"{osm_type}{osm_id}"}
        if name_de and name_de != name:
            props["name_de"] = name_de
        if ele is not None:
            props["ele"] = round(ele)
        out.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": json.loads(geom),
                "tippecanoe": {"layer": "poi"},
            }
        )
    return out


def zoom_filter() -> dict:
    """Filtro di tippecanoe (`-j`) che decide da quale zoom compare ogni elemento.

    Non si usa il `minzoom` per singolo elemento: con tippecanoe 2.49 faceva sparire quasi tutti
    gli elementi anche agli zoom superiori (verificato: 1 tratto su 7 nel tile della fixture).
    Reti: internazionali e nazionali da z8, regionali da z9, locali da z11.
    """
    by_zoom: dict[int, list[str]] = {}
    for kind, zoom in POI_MINZOOM.items():
        by_zoom.setdefault(zoom, []).append(kind)
    poi_rules: list = [[">=", "$zoom", 14]]
    for zoom, kinds in sorted(by_zoom.items()):
        if zoom < 14:
            poi_rules.append(["all", ["in", "kind", *sorted(kinds)], [">=", "$zoom", zoom]])
    return {
        "sentieri": [
            "any",
            [">=", "$zoom", 11],
            ["<=", "net", 2],
            ["all", ["==", "net", 3], [">=", "$zoom", 9]],
        ],
        "poi": ["any", *poi_rules],
    }


def build(conn: psycopg.Connection, out_file: Path, work_dir: Path) -> dict:
    bbox = areas()["pilot"].bbox
    work_dir.mkdir(parents=True, exist_ok=True)
    seq = work_dir / "pilota.geojsonseq"
    trails = trail_features(conn, bbox)
    pois = poi_features(conn, bbox)
    with seq.open("w", encoding="utf-8") as fh:
        for feature in trails + pois:
            fh.write(json.dumps(feature, ensure_ascii=False) + "\n")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "tippecanoe",
        "-o",
        str(out_file),
        "--force",
        "--minimum-zoom=8",
        "--maximum-zoom=14",
        "--name=Cordata – sentieri e POI dell'area pilota",
        "--attribution=© OpenStreetMap contributors (ODbL) · © CAI INFOMONT (ODbL)",
        "--read-parallel",
        "--simplification=4",
        "--drop-densest-as-needed",
        "--maximum-tile-bytes=1000000",
        "-j",
        json.dumps(zoom_filter()),
        "--quiet",
        str(seq),
    ]
    subprocess.run(cmd, check=True)
    size = out_file.stat().st_size
    if size > MAX_BYTES:
        raise RuntimeError(f"{out_file} pesa {size / 1e6:.1f} MB: oltre il limite di 25 MiB")
    return {"trail_ways": len(trails), "pois": len(pois), "bytes": size}
