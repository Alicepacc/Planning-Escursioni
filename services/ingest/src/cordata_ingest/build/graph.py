"""Grafo pedonale a tasselli per il routing nel browser (ADR 0010).

Dalla rete OSM percorribile a piedi in PostGIS (`osm_ways`):

1. **incroci**: i vertici condivisi da più vie (coordinate arrotondate a 1e-6°) e gli estremi
   delle vie sono i nodi del grafo; ogni via si divide in archi tra nodi consecutivi;
2. per ogni arco: lunghezza, **salita e discesa** dal DEM (con soglia contro il rumore),
   **difficoltà** (scala CAI del catasto se il tratto è in un sentiero ufficiale, altrimenti da
   `sac_scale`), **classe** della via, flag (segnato, traccia poco visibile, segnalazione OSM2CAI,
   scale, via ferrata) e numeri dei sentieri;
3. **tasselli** di 0,1° × 0,05°: ogni arco va nel tassello del suo punto medio, con i nodi che
   usa e la forma intermedia semplificata: per ogni punto le differenze dal precedente in 1e-5°
   (circa 1 m) e la quota, per profilo e quota massima nel browser;
4. nei tasselli anche i **luoghi** utili alle proposte (cime, laghi, rifugi, punti panoramici,
   parcheggi).

Formato di un tassello (`grafo/<ix>_<iy>.json`):
    {"n": [[id, x, y, quota], …],                      # x, y in 1e-5°
     "e": [[da, a, lung_m, salita_m, discesa_m, diff, classe, flag, rif, [dx, dy, z, …]], …],
     "r": ["332", "E325", …],                          # numeri dei sentieri (indice da `rif`)
     "p": [[tipo, x, y, quota, nome], …]}
"""

from __future__ import annotations

import itertools
import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg
from shapely import wkb
from shapely.geometry import LineString

from ..geo.track import haversine_m

TILE_DX = 0.1
TILE_DY = 0.05
SCALE = 100_000  # 1e-5°
SIMPLIFY_DEG = 0.00004  # circa 4 m
ELE_THRESHOLD_M = 3.0  # salite più piccole sono rumore del DEM

WALKABLE = (
    "path",
    "footway",
    "track",
    "steps",
    "pedestrian",
    "living_street",
    "residential",
    "unclassified",
    "service",
    "tertiary",
    "secondary",
    "primary",
    "bridleway",
    "via_ferrata",
)
# classe: 0 sentiero, 1 strada forestale o carrareccia, 2 strada minore, 3 strada principale
CLASS = {
    "path": 0,
    "footway": 0,
    "steps": 0,
    "bridleway": 0,
    "via_ferrata": 0,
    "pedestrian": 2,
    "track": 1,
    "living_street": 2,
    "residential": 2,
    "unclassified": 2,
    "service": 2,
    "tertiary": 3,
    "secondary": 3,
    "primary": 3,
}
DIFFICULTY = {"T": 0, "E": 1, "EE": 2, "EEA": 3}
SAC_TO_CAI = {
    "strolling": "T",
    "hiking": "T",
    "mountain_hiking": "E",
    "demanding_mountain_hiking": "EE",
    "alpine_hiking": "EE",
    "demanding_alpine_hiking": "EEA",
    "difficult_alpine_hiking": "EEA",
}
F_MARKED, F_LOW_VIS, F_ISSUE, F_STEPS, F_FERRATA = 1, 2, 4, 8, 16
POI_KINDS = {
    "cima": "c",
    "lago": "l",
    "rifugio": "r",
    "bivacco": "b",
    "panorama": "v",
    "parcheggio": "k",
}

WALKABLE_SQL = """
    highway = ANY(%(hw)s)
    AND coalesce(foot, '') <> 'no'
    AND NOT (coalesce(access, '') IN ('private', 'no')
             AND coalesce(foot, '') NOT IN ('yes', 'designated', 'permissive'))
"""


def tile_of(x: float, y: float) -> tuple[int, int]:
    return math.floor(x / TILE_DX), math.floor(y / TILE_DY)


def difficulty_of(highway: str, sac: str | None, cai_scales: list[str] | None) -> int:
    """Grado ufficiale del catasto se c'è (il più alto), altrimenti da OSM."""
    official = [s.upper().split(":")[0] for s in cai_scales or [] if s]
    official = [s for s in official if s in DIFFICULTY]
    if official:
        return max(DIFFICULTY[s] for s in official)
    if highway == "via_ferrata":
        return DIFFICULTY["EEA"]
    if sac:
        return DIFFICULTY[SAC_TO_CAI.get(sac.split(";")[0], "E")]
    return DIFFICULTY["E"] if highway == "path" else DIFFICULTY["T"]


def up_down(elevations: list[float]) -> tuple[float, float]:
    """Salita e discesa con isteresi: ignora le oscillazioni sotto la soglia."""
    up = down = 0.0
    ref = elevations[0]
    for e in elevations[1:]:
        if e - ref >= ELE_THRESHOLD_M:
            up += e - ref
            ref = e
        elif ref - e >= ELE_THRESHOLD_M:
            down += ref - e
            ref = e
    return up, down


def _junctions(conn: psycopg.Connection) -> set[tuple[int, int]]:
    """Vertici condivisi da almeno due vie (o due volte dalla stessa): sono incroci."""
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT round(ST_X(p.geom) * 1e6)::bigint, round(ST_Y(p.geom) * 1e6)::bigint
                FROM (SELECT (ST_DumpPoints(geom)).geom AS geom FROM osm_ways
                      WHERE {WALKABLE_SQL}) p
                GROUP BY 1, 2 HAVING count(*) > 1""",
            {"hw": list(WALKABLE)},
        )
        return {(x, y) for x, y in cur.fetchall()}


def _trail_info(conn: psycopg.Connection) -> dict[int, tuple[str, list[str], bool]]:
    """way_id → (numeri dei sentieri, gradi CAI ufficiali, segnalazione OSM2CAI)."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT tw.way_id, tw.refs, tw.cai_scales,
                      bool_or(t.issues_status ILIKE '%%non percorribile%%'
                              OR t.issues_status ILIKE '%%parzialmente%%')
               FROM trail_ways tw
               LEFT JOIN trails t ON t.osm2cai_id = ANY(tw.osm2cai_ids)
               GROUP BY tw.way_id, tw.refs, tw.cai_scales"""
        )
        return {row[0]: (row[1] or "", row[2] or [], bool(row[3])) for row in cur.fetchall()}


def build_graph(conn: psycopg.Connection, dem: Any, out_dir: Path) -> dict[str, Any]:
    t0 = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    junctions = _junctions(conn)
    trails = _trail_info(conn)
    node_ids: dict[tuple[int, int], int] = {}
    node_ele: dict[int, float] = {}
    node_xy: dict[int, tuple[float, float]] = {}
    tiles: dict[tuple[int, int], dict[str, Any]] = defaultdict(
        lambda: {"n": {}, "e": [], "r": {}, "p": []}
    )

    def node(x: float, y: float) -> int:
        key = (round(x * 1e6), round(y * 1e6))
        nid = node_ids.get(key)
        if nid is None:
            nid = len(node_ids)
            node_ids[key] = nid
            node_xy[nid] = (x, y)
            node_ele[nid] = dem.elevation(x, y)
        return nid

    edges = 0
    with conn.transaction(), conn.cursor(name="vie") as cur:
        cur.itersize = 5000
        cur.execute(
            f"""SELECT way_id, highway, sac_scale, trail_visibility, ST_AsBinary(geom)
                    FROM osm_ways WHERE {WALKABLE_SQL}""",
            {"hw": list(WALKABLE)},
        )
        for way_id, highway, sac, visibility, geom in cur:
            coords = list(wkb.loads(bytes(geom)).coords)
            if len(coords) < 2:
                continue
            refs, scales, issue = trails.get(way_id, ("", [], False))
            diff = difficulty_of(highway, sac, scales)
            cls = CLASS.get(highway, 2)
            flags = (
                (F_MARKED if refs else 0)
                | (F_LOW_VIS if visibility in ("bad", "horrible", "no") else 0)
                | (F_ISSUE if issue else 0)
                | (F_STEPS if highway == "steps" else 0)
                | (F_FERRATA if highway == "via_ferrata" else 0)
            )
            # spezza agli incroci
            start = 0
            for i in range(1, len(coords)):
                key = (round(coords[i][0] * 1e6), round(coords[i][1] * 1e6))
                if i < len(coords) - 1 and key not in junctions:
                    continue
                part = coords[start : i + 1]
                start = i
                a, b = node(*part[0]), node(*part[-1])
                if a == b and len(part) < 3:
                    continue
                line = LineString(part)
                shape = list(line.simplify(SIMPLIFY_DEG, preserve_topology=False).coords)
                length = sum(haversine_m(p, q) for p, q in itertools.pairwise(part))
                if length < 0.5:
                    continue
                inner = shape[1:-1]
                eles = [node_ele[a], *(dem.elevation(x, y) for x, y in inner), node_ele[b]]
                up, down = up_down(eles)
                mid = part[len(part) // 2]
                tile = tiles[tile_of(*mid)]
                rid = -1
                if refs:
                    rid = tile["r"].setdefault(refs, len(tile["r"]))
                ax, ay = node_xy[a]
                deltas: list[int] = []
                px, py = round(ax * SCALE), round(ay * SCALE)
                for (x, y), z in zip(inner, eles[1:-1], strict=True):
                    qx, qy = round(x * SCALE), round(y * SCALE)
                    deltas += [qx - px, qy - py, round(z)]  # differenze in 1e-5° e quota
                    px, py = qx, qy
                tile["e"].append(
                    [a, b, round(length, 1), round(up), round(down), diff, cls, flags, rid, deltas]
                )
                for nid in (a, b):
                    if nid not in tile["n"]:
                        x, y = node_xy[nid]
                        tile["n"][nid] = [
                            nid,
                            round(x * SCALE),
                            round(y * SCALE),
                            round(node_ele[nid]),
                        ]
                edges += 1

    with conn.cursor() as cur:
        cur.execute(
            """SELECT kind, ST_X(geom), ST_Y(geom), ele, coalesce(name_it, name)
               FROM osm_pois WHERE kind = ANY(%s) AND (kind <> 'parcheggio' OR name IS NOT NULL)""",
            (list(POI_KINDS),),
        )
        for kind, x, y, ele, name in cur.fetchall():
            key = tile_of(x, y)
            if key in tiles:
                tiles[key]["p"].append(
                    [
                        POI_KINDS[kind],
                        round(x * SCALE),
                        round(y * SCALE),
                        round(ele) if ele else None,
                        name or "",
                    ]
                )

    sizes = []
    for (ix, iy), tile in tiles.items():
        payload = {
            "n": list(tile["n"].values()),
            "e": tile["e"],
            "r": [r for r, _ in sorted(tile["r"].items(), key=lambda kv: kv[1])],
            "p": tile["p"],
        }
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        (out_dir / f"{ix}_{iy}.json").write_text(text, encoding="utf-8")
        sizes.append(len(text))
    index = {
        "schema": 1,
        "tile": [TILE_DX, TILE_DY],
        "scale": SCALE,
        "tiles": sorted(f"{ix}_{iy}" for ix, iy in tiles),
        "difficulty": list(DIFFICULTY),
        "flags": {
            "segnato": F_MARKED,
            "poco_visibile": F_LOW_VIS,
            "segnalazione": F_ISSUE,
            "scale": F_STEPS,
            "via_ferrata": F_FERRATA,
        },
        "attribution": "© OpenStreetMap contributors (ODbL); difficoltà: catasto CAI (OSM2CAI)",
        "generated_at": time.strftime("%Y-%m-%d"),
    }
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return {
        "nodi": len(node_ids),
        "archi": edges,
        "tasselli": len(tiles),
        "MB": round(sum(sizes) / 1e6, 1),
        "tassello_max_kB": round(max(sizes) / 1e3) if sizes else 0,
        "secondi": round(time.time() - t0),
    }
