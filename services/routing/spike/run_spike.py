"""Spike di routing (Fase 0): GraphHopper vs BRouter sulla fixture golden Val d'Inferno.

Confronta i due motori sugli stessi waypoint e con lo stesso metro di misura:

- distanza planimetrica ricalcolata sulla geometria restituita;
- dislivello ricalcolato su un DEM comune (SRTM 1") con ricampionamento e soglia di isteresi,
  oltre ai valori "nativi" di ciascun motore;
- quota massima, chiusura dell'anello, quota di traccia sui sentieri citati (332, 360, 326);
- tempo di risposta.

Uso (motori avviati come in services/routing/README.md):

    cd services/ingest && .venv/bin/python ../routing/spike/run_spike.py

Scrive reports/phase0/routing-spike/{results.json,tracks.geojson,table.md}.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import osmium
from shapely import STRtree
from shapely.geometry import LineString, Point, mapping
from shapely.ops import unary_union

from cordata_ingest.config import data_dir, repo_root
from cordata_ingest.geo.elevation import HgtDem, ascent_descent, moving_average
from cordata_ingest.geo.track import haversine_m, length_m, resample
from cordata_ingest.timing import din33466_hours, format_hours

GH_URL = "http://localhost:8989"
BR_URL = "http://localhost:17777"
HERE = Path(__file__).parent
OUT = repo_root() / "reports" / "phase0" / "routing-spike"
AREA = (11.49, 46.11, 11.61, 46.19)  # bbox attorno alla fixture
LAT0 = 46.15
MX = 111_320 * math.cos(math.radians(LAT0))  # metri per grado di longitudine
MY = 110_950  # metri per grado di latitudine
SNAP_M = 12.0  # distanza massima traccia–way per attribuire un tratto a una way OSM
SAC_ORDER = [
    "hiking",
    "mountain_hiking",
    "demanding_mountain_hiking",
    "alpine_hiking",
    "demanding_alpine_hiking",
    "difficult_alpine_hiking",
]


def to_xy(lon: float, lat: float) -> tuple[float, float]:
    return ((lon - 11.55) * MX, (lat - LAT0) * MY)


def to_lonlat(x: float, y: float) -> tuple[float, float]:
    return (x / MX + 11.55, y / MY + LAT0)


# ----------------------------------------------------------------- dati OSM locali


def load_osm_ways(pbf: Path) -> dict[str, Any]:
    """Way percorribili nell'area + relazioni escursionistiche a cui appartengono (con cache)."""
    cache = data_dir() / "routing" / "spike" / "ways.json"
    if cache.exists() and cache.stat().st_mtime > pbf.stat().st_mtime:
        return json.loads(cache.read_text(encoding="utf-8"))

    way_rels: dict[int, list[int]] = {}
    relations: dict[int, dict[str, str]] = {}
    for obj in osmium.FileProcessor(str(pbf), osmium.osm.RELATION):
        tags = dict(obj.tags)
        if tags.get("type") == "route" and tags.get("route") in ("hiking", "foot"):
            relations[obj.id] = {
                k: tags[k] for k in ("ref", "name", "cai_scale", "network") if k in tags
            }
            for member in obj.members:
                if member.type == "w":
                    way_rels.setdefault(member.ref, []).append(obj.id)

    w, s, e, n = AREA
    ways: dict[str, Any] = {}
    for obj in osmium.FileProcessor(str(pbf)).with_locations():
        if not obj.is_way() or "highway" not in obj.tags:
            continue
        pts = [(nd.lon, nd.lat) for nd in obj.nodes if nd.location.valid()]
        if len(pts) < 2 or not any(w <= x <= e and s <= y <= n for x, y in pts):
            continue
        tags = dict(obj.tags)
        ways[str(obj.id)] = {
            "coords": pts,
            "tags": {
                k: tags[k]
                for k in ("highway", "name", "sac_scale", "trail_visibility", "tracktype", "surface")
                if k in tags
            },
            "relations": way_rels.get(obj.id, []),
        }
    used = {r for way in ways.values() for r in way["relations"]}
    data = {"ways": ways, "relations": {str(r): relations[r] for r in sorted(used)}}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


class WayIndex:
    """Indice spaziale delle way OSM dell'area, in coordinate metriche locali."""

    def __init__(self, osm: dict[str, Any]):
        self.osm = osm
        self.ids = list(osm["ways"])
        self.lines = [LineString([to_xy(*p) for p in osm["ways"][i]["coords"]]) for i in self.ids]
        self.tree = STRtree(self.lines)

    def nearest_way(self, lon: float, lat: float) -> tuple[str | None, float]:
        point = Point(to_xy(lon, lat))
        idx = self.tree.nearest(point)
        dist = self.lines[idx].distance(point)
        return (self.ids[idx], dist) if dist <= SNAP_M else (None, dist)

    def cited_buffer_geojson(self, cited: dict[str, int], buffer_m: float = 30.0) -> dict[str, Any]:
        """Poligono (buffer) attorno alle way delle relazioni citate: area GraphHopper."""
        wanted = set(cited.values())
        lines = [
            line
            for wid, line in zip(self.ids, self.lines, strict=True)
            if wanted & set(self.osm["ways"][wid]["relations"])
        ]
        merged = unary_union([ln.buffer(buffer_m, quad_segs=2) for ln in lines]).simplify(5)
        polygons = list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged]
        features = []
        for i, poly in enumerate(polygons):
            ring = [list(to_lonlat(x, y)) for x, y in poly.exterior.coords]
            features.append(
                {
                    "type": "Feature",
                    "id": f"citati{i}",
                    "properties": {},
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                }
            )
        return {"type": "FeatureCollection", "features": features}


# ------------------------------------------------------------------------ motori


def route_graphhopper(
    points: list[tuple[float, float]], custom_model: dict | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "profile": "hike",
        "points": [list(p) for p in points],
        "elevation": True,
        "points_encoded": False,
        "instructions": False,
        "details": ["osm_way_id", "hike_rating", "foot_network"],
    }
    if custom_model:
        body["custom_model"] = custom_model
        body["ch.disable"] = True
    start = time.perf_counter()
    resp = httpx.post(f"{GH_URL}/route", json=body, timeout=120)
    elapsed = (time.perf_counter() - start) * 1000
    data = resp.json()
    if resp.status_code != 200 or "paths" not in data:
        return {"ok": False, "error": data.get("message", resp.text[:300]), "ms": elapsed}
    path = data["paths"][0]
    return {
        "ok": True,
        "ms": elapsed,
        "coords": path["points"]["coordinates"],
        "native": {
            "distance_m": path["distance"],
            "ascent_m": path["ascend"],
            "descent_m": path["descend"],
            "time_h": path["time"] / 3_600_000,
        },
        "way_ids": [
            (a, b, str(wid)) for a, b, wid in path.get("details", {}).get("osm_way_id", [])
        ],
        "snapped": path["snapped_waypoints"]["coordinates"],
    }


def route_brouter(points: list[tuple[float, float]], profile: str = "hiking-mountain") -> dict:
    lonlats = "|".join(f"{lon},{lat}" for lon, lat in points)
    start = time.perf_counter()
    resp = httpx.get(
        f"{BR_URL}/brouter",
        params={"lonlats": lonlats, "profile": profile, "alternativeidx": 0, "format": "geojson"},
        timeout=120,
    )
    elapsed = (time.perf_counter() - start) * 1000
    if resp.status_code != 200 or not resp.text.lstrip().startswith("{"):
        return {"ok": False, "error": resp.text.strip()[:300], "ms": elapsed}
    feature = resp.json()["features"][0]
    props = feature["properties"]
    return {
        "ok": True,
        "ms": elapsed,
        "coords": feature["geometry"]["coordinates"],
        "native": {
            "distance_m": float(props["track-length"]),
            "ascent_m": float(props["filtered ascend"]),
            "descent_m": None,
            "time_h": float(props["total-time"]) / 3600,
        },
        "way_ids": None,
        "snapped": None,
    }


# ----------------------------------------------------------------------- metriche


def analyse(
    route: dict, index: WayIndex, dem: HgtDem, cited: dict[str, int], declared: dict, points: list
) -> dict[str, Any]:
    coords = route["coords"]
    dense = resample(coords, 15.0)
    ele = dem.sample(dense)
    smooth = moving_average(ele, 5)  # finestra di 75 m
    dist_km = length_m(coords) / 1000

    cited_ids = {rid: ref for ref, rid in cited.items()}
    on_cited = on_any = off_network = 0
    highway: dict[str, int] = {}
    refs_seq: list[str] = []
    max_sac = -1
    for lon, lat in dense:
        wid, _ = index.nearest_way(lon, lat)
        if wid is None:
            off_network += 1
            continue
        way = index.osm["ways"][wid]
        rels = way["relations"]
        hw = way["tags"].get("highway", "?")
        highway[hw] = highway.get(hw, 0) + 1
        sac = way["tags"].get("sac_scale")
        if sac in SAC_ORDER:
            max_sac = max(max_sac, SAC_ORDER.index(sac))
        if rels:
            on_any += 1
        hit = sorted(cited_ids[r] for r in rels if r in cited_ids)
        if hit:
            on_cited += 1
        label = "+".join(hit) if hit else ("altro sentiero" if rels else "fuori rete CAI")
        if not refs_seq or refs_seq[-1] != label:
            refs_seq.append(label)
    total = len(dense)

    up5, down5 = ascent_descent(smooth, 5.0)
    up10, down10 = ascent_descent(smooth, 10.0)
    raw_up, raw_down = ascent_descent(ele, 0.0)
    native_max = max((c[2] for c in coords if len(c) > 2), default=float("nan"))
    closure = haversine_m(coords[0], coords[-1])
    snap = [
        round(haversine_m(p, min(coords, key=lambda c, p=p: haversine_m(p, c))))
        for p in points
    ]
    err_km = (dist_km - declared["km"]) / declared["km"]
    err_up = (up10 - declared["up"]) / declared["up"]
    err_max = max(ele) - declared["max"]
    status = (
        "auto_ok"
        if abs(err_km) <= 0.10 and abs(err_up) <= 0.15 and abs(err_max) <= 50 and closure < 100
        else "da_rivedere"
    )
    return {
        "distance_km": round(dist_km, 2),
        "native": route["native"],
        "dem": {
            "ascent_raw_m": round(raw_up),
            "descent_raw_m": round(raw_down),
            "ascent_h5_m": round(up5),
            "descent_h5_m": round(down5),
            "ascent_h10_m": round(up10),
            "descent_h10_m": round(down10),
            "max_ele_m": round(max(ele)),
            "min_ele_m": round(min(ele)),
        },
        "native_max_ele_m": round(native_max),
        "loop_closure_m": round(closure, 1),
        "share_on_cited_trails": round(on_cited / total, 3),
        "share_on_hiking_relations": round(on_any / total, 3),
        "share_unmatched": round(off_network / total, 3),
        "highway_share": {k: round(v / total, 3) for k, v in sorted(highway.items())},
        "max_sac_scale": SAC_ORDER[max_sac] if max_sac >= 0 else None,
        "trail_sequence": refs_seq,
        "max_waypoint_offset_m": max(snap),
        "waypoint_offsets_m": snap,
        "din33466": format_hours(din33466_hours(dist_km, up10, down10)),
        "errors": {
            "distance_pct": round(err_km * 100, 1),
            "ascent_pct": round(err_up * 100, 1),
            "max_ele_m": round(err_max),
        },
        "status": status,
        "ms": round(route["ms"]),
    }


def brouter_custom_profile(name: str, replacements: dict[str, str]) -> str:
    """Crea una variante del profilo hiking-mountain cambiando i parametri `assign`."""
    base = data_dir() / "routing" / "brouter" / "profiles-current" / "hiking-mountain.brf"
    lines = []
    for line in base.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "assign" and parts[1] in replacements:
            line = f"assign   {parts[1]}   {replacements[parts[1]]}"
        lines.append(line)
    (base.parent / f"{name}.brf").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return name


def main() -> int:
    spec = json.loads((HERE / "val_inferno_waypoints.json").read_text(encoding="utf-8"))
    fixture = json.loads(
        (repo_root() / "fixtures" / "golden" / "val-d-inferno.json").read_text(encoding="utf-8")
    )
    declared = {
        "km": fixture["distanza_km"],
        "up": fixture["dislivello_salita_m"],
        "max": fixture["quota_max_m"],
    }
    cited: dict[str, int] = spec["cited_relations"]
    by_key = {w["key"]: w for w in spec["waypoints"]}

    pbf = max((data_dir() / "osm").glob("*.osm.pbf"), key=lambda p: p.stat().st_size)
    index = WayIndex(load_osm_ways(pbf))
    dem = HgtDem(data_dir() / "routing" / "graphhopper" / "elevation-cache")
    areas = index.cited_buffer_geojson(cited)
    outside = " && ".join(f"!in_{f['id']}" for f in areas["features"])
    prefer_cited = {"priority": [{"if": outside, "multiply_by": "0.2"}], "areas": areas}
    max_e = {"priority": [{"if": "hike_rating >= 3", "multiply_by": "0"}]}
    br_max_e = brouter_custom_profile("hiking-mountain-maxE", {"SAC_scale_limit": "2"})

    runs: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []

    def record(engine: str, scenario: str, variant: str, route: dict, points: list) -> None:
        entry: dict[str, Any] = {"engine": engine, "scenario": scenario, "variant": variant}
        if route["ok"]:
            entry.update(analyse(route, index, dem, cited, declared, points))
            features.append(
                {
                    "type": "Feature",
                    "properties": {k: entry[k] for k in ("engine", "scenario", "variant")},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[round(c[0], 6), round(c[1], 6)] for c in route["coords"]],
                    },
                }
            )
        else:
            entry.update({"status": "fallita", "error": route["error"], "ms": round(route["ms"])})
        runs.append(entry)
        print(engine, scenario, variant, entry.get("status"), entry.get("distance_km"))

    for scenario, keys in spec["scenarios"].items():
        pts = [(by_key[k]["lon"], by_key[k]["lat"]) for k in keys]
        for _ in range(2):  # la prima chiamata scalda le cache: si registra la seconda
            gh = route_graphhopper(pts)
            br = route_brouter(pts)
        record("graphhopper", scenario, "profilo hike", gh, pts)
        record("brouter", scenario, "hiking-mountain", br, pts)
        if scenario != "completo":
            record(
                "graphhopper",
                scenario,
                "hike + preferenza sentieri citati",
                route_graphhopper(pts, prefer_cited),
                pts,
            )
        if scenario == "rado":
            record(
                "graphhopper", scenario, "hike, difficoltà max E", route_graphhopper(pts, max_e), pts
            )
            record("brouter", scenario, "hiking-mountain, max T2", route_brouter(pts, br_max_e), pts)

    # geometrie di contesto per la mappa: sentieri citati e waypoint
    for ref, rid in cited.items():
        for wid, way in index.osm["ways"].items():
            if rid in way["relations"]:
                features.append(
                    {
                        "type": "Feature",
                        "properties": {"kind": "cited_trail", "ref": ref, "way": wid},
                        "geometry": mapping(LineString(way["coords"])),
                    }
                )
    for wp in spec["waypoints"][:-1]:
        features.append(
            {
                "type": "Feature",
                "properties": {"kind": "waypoint", "nome": wp["nome"], "key": wp["key"]},
                "geometry": {"type": "Point", "coordinates": [wp["lon"], wp["lat"]]},
            }
        )

    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "declared": declared | {"duration": fixture["durata_dichiarata"]},
        "osm_extract": pbf.name,
        "dem": "SRTM 1 arcsec (tile skadi, AWS Open Data), bilineare, passo 15 m, media mobile 75 m",
        "runs": runs,
    }
    (OUT / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (OUT / "tracks.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    head = (
        "| Motore | Scenario | Variante | km | Δ km | D+ nativo | D+ DEM (isteresi 10 m) | Δ D+ | "
        "Quota max DEM | Sui sentieri citati | Max sac_scale | DIN | Stato | ms |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for r in runs:
        if r["status"] == "fallita":
            rows.append(
                f"| {r['engine']} | {r['scenario']} | {r['variant']} | – | – | – | – | – | – | – "
                f"| – | – | fallita: {r['error'][:80]} | {r['ms']} |"
            )
            continue
        rows.append(
            f"| {r['engine']} | {r['scenario']} | {r['variant']} | {r['distance_km']} "
            f"| {r['errors']['distance_pct']:+}% | {round(r['native']['ascent_m'])} "
            f"| {r['dem']['ascent_h10_m']} | {r['errors']['ascent_pct']:+}% "
            f"| {r['dem']['max_ele_m']} | {round(r['share_on_cited_trails'] * 100)}% "
            f"| {r['max_sac_scale']} | {r['din33466']} | {r['status']} | {r['ms']} |"
        )
    (OUT / "table.md").write_text(head + "\n".join(rows) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
