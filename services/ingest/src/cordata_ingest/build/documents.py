"""Documenti JSON per le schede della PWA: sentieri OSM2CAI e itinerari (SPEC §5.2, §8).

Ogni documento contiene geometria semplificata, profilo altimetrico, valori ufficiali (quando
esistono) e valori calcolati, con la fonte di ciascuno. Il formato è descritto in
`apps/web/src/lib/data/types.ts`: i due file vanno tenuti allineati.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import psycopg
from shapely.geometry import LineString, shape

from ..config import areas
from ..difficulty import normalize_cai, osmc_color
from ..geo.profile import Profile, ProfileParams, as_single_line, compute_profile
from ..geo.track import haversine_m
from ..osm2cai import localized
from ..osm2cai.sync import Osm2caiStore
from ..timing import din33466_hours, swiss_segment_minutes

SCHEMA_VERSION = 1
PROFILE_EVERY = 2  # un punto del profilo ogni 2 campioni (30 m con passo 15 m)
LINE_TOLERANCE_DEG = 0.00002  # ~2 m: semplificazione della linea disegnata
DEFAULT_PARAMS = ProfileParams(step_m=15, smooth_window=5, hysteresis_m=10, time_segment_m=15)


def _r(value: float | None, digits: int = 0) -> float | int | None:
    if value is None:
        return None
    return round(value, digits) if digits else round(value)


def profile_payload(prof: Profile) -> dict[str, Any]:
    """Profilo compatto: [distanza m, quota m, lon, lat, minuti cumulati in andata]."""
    cumulative = [0.0]
    for i in range(1, len(prof.distances_m)):
        span = prof.distances_m[i] - prof.distances_m[i - 1]
        dh = prof.elevations_m[i] - prof.elevations_m[i - 1]
        cumulative.append(cumulative[-1] + swiss_segment_minutes(span, dh))
    keep = list(range(0, len(prof.distances_m), PROFILE_EVERY))
    if keep[-1] != len(prof.distances_m) - 1:
        keep.append(len(prof.distances_m) - 1)
    return {
        "columns": ["dist_m", "ele_m", "lon", "lat", "min"],
        "points": [
            [
                round(prof.distances_m[i]),
                round(prof.elevations_m[i]),
                round(prof.coords[i][0], 5),
                round(prof.coords[i][1], 5),
                round(cumulative[i], 1),
            ]
            for i in keep
        ],
    }


def computed_payload(prof: Profile) -> dict[str, Any]:
    km = prof.length_m / 1000
    return {
        "distance_km": _r(km, 2),
        "ascent_m": _r(prof.ascent_m),
        "descent_m": _r(prof.descent_m),
        "min_ele_m": _r(prof.min_ele_m),
        "max_ele_m": _r(prof.max_ele_m),
        "cai_forward_min": _r(prof.minutes_forward),
        "cai_backward_min": _r(prof.minutes_backward),
        "din_forward_min": _r(60 * din33466_hours(km, prof.ascent_m, prof.descent_m)),
        "din_backward_min": _r(60 * din33466_hours(km, prof.descent_m, prof.ascent_m)),
        "steep_m": _r(prof.steep_m),
        "gaps": prof.gaps,
        "method": {
            "dem": "Mapterhorn z12 (Terrarium)",
            "step_m": prof.params.step_m,
            "smoothing_m": prof.params.step_m * prof.params.smooth_window,
            "hysteresis_m": prof.params.hysteresis_m,
            "time_model": "CAI / Sentieri Svizzeri",
            "time_segment_m": prof.params.time_segment_m,
        },
    }


def simplified_line(coords: Sequence[Sequence[float]]) -> list[list[float]]:
    line = LineString([(c[0], c[1]) for c in coords]).simplify(LINE_TOLERANCE_DEG)
    return [[round(x, 5), round(y, 5)] for x, y in line.coords]


def osm_relations(conn: psycopg.Connection) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        "SELECT relation_id, network, osmc_symbol, name_de, operator FROM osm_routes"
    ).fetchall()
    return {r[0]: {"network": r[1], "osmc": r[2], "name_de": r[3], "operator": r[4]} for r in rows}


def trail_document(feature: dict[str, Any], osm: dict[str, Any], dem, params=DEFAULT_PARAMS) -> dict:
    p = feature["properties"]
    coords, gaps = as_single_line(shape(feature["geometry"]))
    prof = compute_profile(coords, dem, params, gaps=gaps)
    official = {
        "distance_km": p.get("distance") or None,
        "ascent_m": p.get("ascent") or None,
        "descent_m": p.get("descent") or None,
        "duration_forward_min": p.get("duration_forward") or None,
        "duration_backward_min": p.get("duration_backward") or None,
    }
    xs, ys = [c[0] for c in coords], [c[1] for c in coords]
    relation_id = p.get("relation_id")
    return {
        "schema": SCHEMA_VERSION,
        "kind": "sentiero",
        "id": str(p["id"]),
        "ref": localized(p.get("ref")) or "",
        "name": localized(p.get("name")) or "",
        "name_de": osm.get("name_de"),
        "from": localized(p.get("from")) or "",
        "to": localized(p.get("to")) or "",
        "roundtrip": bool(p.get("roundtrip")),
        "difficulty": {"cai": normalize_cai(p.get("cai_scale")), "raw": p.get("cai_scale")},
        "network": osm.get("network") or p.get("network"),
        "operator": osm.get("operator"),
        "color": osmc_color(osm.get("osmc")) or "red",
        "osmc_symbol": osm.get("osmc"),
        "sda": p.get("sda"),
        "validation_date": p.get("validation_date") or None,
        "issues": {
            "status": localized(p.get("issues_status")) or "sconosciuto",
            "description": localized(p.get("issues_description")) or "",
            "updated": localized(p.get("issues_last_update")) or "",
        },
        "values_source": "manuale" if p.get("manual_data") else "DEM OSM2CAI" if p.get("dem_data") else None,
        "official": official,
        "computed": computed_payload(prof),
        "bbox": [round(min(xs), 5), round(min(ys), 5), round(max(xs), 5), round(max(ys), 5)],
        "line": simplified_line(coords),
        "profile": profile_payload(prof),
        "links": {
            "osm2cai": p.get("public_page"),
            "osm": f"https://www.openstreetmap.org/relation/{relation_id}" if relation_id else None,
        },
        "attribution": [
            "© Club Alpino Italiano – INFOMONT (ODbL)",
            "© OpenStreetMap contributors (ODbL)",
            "Quote: Mapterhorn",
        ],
        "generated_at": time.strftime("%Y-%m-%d"),
    }


def index_entry(doc: dict[str, Any]) -> dict[str, Any]:
    off, comp = doc["official"], doc["computed"]
    return {
        "id": doc["id"],
        "ref": doc["ref"],
        "name": doc["name"],
        "from": doc["from"],
        "to": doc["to"],
        "cai": doc["difficulty"]["cai"],
        "km": off["distance_km"] or comp["distance_km"],
        "up": off["ascent_m"] or comp["ascent_m"],
        "min": off["duration_forward_min"] or comp["cai_forward_min"],
        "sda": doc["sda"],
        "bbox": doc["bbox"],
        "issues": doc["issues"]["status"],
    }


def build_trails(store: Osm2caiStore, conn: psycopg.Connection, dem, out_dir: Path) -> dict:
    w, s, e, n = areas()["pilot"].bbox
    osm = osm_relations(conn)
    out_dir.mkdir(parents=True, exist_ok=True)
    index, skipped = [], 0
    for feature in store.features():
        geom = feature.get("geometry")
        if not geom:
            skipped += 1
            continue
        minx, miny, maxx, maxy = shape(geom).bounds
        if maxx < w or minx > e or maxy < s or miny > n:
            continue
        rel = feature["properties"].get("relation_id")
        doc = trail_document(feature, osm.get(int(rel), {}) if rel else {}, dem)
        (out_dir / f"{doc['id']}.json").write_text(
            json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        index.append(index_entry(doc))
    index.sort(key=lambda x: (x["ref"] or "~", x["id"]))
    (out_dir / "index.json").write_text(
        json.dumps({"schema": SCHEMA_VERSION, "trails": index}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return {"trails": len(index), "skipped_without_geometry": skipped}


# ----------------------------------------------------------------------------- itinerari

TRAILS_ALONG_SQL = """
WITH route AS (SELECT ST_SetSRID(ST_GeomFromText(%s), 4326) AS g),
hits AS (
    SELECT t.relation_id, t.osm2cai_id, t.ref, t.name, t.cai_scale, t.network,
           ST_Length(ST_Intersection(ST_Buffer(route.g::geography, 8)::geometry, tw.geom)::geography) AS len,
           ST_LineLocatePoint(route.g, ST_ClosestPoint(tw.geom, route.g)) AS pos
    FROM route
    JOIN trail_ways tw ON ST_DWithin(tw.geom::geography, route.g::geography, 8)
    JOIN trails t ON t.relation_id = ANY (tw.relation_ids)
)
SELECT relation_id, osm2cai_id, ref, name, cai_scale, network, sum(len) AS len, min(pos) AS pos
FROM hits GROUP BY relation_id, osm2cai_id, ref, name, cai_scale, network
HAVING sum(len) > 200
ORDER BY min(pos)
"""


def trails_along(conn: psycopg.Connection, coords: Sequence[Sequence[float]]) -> list[dict]:
    wkt = "LINESTRING(" + ",".join(f"{c[0]} {c[1]}" for c in coords) + ")"
    out = []
    for rel, cai_id, ref, name, scale, network, length, _pos in conn.execute(TRAILS_ALONG_SQL, (wkt,)):
        out.append(
            {
                "relation_id": rel,
                "osm2cai_id": str(cai_id) if cai_id else None,
                "ref": ref or "",
                "name": name or "",
                "cai": normalize_cai(scale),
                "network": network,
                "km_on_route": round(length / 1000, 1),
            }
        )
    return out


def stages(prof: Profile, waypoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Proietta i punti chiave sul profilo, in ordine, e calcola distanza e tempo cumulati."""
    cumulative = [0.0]
    for i in range(1, len(prof.distances_m)):
        span = prof.distances_m[i] - prof.distances_m[i - 1]
        dh = prof.elevations_m[i] - prof.elevations_m[i - 1]
        cumulative.append(cumulative[-1] + swiss_segment_minutes(span, dh))
    out, start = [], 0
    for k, wp in enumerate(waypoints):
        last = k == len(waypoints) - 1
        candidates = range(len(prof.coords) - 1, start - 1, -1) if last else range(start, len(prof.coords))
        best = min(candidates, key=lambda i: haversine_m(prof.coords[i], (wp["lon"], wp["lat"])))
        start = best
        out.append(
            {
                "name": wp["nome"],
                "declared_ele_m": wp.get("quota_dichiarata"),
                "ele_m": round(prof.elevations_m[best]),
                "dist_km": round(prof.distances_m[best] / 1000, 2),
                "cai_min": round(cumulative[best]),
                "offset_m": round(haversine_m(prof.coords[best], (wp["lon"], wp["lat"]))),
                "osm": wp.get("osm"),
            }
        )
    return out


def fixture_itinerary(
    fixture: dict[str, Any], waypoints: dict[str, Any], coords, conn, dem, engine_note: str
) -> dict:
    prof = compute_profile(coords, dem, DEFAULT_PARAMS)
    by_key = {w["key"]: w for w in waypoints["waypoints"]}
    ordered = [by_key[k] for k in waypoints["scenarios"]["completo"]]
    xs, ys = [c[0] for c in coords], [c[1] for c in coords]
    declared = {
        "distance_km": fixture["distanza_km"],
        "ascent_m": fixture["dislivello_salita_m"],
        "descent_m": fixture["dislivello_discesa_m"],
        "max_ele_m": fixture["quota_max_m"],
        "duration": fixture["durata_dichiarata"],
        "difficulty": fixture["difficolta_cai"],
    }
    return {
        "schema": SCHEMA_VERSION,
        "kind": "itinerario",
        "id": "val-d-inferno",
        "title": fixture["titolo"],
        "group": fixture["gruppo_montuoso"],
        "type": fixture["tipo_percorso"],
        "start": fixture["partenza"],
        "difficulty": {"cai": normalize_cai(fixture["difficolta_cai"]), "raw": fixture["difficolta_cai"]},
        "declared": declared,
        "computed": computed_payload(prof),
        "trails": trails_along(conn, coords),
        "networks": fixture["reti_citate"],
        "off_trail": fixture["tratti_fuori_sentiero"],
        "stages": stages(prof, ordered),
        "equipment": fixture["attrezzatura"],
        "notes": [n for n in fixture["note"] if "riservata" not in n],
        "map_reference": fixture["cartografia"],
        "activity": {
            "date": fixture["data"],
            "organizers": fixture["organizzatori"],
            "signup_note": "Iscrizione sul sito della sezione: l'app non gestisce le iscrizioni CAI.",
            "source_url": None,
        },
        "bbox": [round(min(xs), 5), round(min(ys), 5), round(max(xs), 5), round(max(ys), 5)],
        "line": simplified_line(coords),
        "profile": profile_payload(prof),
        "reconstruction": engine_note,
        "attribution": [
            "Attività: CAI Sezione di Merano, CAI Sezione di Mestre, Commissione Giovani CAI Alto Adige",
            "© OpenStreetMap contributors (ODbL)",
            "© Club Alpino Italiano – INFOMONT (ODbL)",
            "Quote: Mapterhorn",
        ],
        "generated_at": time.strftime("%Y-%m-%d"),
    }
