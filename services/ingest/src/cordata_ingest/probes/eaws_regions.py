"""Micro-regioni EAWS: poligoni per intersecare la traccia con il bollettino valanghe."""

from __future__ import annotations

import json

from shapely.geometry import Point, shape

from ..config import data_dir
from .base import ProbeContext, ProbeResult

PROBE_ID = "eaws_regions"
BASE = "https://regions.avalanches.org/micro-regions"
REGIONS = ("IT-32-TN", "IT-32-BZ", "AT-07")
POINTS = {"Cima Nassere": (11.550534, 46.150821), "centro bbox Lagorai": (11.51, 46.105)}


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="EAWS regions – micro-regioni del bollettino valanghe",
        format="GeoJSON (MultiPolygon, WGS84), un file per regione",
        license="CC0 1.0 Universal (file LICENSE del repository eaws/eaws-regions)",
        license_url="https://gitlab.com/eaws/eaws-regions/-/raw/master/LICENSE",
        limits="File statici (cache-control max-age=600); scaricare una volta e versionare.",
        update_frequency="Rara (revisioni delle micro-regioni prima della stagione)",
    )
    r.notes.append(
        "Licenza letta a mano il 13/11/2026 nel file LICENSE del repository (CC0 1.0 Universal). "
        "Lo script non la riscarica: il robots.txt di gitlab.com vieta quel percorso ai client "
        "automatici."
    )
    current: dict[str, object] = {}
    for code in REGIONS:
        res = ctx.try_get(
            r, f"poligoni {code}", f"{BASE}/{code}_micro-regions.geojson.json", ttl=30 * 86400
        )
        if not res:
            continue
        features = res.json()["features"]
        active = [f for f in features if not f["properties"].get("end_date")]
        for feat in active:
            current[feat["properties"]["id"]] = shape(feat["geometry"])
        r.notes.append(
            f"{code}: {len(features)} poligoni, {len(active)} validi oggi "
            f"(gli altri hanno end_date: micro-regioni storiche)"
        )
        r.samples.append(ctx.save_sample(PROBE_ID, f"{code}_micro-regions.geojson", res.json()))
        r.examples.append(res.url)

    bulletin_path = data_dir() / "samples" / "avalanche_report" / "2026-02-10_EUREGIO_it.json"
    in_bulletin: set[str] = set()
    if bulletin_path.exists():
        bulletins = json.loads(bulletin_path.read_text(encoding="utf-8"))["bulletins"]
        in_bulletin = {reg["regionID"] for b in bulletins for reg in b["regions"]}
    for name, (lon, lat) in POINTS.items():
        hits = [rid for rid, geom in current.items() if geom.contains(Point(lon, lat))]
        r.check(f"{name} cade in una sola micro-regione", len(hits) == 1, str(hits))
        if hits and in_bulletin:
            r.check(
                f"{hits[0]} compare nel bollettino del 10/02/2026",
                hits[0] in in_bulletin,
                "eseguire prima la verifica avalanche_report" if not in_bulletin else "",
            )
    out = ctx.try_get(
        r, "avalanches.org raggiungibile (rimando fuori Euregio)", "https://www.avalanches.org/"
    )
    if out:
        r.notes.append("Fuori Euregio l'app rimanda a https://www.avalanches.org/")
    return r.finish()
