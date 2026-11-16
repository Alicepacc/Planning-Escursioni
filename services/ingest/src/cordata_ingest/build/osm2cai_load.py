"""Carica i sentieri OSM2CAI sincronizzati (data/osm2cai) nella tabella `osm2cai_routes`."""

from __future__ import annotations

import json
from typing import Any

import psycopg

from ..osm2cai import localized
from ..osm2cai.sync import Osm2caiStore

DDL = """
DROP TABLE IF EXISTS osm2cai_routes;
CREATE TABLE osm2cai_routes (
    id int PRIMARY KEY,
    relation_id bigint,
    ref text,
    name text,
    sda int,
    cai_scale text,
    from_place text,
    to_place text,
    distance_km real,
    ascent_m real,
    descent_m real,
    duration_forward_min int,
    duration_backward_min int,
    ele_from real,
    ele_to real,
    ele_min real,
    ele_max real,
    issues_status text,
    issues_description text,
    issues_last_update text,
    validation_date text,
    public_page text,
    regions text[],
    updated_at text,
    props jsonb,
    geom geometry(MultiLineString, 4326)
);
"""

INSERT = """
INSERT INTO osm2cai_routes VALUES (
    %(id)s, %(relation_id)s, %(ref)s, %(name)s, %(sda)s, %(cai_scale)s, %(from)s, %(to)s,
    %(distance)s, %(ascent)s, %(descent)s, %(duration_forward)s, %(duration_backward)s,
    %(ele_from)s, %(ele_to)s, %(ele_min)s, %(ele_max)s, %(issues_status)s,
    %(issues_description)s, %(issues_last_update)s, %(validation_date)s, %(public_page)s,
    %(regions)s, %(updated_at)s, %(props)s,
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(%(geometry)s), 4326)))
)
"""

NUMERIC = ("distance", "ascent", "descent", "ele_from", "ele_to", "ele_min", "ele_max")
INTEGER = ("duration_forward", "duration_backward", "sda", "relation_id")


def _num(value: Any, cast=float) -> Any:
    if value in (None, ""):
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def row(feature: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    p = feature["properties"]
    text_keys = ("ref", "name", "cai_scale", "from", "to", "issues_status", "issues_description")
    out = {key: localized(p.get(key)) for key in text_keys}
    out |= {key: localized(p.get(key)) for key in ("issues_last_update", "validation_date")}
    out["public_page"] = localized(p.get("public_page"))
    out |= {key: _num(p.get(key)) for key in NUMERIC}
    out |= {key: _num(p.get(key), int) for key in INTEGER}
    out["id"] = int(p["id"])
    out["regions"] = state.get("regions")
    out["updated_at"] = state.get("updated_at")
    out["props"] = json.dumps(p, ensure_ascii=False)
    out["geometry"] = json.dumps(feature["geometry"])
    return out


def load(conn: psycopg.Connection, store: Osm2caiStore) -> int:
    conn.execute(DDL)
    rows = [
        row(feature, store.routes.get(str(feature["properties"]["id"]), {}))
        for feature in store.features()
        if feature.get("geometry")
    ]
    with conn.cursor() as cur:
        cur.executemany(INSERT, rows)
    conn.execute("CREATE INDEX ON osm2cai_routes (relation_id)")
    conn.execute("CREATE INDEX ON osm2cai_routes USING gist (geom)")
    return len(rows)
