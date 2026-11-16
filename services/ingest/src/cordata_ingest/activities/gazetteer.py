"""Gazetteer locale per la geocodifica dei punti chiave (SPEC §7.4, passi 1-2).

Le locandine citano località, masi, castelli, chiese, malghe, stazioni di funivia, fermate del
bus: molto più dei POI escursionistici di `osm_pois`. Questo modulo carica in PostGIS tutti gli
elementi OSM con nome di quelle categorie (estratti con osmium, vedi `build_extract`) e offre
una ricerca fuzzy italiano/tedesco (pg_trgm su nomi normalizzati), con vincolo di distanza e di
quota. Nessun servizio esterno: niente Nominatim.

    osmium tags-filter … | osmium export -f geojsonseq   (build_extract)
    python -m cordata_ingest.activities gazetteer          (load)
"""

from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from ..config import data_dir

# categorie estratte (osmium tags-filter); il primo filtro sceglie gli oggetti, il secondo
# tiene solo quelli con un nome
TAG_FILTERS = [
    "nwr/place",
    "nwr/historic",
    "nwr/tourism",
    "nwr/natural=peak,saddle,water,spring,glacier,cave_entrance,valley,ridge,arete,cliff,rock,"
    "stone,bay,wetland,shingle,scree",
    "nwr/water",
    "nwr/amenity=restaurant,place_of_worship,parking,shelter,bus_station,cafe,pub,biergarten,"
    "townhall,school",
    "nwr/building=church,chapel,farm,hotel,cabin,hut,farm_auxiliary,house",
    "nwr/aerialway=station",
    "nwr/highway=bus_stop",
    "nwr/railway=station,halt",
    "nwr/mountain_pass",
    "nwr/waterway=waterfall,dam",
    "nwr/landuse=meadow,farmyard,forest",
    "nwr/leisure=park,nature_reserve,picnic_table",
    "nwr/boundary=protected_area",
    "nwr/man_made=bridge,tower,cross,water_works",
    "nwr/summit:cross",
]

# tipo del luogo, in ordine di priorità
KIND_RULES: list[tuple[str, str, str | None]] = [
    ("natural", "peak", "cima"),
    ("natural", "saddle", "sella"),
    ("mountain_pass", "yes", "passo"),
    ("tourism", "alpine_hut", "rifugio"),
    ("tourism", "wilderness_hut", "bivacco"),
    ("aerialway", "station", "funivia"),
    ("railway", "station", "stazione"),
    ("railway", "halt", "stazione"),
    ("highway", "bus_stop", "fermata"),
    ("amenity", "bus_station", "fermata"),
    ("amenity", "parking", "parcheggio"),
    ("historic", "castle", "castello"),
    ("amenity", "place_of_worship", "chiesa"),
    ("building", "church", "chiesa"),
    ("building", "chapel", "chiesa"),
    ("historic", "wayside_shrine", "capitello"),
    ("natural", "water", "lago"),
    ("water", "lake", "lago"),
    ("water", "pond", "lago"),
    ("natural", "spring", "sorgente"),
    ("waterway", "waterfall", "cascata"),
    ("natural", "glacier", "ghiacciaio"),
    ("tourism", "information", "palina"),
    ("tourism", "viewpoint", "panorama"),
    ("place", "city", "paese"),
    ("place", "town", "paese"),
    ("place", "village", "paese"),
    ("place", "hamlet", "frazione"),
    ("place", "isolated_dwelling", "maso"),
    ("place", "locality", "localita"),
    ("place", "farm", "maso"),
    ("building", "farm", "maso"),
    ("landuse", "farmyard", "maso"),
    ("amenity", "restaurant", "ristoro"),
    ("amenity", "cafe", "ristoro"),
    ("amenity", "pub", "ristoro"),
    ("amenity", "biergarten", "ristoro"),
    ("tourism", "hotel", "albergo"),
    ("tourism", "guest_house", "albergo"),
    ("man_made", "bridge", "ponte"),
    ("natural", "valley", "valle"),
]

NAME_KEYS = ("name", "name:it", "name:de", "name:lld", "alt_name", "loc_name", "official_name")

ABBREVIATIONS = {
    "rif": "rifugio",
    "s": "san",
    "st": "sankt",
    "m": "monte",
    "mt": "monte",
    "loc": "localita",
    "fraz": "frazione",
    "p": "passo",
    "pso": "passo",
    "c": "cima",
    "lgo": "lago",
    "malg": "malga",
}


def normalize(text: str) -> str:
    """Minuscole, senza accenti né punteggiatura, abbreviazioni sciolte (Rif. → rifugio)."""
    text = unicodedata.normalize("NFKD", text.lower().replace("ß", "ss"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [ABBREVIATIONS.get(w, w) for w in text.split()]
    return " ".join(words)


def kind_of(tags: dict[str, str]) -> str:
    for key, value, kind in KIND_RULES:
        if tags.get(key) == value:
            return kind or value
    for key in ("place", "historic", "tourism", "natural", "amenity", "building"):
        if key in tags:
            return f"{key}:{tags[key]}"
    return "altro"


def _ele(tags: dict[str, str]) -> float | None:
    m = re.match(r"^\s*(\d{2,4}(?:[.,]\d+)?)", tags.get("ele", ""))
    return float(m.group(1).replace(",", ".")) if m else None


def build_extract(pbf: Path, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or data_dir() / "osm" / "gazetteer"
    out_dir.mkdir(parents=True, exist_ok=True)
    step1, named, seq = (
        out_dir / "step1.osm.pbf",
        out_dir / "named.osm.pbf",
        out_dir / "named.geojsonseq",
    )
    subprocess.run(
        ["osmium", "tags-filter", str(pbf), *TAG_FILTERS, "-o", str(step1), "--overwrite"],
        check=True,
    )
    subprocess.run(
        [
            *["osmium", "tags-filter", str(step1), "nwr/name", "nwr/name:it", "nwr/name:de"],
            *["-o", str(named), "--overwrite"],
        ],
        check=True,
    )
    subprocess.run(
        [
            *["osmium", "export", str(named), "-f", "geojsonseq", "-o", str(seq)],
            *["--overwrite", "-a", "type,id"],
        ],
        check=True,
    )
    return seq


SCHEMA = """
DROP TABLE IF EXISTS gazetteer_names;
DROP TABLE IF EXISTS gazetteer;
CREATE TABLE gazetteer (
    gid serial PRIMARY KEY,
    osm_type char(1),
    osm_id bigint,
    kind text,
    name text,
    name_it text,
    name_de text,
    ele real,
    geom geometry(Point, 4326)
);
CREATE TABLE gazetteer_names (gid int REFERENCES gazetteer, name text, norm text);
"""

INDEXES = """
CREATE INDEX gazetteer_geom_idx ON gazetteer USING gist (geom);
CREATE INDEX gazetteer_geog_idx ON gazetteer USING gist ((geom::geography));
CREATE INDEX gazetteer_names_trgm ON gazetteer_names USING gin (norm gin_trgm_ops);
CREATE INDEX gazetteer_names_gid ON gazetteer_names (gid);
ANALYZE gazetteer; ANALYZE gazetteer_names;
"""


def _features(seq: Path):
    with seq.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip().lstrip("\x1e")
            if line:
                yield json.loads(line)


def load(conn: Any, seq: Path | None = None) -> int:
    seq = seq or data_dir() / "osm" / "gazetteer" / "named.geojsonseq"
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
        n = 0
        for f in _features(seq):
            tags = {k: v for k, v in f["properties"].items() if not k.startswith("@")}
            names = {tags[k].strip() for k in NAME_KEYS if tags.get(k, "").strip()}
            if not names:
                continue
            geom = shape(f["geometry"])
            point = geom if geom.geom_type == "Point" else geom.representative_point()
            cur.execute(
                "INSERT INTO gazetteer (osm_type, osm_id, kind, name, name_it, name_de, ele, geom)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326))"
                " RETURNING gid",
                (
                    f["properties"].get("@type", "?")[:1],
                    f["properties"].get("@id"),
                    kind_of(tags),
                    tags.get("name") or next(iter(names)),
                    tags.get("name:it"),
                    tags.get("name:de"),
                    _ele(tags),
                    point.x,
                    point.y,
                ),
            )
            gid = cur.fetchone()[0]
            variants: set[str] = set()
            for nm in names:
                variants.add(nm)
                # nomi bilingui "Rifugio X - X-Hütte" o "X / Y": anche le singole parti
                variants.update(p.strip() for p in re.split(r"\s+[-/–]\s+|/", nm) if p.strip())
            cur.executemany(
                "INSERT INTO gazetteer_names (gid, name, norm) VALUES (%s,%s,%s)",
                [(gid, v, normalize(v)) for v in variants if normalize(v)],
            )
            n += 1
        cur.execute(INDEXES)
    conn.commit()
    return n


POINT = "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography"


@dataclass
class Place:
    gid: int
    name: str
    kind: str
    lon: float
    lat: float
    ele: float | None
    score: float
    similarity: float
    distance_km: float | None
    variant: str = ""  # la forma del nome che corrisponde meglio alla ricerca
    exact: bool = False  # nome identico alla ricerca (dopo la normalizzazione)


def search(
    conn: Any,
    query: str,
    *,
    near: tuple[float, float] | None = None,
    radius_km: float = 25.0,
    ele: float | None = None,
    kinds: tuple[str, ...] | None = None,
    limit: int = 5,
    min_similarity: float = 0.45,
) -> list[Place]:
    """Candidati per un nome, ordinati per punteggio (somiglianza, distanza, quota)."""
    q = normalize(query)
    if not q:
        return []
    params: dict[str, Any] = {"q": q, "minsim": min_similarity, "limit": limit * 4}
    where = ["%(q)s <%% n.norm"]  # operatore di word_similarity: usa l'indice trigrammi
    if near:
        params.update({"lon": near[0], "lat": near[1], "r": radius_km * 1000})
        where.append(f"ST_DWithin(g.geom::geography, {POINT}, %(r)s)")
    if kinds:
        params["kinds"] = list(kinds)
        where.append("g.kind = ANY(%(kinds)s)")
    dist = f"ST_Distance(g.geom::geography, {POINT})/1000" if near else "NULL::float"
    sql = f"""
        SELECT * FROM (
            SELECT DISTINCT ON (g.gid) g.gid, g.name, g.kind, ST_X(g.geom), ST_Y(g.geom), g.ele,
                   greatest(word_similarity(%(q)s, n.norm), similarity(%(q)s, n.norm)) AS sim,
                   {dist} AS dkm, n.name AS variant, n.norm = %(q)s AS exact
            FROM gazetteer_names n JOIN gazetteer g USING (gid)
            WHERE {" AND ".join(where)}
            ORDER BY g.gid, sim DESC, exact DESC
        ) best
        ORDER BY sim DESC, exact DESC
        LIMIT %(limit)s
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('pg_trgm.word_similarity_threshold', %s, false)",
            (str(min_similarity),),
        )
        cur.execute(sql, params)
        rows = cur.fetchall()
    out = []
    for gid, name, kind, lon, lat, gele, sim, dkm, variant, exact in rows:
        score = float(sim)
        if near and dkm is not None:
            score -= 0.15 * min(float(dkm) / radius_km, 1.0)
        if ele is not None and gele is not None:
            diff = abs(float(gele) - ele)
            score += 0.15 if diff <= 30 else 0.05 if diff <= 80 else -0.1
        out.append(
            Place(
                gid,
                name,
                kind,
                lon,
                lat,
                gele,
                round(score, 3),
                round(float(sim), 3),
                None if dkm is None else round(float(dkm), 2),
                variant,
                bool(exact),
            )
        )
    out.sort(key=lambda p: -p.score)
    return out[:limit]
