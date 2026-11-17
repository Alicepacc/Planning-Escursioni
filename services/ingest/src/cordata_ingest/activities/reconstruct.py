"""Ricostruzione della traccia di un'attività (SPEC §7.4, "il cuore del problema").

1. Geocodifica dei punti chiave con il gazetteer locale (nomi italiano/tedesco, fuzzy), con la
   quota dichiarata verificata sul DEM e la vicinanza ai sentieri citati come indizi.
2. Sentieri citati: relazioni con quei numeri (anche SAT E/O) entro 25 km dalla partenza.
3. Routing GraphHopper tra i punti, con forte preferenza per le way dei sentieri citati
   (area "citati" nel custom model; fuori costa di più, ma resta percorribile).
4. Profilo sul DEM (stesso calcolo delle schede) e confronto con i dati dichiarati:
   `auto_ok` entro ±10% km, ±15% D+ e ±50 m di quota massima; `da_rivedere`; `fallita`.
5. Per gli anelli, controllo che inizio e fine coincidano.
"""

from __future__ import annotations

import itertools
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from ..build.documents import DEFAULT_PARAMS
from ..geo.profile import compute_profile
from ..geo.track import haversine_m
from .gazetteer import Place, normalize, search

GH_URL = "http://localhost:8989"
TRAIL_RADIUS_KM = 25.0
POINT_RADIUS_KM = 12.0
CITED_BUFFER_M = 35.0
OFF_CITED_FACTOR = "0.25"  # priorità fuori dai sentieri citati
TOL_DISTANCE = 0.10
TOL_ASCENT = 0.15
TOL_MAX_ELE_M = 50.0
LOOP_CLOSE_M = 200.0

GENERIC_PREFIXES = [
    r"parcheggio(?: di| del| della)?",
    r"stazione a monte(?: della)?(?: funivia)?",
    r"stazione a valle(?: della)?(?: funivia)?",
    r"funivia",
    r"ristorante",
    r"albergo",
    r"hotel",
    r"chiesetta di",
    r"chiesa di",
    r"localit[aà]",
    r"loc\.",
    r"centro di",
    r"paese di",
    r"abitato di",
    r"bagni di",
]


AREA_KINDS = {"valle", "ghiacciaio", "landuse:forest", "landuse:meadow", "boundary"}


@dataclass
class Point:
    query: str
    quota_m: float | None
    place: Place | None = None
    dem_ele: float | None = None
    how: str = ""


@dataclass
class Result:
    id: str
    status: str
    reasons: list[str] = field(default_factory=list)
    points: list[dict[str, Any]] = field(default_factory=list)
    cited_refs: list[str] = field(default_factory=list)
    cited_found: list[str] = field(default_factory=list)
    declared: dict[str, Any] = field(default_factory=dict)
    computed: dict[str, Any] = field(default_factory=dict)
    checks: dict[str, Any] = field(default_factory=dict)
    on_cited_share: float | None = None
    coords: list[list[float]] = field(default_factory=list)
    profile: list[list[float]] = field(default_factory=list)
    route_ms: float | None = None
    seconds: float | None = None


# ------------------------------------------------------------------ geocodifica


def query_variants(name: str) -> list[str]:
    out = [name]
    core = name
    for prefix in GENERIC_PREFIXES:
        core = re.sub(rf"^\s*{prefix}\s+", "", core, flags=re.IGNORECASE)
    if core != name and len(core) >= 3:
        out.append(core)
    # "Malga X" ↔ "X Alm", "Rifugio X" ↔ "X-Hütte": il gazetteer ha anche i nomi tedeschi
    m = re.match(
        r"(?i)^(malga|rifugio|lago|laghi|passo|monte|cima)\s+(?:di\s+|del\s+|della\s+)?(.+)$", core
    )
    if m and len(m.group(2)) >= 4:
        out.append(m.group(2))
    return list(dict.fromkeys(out))


# prima parola del nome → tipi di luogo attesi
EXPECTED_KINDS: list[tuple[str, set[str]]] = [
    (r"lag(?:o|hi|hetto|hetti)|see|seen", {"lago"}),
    (
        r"malga|malghe|alm|casere|casoni|baita|hütte|hutte",
        {"ristoro", "maso", "rifugio", "localita", "building:cabin", "building:hut"},
    ),
    (r"rifugio|schutzhaus|bivacco", {"rifugio", "bivacco"}),
    (r"cima|monte|punta|corno|croda|sass|dosso|piz|spitze|kofel", {"cima"}),
    (r"passo|forcella|forca|forcellina|sella|selletta|giogo|joch|scharte", {"sella", "passo"}),
    (r"chiesa|chiesetta|santuario|kirche|cappella", {"chiesa"}),
    (r"castel|castello|schloss|burg", {"castello"}),
    (r"cascata|cascate|wasserfall", {"cascata"}),
    (r"ponte|brücke", {"ponte"}),
    (r"maso|hof", {"maso", "albergo", "ristoro"}),
    (r"san|santa|santo|sankt|st|s", {"paese", "frazione", "chiesa", "localita", "maso"}),
    (r"parcheggio|parkplatz", {"parcheggio"}),
    (r"stazione|funivia|bergstation", {"funivia", "stazione"}),
]
GENERIC_WORDS = {
    "malga",
    "malghe",
    "rifugio",
    "lago",
    "laghi",
    "laghetto",
    "laghetti",
    "monte",
    "cima",
    "passo",
    "forcella",
    "forca",
    "sella",
    "selletta",
    "chiesa",
    "chiesetta",
    "di",
    "del",
    "della",
    "dei",
    "delle",
    "san",
    "santa",
    "sankt",
    "parcheggio",
    "stazione",
    "a",
    "funivia",
    "ristorante",
    "albergo",
    "hotel",
    "val",
    "valle",
    "bagni",
    "localita",
    "piana",
    "alm",
    "see",
    "maso",
    "hof",
    "baita",
    "casera",
    "capanna",
    "gasthof",
    "plan",
    "pian",
    "piano",
    "prato",
    "prati",
    "torrente",
    "rio",
    "ponte",
    "croce",
    "alta",
    "bassa",
    "di sopra",
    "di sotto",
}


def expected_kinds(query: str) -> set[str]:
    words = normalize(query).split()
    if len(words) == 1:
        return {"paese", "frazione", "localita", "maso"}  # un solo nome: di solito un abitato
    head = words[0]
    for pattern, kinds in EXPECTED_KINDS:
        if re.fullmatch(pattern, head):
            return kinds
    return set()


def core_matches(query: str, variant: str) -> bool:
    """Le parole distintive della ricerca ("Zocchi" in "Malga Zocchi") devono comparire."""
    from difflib import SequenceMatcher

    core = [w for w in normalize(query).split() if w not in GENERIC_WORDS and len(w) > 2]
    tokens = normalize(variant).split()
    if not core or not tokens:
        return True
    # composti tedeschi: "hof" in "miglanzerhof", "waldner" in "waldnersee"
    return all(
        any(w in t or SequenceMatcher(None, w, t).ratio() >= 0.75 for t in tokens) for w in core
    )


def _ele_bonus(declared: float | None, ele: float | None) -> float:
    if declared is None or ele is None:
        return 0.0
    diff = abs(ele - declared)
    return 0.2 if diff <= 40 else 0.1 if diff <= 90 else -0.1 if diff <= 250 else -0.3


def _candidates(
    conn: Any, point: Point, dem: Any, near: tuple[float, float] | None, radius_km: float
) -> list[tuple[float, Place, float | None, str]]:
    found: dict[int, tuple[float, Place, float | None, str]] = {}
    for i, q in enumerate(query_variants(point.query)):
        kinds = expected_kinds(point.query)
        for place in search(conn, q, near=near, radius_km=radius_km, limit=8):
            if not core_matches(point.query, place.variant or place.name):
                continue
            dem_ele = dem.elevation(place.lon, place.lat) if point.quota_m else None
            ele = place.ele if place.ele is not None else dem_ele
            score = place.score - 0.1 * i + _ele_bonus(point.quota_m, ele)
            if place.exact:
                score += 0.25
            if kinds and place.kind in kinds:
                score += 0.15
            if place.kind in AREA_KINDS:  # punto rappresentativo arbitrario: non è un passaggio
                score -= 0.3
            how = f"«{q}» → {place.name} ({place.kind})"
            if place.gid not in found or found[place.gid][0] < score:
                found[place.gid] = (score, place, dem_ele, how)
    return sorted(found.values(), key=lambda t: -t[0])


def _near_trails(conn: Any, lon: float, lat: float, refs: list[str], km: float = 1.5) -> bool:
    if not refs:
        return False
    plain, reg = _ref_lists(refs)
    with conn.cursor() as cur:
        cur.execute(
            """SELECT 1 FROM trails WHERE (upper(ref) = ANY(%s) OR upper(reg_ref) = ANY(%s))
               AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, %s)
               LIMIT 1""",
            (plain, reg, lon, lat, km * 1000),
        )
        return cur.fetchone() is not None


def search_radius_km(activity: dict[str, Any]) -> float:
    """Distanza massima di un punto chiave dalla partenza, dalla lunghezza o dalla durata."""
    km = activity.get("distanza_km")
    if not km and activity.get("durata"):
        h, m = str(activity["durata"]).split(":")
        km = 3.5 * (int(h) + int(m) / 60)  # stima prudente: 3,5 km/h
    if not km:
        return POINT_RADIUS_KM
    if activity.get("tipo_percorso") in {"anello", "andata_ritorno"}:
        return max(2.0, float(km) / 2 + 1.0)
    return max(2.0, float(km) + 1.0)


MUNICIPALITY_RADIUS_KM = 15.0


def municipality_anchor(conn: Any, comune: str | None) -> tuple[float, float] | None:
    """Il comune della partenza («Laces», «Scurelle (TN)») come àncora per i nomi comuni."""
    if not comune:
        return None
    name = re.sub(r"\s*\([A-Z]{2}\)\s*$", "", comune).strip()
    for place in search(conn, name, kinds=("paese", "frazione"), limit=3, min_similarity=0.6):
        if place.exact or place.similarity >= 0.9:
            return (place.lon, place.lat)
    return None


def geocode(
    conn: Any,
    dem: Any,
    points: list[Point],
    refs: list[str],
    radius_km: float = POINT_RADIUS_KM,
    anchor_hint: tuple[float, float] | None = None,
) -> list[Point]:
    """Partenza scelta sull'insieme (nome, quota, sentieri vicini, punto successivo), vicino al
    comune se noto; poi in sequenza, ciascun punto vicino al precedente."""
    if not points:
        return points
    first, rest = points[0], points[1:]
    best: tuple[float, Place, float | None, str] | None = None
    start_radius = MUNICIPALITY_RADIUS_KM if anchor_hint else 0
    for score, place, dem_ele, how in _candidates(conn, first, dem, anchor_hint, start_radius)[:8]:
        bonus = 0.25 if _near_trails(conn, place.lon, place.lat, refs) else 0.0
        if rest:
            nxt = _candidates(conn, rest[0], dem, (place.lon, place.lat), POINT_RADIUS_KM)
            if nxt:
                bonus += 0.4 * max(0.0, nxt[0][0])
        total = score + bonus
        if best is None or total > best[0]:
            best = (total, place, dem_ele, how)
    if best:
        first.place, first.dem_ele, first.how = best[1], best[2], best[3]
    anchor = (first.place.lon, first.place.lat) if first.place else None
    previous = anchor
    for point in rest:
        if previous is None:
            break
        # stesso nome della partenza (anelli): stesso luogo
        if first.place and normalize(point.query) == normalize(first.query):
            point.place, point.dem_ele, point.how = first.place, first.dem_ele, "come la partenza"
            continue
        cands = _candidates(conn, point, dem, previous, radius_km)
        scored = []
        for score, place, dem_ele, how in cands:
            d = haversine_m(previous, (place.lon, place.lat)) / 1000
            if anchor and haversine_m(anchor, (place.lon, place.lat)) / 1000 > radius_km:
                continue  # troppo lontano dalla partenza per questo itinerario
            scored.append((score - 0.05 * d, place, dem_ele, how))
        scored.sort(key=lambda t: -t[0])
        if scored and scored[0][0] >= 0.5:
            point.place, point.dem_ele, point.how = scored[0][1], scored[0][2], scored[0][3]
            previous = (point.place.lon, point.place.lat)
    # punti non trovati tra i luoghi: forse sono nomi di sentieri o strade
    for i, point in enumerate(points):
        if point.place is not None:
            continue
        before = next((p.place for p in reversed(points[:i]) if p.place), None)
        after = next((p.place for p in points[i + 1 :] if p.place), None)
        if before is None:
            continue
        hit = via_named_way(
            conn, point.query, (before.lon, before.lat), (after.lon, after.lat) if after else None
        )
        if hit:
            lon, lat, how = hit
            point.place = Place(-1, how, "via", lon, lat, None, 0.6, 0.6, None)
            point.how = how
    return points


def via_named_way(
    conn: Any, name: str, before: tuple[float, float], after: tuple[float, float] | None
) -> tuple[float, float, str] | None:
    """Punto su una via o un sentiero con quel nome ("Edelweisssteig", "Sentiero della Posta"),
    il più vicino al punto medio del tratto: diventa un punto di passaggio."""
    mid = before if after is None else ((before[0] + after[0]) / 2, (before[1] + after[1]) / 2)
    q = normalize(name)
    with conn.cursor() as cur:
        cur.execute(
            """WITH cand AS (
                   SELECT name, geom FROM osm_ways
                   WHERE name IS NOT NULL
                     AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%(lon)s,%(lat)s),4326), 0.12)
                   UNION ALL
                   SELECT name, (ST_Dump(geom)).geom FROM trails
                   WHERE name IS NOT NULL
                     AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%(lon)s,%(lat)s),4326), 0.12)
               )
               SELECT name, ST_X(p), ST_Y(p),
                      word_similarity(%(q)s, lower(unaccent(name))) AS sim
               FROM (SELECT name, ST_ClosestPoint(geom,
                        ST_SetSRID(ST_MakePoint(%(mx)s,%(my)s),4326)) AS p FROM cand) c
               ORDER BY sim DESC LIMIT 1""",
            {"lon": before[0], "lat": before[1], "q": q, "mx": mid[0], "my": mid[1]},
        )
        row = cur.fetchone()
    if row and row[3] >= 0.75:
        return row[1], row[2], f"via «{row[0]}» (somiglianza {row[3]:.2f})"
    return None


# ------------------------------------------------------------------ sentieri citati


def _ref_lists(refs: list[str]) -> tuple[list[str], list[str]]:
    plain, reg = [], []
    for r in refs:
        r = r.upper()
        m = re.fullmatch(r"([EO])(\d{1,3}[A-Z]?)", r)
        if m:
            reg.append(r)  # "E325" della SAT: in OSM2CAI ref = "325", reg_ref = "E325"
        else:
            plain.append(r)
    return plain, reg


def cited_trails(conn: Any, refs: list[str], center: tuple[float, float]) -> list[dict[str, Any]]:
    if not refs:
        return []
    plain, reg = _ref_lists(refs)
    with conn.cursor() as cur:
        cur.execute(
            """SELECT relation_id, osm2cai_id, ref, reg_ref, name, sda
               FROM trails
               WHERE (upper(ref) = ANY(%s) OR upper(reg_ref) = ANY(%s))
                 AND ST_DWithin(geom::geography,
                                ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, %s)""",
            (plain, reg, center[0], center[1], TRAIL_RADIUS_KM * 1000),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def named_routes(conn: Any, names: list[str], center: tuple[float, float]) -> list[dict[str, Any]]:
    """Itinerari citati per nome ("Cammino delle Terre Sospese", "Sentiero della Posta")."""
    out: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        for name in names:
            cur.execute(
                """SELECT relation_id, osm2cai_id, ref, reg_ref, name, sda FROM trails
                   WHERE name IS NOT NULL
                     AND word_similarity(%s, lower(unaccent(name))) >= 0.75
                     AND ST_DWithin(geom::geography,
                                    ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, %s)""",
                (normalize(name), center[0], center[1], TRAIL_RADIUS_KM * 1000),
            )
            cols = [d.name for d in cur.description]
            out.extend(dict(zip(cols, row, strict=True)) for row in cur.fetchall())
    return out


def _trail_filter(trails: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    rel = [t["relation_id"] for t in trails if t["relation_id"]]
    o2c = [t["osm2cai_id"] for t in trails if t["osm2cai_id"]]
    return rel, o2c


def cited_area(conn: Any, trails: list[dict[str, Any]]) -> dict[str, Any] | None:
    rel, o2c = _trail_filter(trails)
    if not rel and not o2c:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology(ST_Union(
                   ST_Buffer(geom::geography, %s)::geometry), 0.00008), 6)
               FROM trails WHERE relation_id = ANY(%s) OR osm2cai_id = ANY(%s)""",
            (CITED_BUFFER_M, rel, o2c),
        )
        row = cur.fetchone()
    if not row or not row[0]:
        return None
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": "citati", "properties": {}, "geometry": json.loads(row[0])}
        ],
    }


def on_cited_share(
    conn: Any, coords: list[list[float]], trails: list[dict[str, Any]]
) -> float | None:
    rel, o2c = _trail_filter(trails)
    if not coords or (not rel and not o2c):
        return None
    line = json.dumps({"type": "LineString", "coordinates": coords})
    with conn.cursor() as cur:
        cur.execute(
            """WITH t AS (SELECT ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s),4326), 32632) g),
                    c AS (SELECT ST_Buffer(ST_Union(ST_Transform(geom, 32632)), 25) g
                          FROM trails WHERE relation_id = ANY(%s) OR osm2cai_id = ANY(%s))
               SELECT ST_Length(ST_Intersection(t.g, c.g)) / NULLIF(ST_Length(t.g), 0)
               FROM t, c""",
            (line, rel, o2c),
        )
        row = cur.fetchone()
    return None if not row or row[0] is None else round(float(row[0]), 3)


# ------------------------------------------------------------------ routing


def route(points: list[tuple[float, float]], area: dict[str, Any] | None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "profile": "hike",
        "points": [list(p) for p in points],
        "points_encoded": False,
        "instructions": False,
        "ch.disable": True,
    }
    if area:
        body["custom_model"] = {
            "priority": [{"if": "!in_citati", "multiply_by": OFF_CITED_FACTOR}],
            "areas": area,
        }
    start = time.perf_counter()
    resp = httpx.post(f"{GH_URL}/route", json=body, timeout=180)
    ms = (time.perf_counter() - start) * 1000
    data = resp.json()
    if resp.status_code != 200 or "paths" not in data:
        return {"ok": False, "error": str(data.get("message", resp.text[:300])), "ms": ms}
    return {"ok": True, "coords": data["paths"][0]["points"]["coordinates"], "ms": ms}


# solo i punti "incerti" (cartelli, località, vie con nome) possono essere spostati: rifugi,
# malghe, cime, laghi e chiese sono mete, e la deviazione fa parte dell'itinerario
RELAXABLE_KINDS = {
    "palina",
    "via",
    "localita",
    "frazione",
    "paese",
    "fermata",
    "parcheggio",
    "stazione",
    "funivia",
    "altro",
}
SPUR_SAME_M = 25.0
SPUR_MIN_M = 100.0
SPUR_MAX_SHARE = 0.25


def relax_spurs(
    coords: list[list[float]], waypoints: list[tuple[float, float]], kinds: list[str | None]
) -> tuple[list[tuple[float, float]], list[str]]:
    """Punti intermedi raggiunti con una deviazione "vai e torna" (cartello o località fuori dal
    percorso): il punto si sposta all'innesto della deviazione. Mai la meta più lontana, mai
    quando c'è un solo punto intermedio, mai per deviazioni lunghe."""
    notes: list[str] = []
    out = list(waypoints)
    if len(waypoints) <= 3 or len(coords) < 3:
        return out, notes
    total = sum(haversine_m(a[:2], b[:2]) for a, b in itertools.pairwise(coords))
    farthest = max(
        range(1, len(waypoints) - 1), key=lambda k: haversine_m(waypoints[0], waypoints[k])
    )
    for k in range(1, len(waypoints) - 1):
        if k == farthest or kinds[k] not in RELAXABLE_KINDS:
            continue
        w = waypoints[k]
        j = min(range(len(coords)), key=lambda i: haversine_m(coords[i][:2], w))
        t, spur = 0, 0.0
        while (
            j - t - 1 >= 0
            and j + t + 1 < len(coords)
            and haversine_m(coords[j - t - 1][:2], coords[j + t + 1][:2]) < SPUR_SAME_M
        ):
            spur += haversine_m(coords[j - t - 1][:2], coords[j - t][:2])
            t += 1
        if SPUR_MIN_M < spur <= SPUR_MAX_SHARE * total:
            out[k] = (coords[j - t][0], coords[j - t][1])
            notes.append(f"punto {k + 1} spostato all'innesto di una deviazione di {spur:.0f} m")
    return out, notes


# ------------------------------------------------------------------ insieme


def _points_from(activity: dict[str, Any]) -> list[Point]:
    out = []
    for p in activity.get("punti_chiave") or []:
        out.append(Point(p["nome"], p.get("quota_m")))
    return out


def _pct(computed: float, declared: float) -> float:
    return (computed - declared) / declared if declared else math.inf


def reconstruct(conn: Any, dem: Any, activity_id: str, activity: dict[str, Any]) -> Result:
    t0 = time.perf_counter()
    res = Result(id=activity_id, status="fallita")
    refs = [str(r).upper() for r in activity.get("sentieri") or [] if str(r).upper() != "SI"]
    res.cited_refs = refs
    kind = activity.get("tipo_percorso")
    res.declared = {
        "tipo_percorso": kind,
        "distanza_km": activity.get("distanza_km"),
        "salita_m": activity.get("salita_m"),
        "discesa_m": activity.get("discesa_m"),
        "quota_max_m": activity.get("quota_max_m"),
        "durata": activity.get("durata"),
    }
    anchor_hint = municipality_anchor(conn, (activity.get("partenza") or {}).get("comune"))
    points = geocode(
        conn, dem, _points_from(activity), refs, search_radius_km(activity), anchor_hint
    )
    res.points = [
        {
            "nome": p.query,
            "quota_dichiarata": p.quota_m,
            "trovato": p.place.name if p.place else None,
            "tipo": p.place.kind if p.place else None,
            "lon": p.place.lon if p.place else None,
            "lat": p.place.lat if p.place else None,
            "quota_osm": p.place.ele if p.place else None,
            "quota_dem": round(p.dem_ele) if p.dem_ele else None,
            "come": p.how,
        }
        for p in points
    ]
    if not points or points[0].place is None:
        res.reasons.append("partenza non trovata nei luoghi OSM")
        res.seconds = round(time.perf_counter() - t0, 1)
        return res
    missing = [p.query for p in points if p.place is None]
    for name in missing:
        res.reasons.append(f"punto non trovato: {name}")
    placed = [p for p in points if p.place]
    resolved = [(p.place.lon, p.place.lat) for p in placed]
    # punti consecutivi coincidenti (stesso luogo) non servono al routing
    waypoints = [resolved[0]]
    kinds: list[str | None] = [placed[0].place.kind]
    for p, pt in zip(placed[1:], resolved[1:], strict=True):
        if haversine_m(waypoints[-1], pt) > 30:
            waypoints.append(pt)
            kinds.append(p.place.kind)
    if len(waypoints) < 2:
        res.reasons.append("meno di due punti distinti: percorso non ricostruibile")
        res.seconds = round(time.perf_counter() - t0, 1)
        return res

    trails = cited_trails(conn, refs, resolved[0])
    found_refs = sorted({(t["reg_ref"] or t["ref"] or "").upper() for t in trails} - {""})
    res.cited_found = found_refs
    missing_refs = [
        r
        for r in refs
        if r not in found_refs and not any((t["ref"] or "").upper() == r for t in trails)
    ]
    if missing_refs:
        res.reasons.append(f"sentieri citati non trovati in OSM/OSM2CAI: {', '.join(missing_refs)}")
    routes = named_routes(conn, list(activity.get("reti") or []), resolved[0])
    if routes:
        res.cited_found += sorted({r["name"] for r in routes})
        trails = trails + routes
    area = cited_area(conn, trails)
    out = route(waypoints, area)
    res.route_ms = round(out["ms"])
    if not out["ok"]:
        res.reasons.append(f"routing fallito: {out['error'][:160]}")
        res.seconds = round(time.perf_counter() - t0, 1)
        return res
    coords = out["coords"]
    relaxed, notes = relax_spurs(coords, waypoints, kinds)
    if notes:
        again = route(relaxed, area)
        if again["ok"]:
            coords = again["coords"]
            res.reasons.extend(f"nota: {n}" for n in notes)
    if kind == "andata_ritorno":
        # andata e ritorno per la stessa via: la traccia è l'andata ripercorsa all'indietro
        coords = coords + coords[-2::-1]
    res.coords = [[round(c[0], 6), round(c[1], 6)] for c in coords]
    prof = compute_profile([c[:2] for c in coords], dem, DEFAULT_PARAMS)
    res.computed = {
        "distanza_km": round(prof.length_m / 1000, 2),
        "salita_m": round(prof.ascent_m),
        "discesa_m": round(prof.descent_m),
        "quota_max_m": round(prof.max_ele_m),
        "quota_min_m": round(prof.min_ele_m),
        "minuti_cai": round(prof.minutes_forward),
    }
    step = max(1, len(prof.distances_m) // 300)
    res.profile = [
        [round(d), round(e)]
        for d, e in zip(prof.distances_m[::step], prof.elevations_m[::step], strict=True)
    ]
    res.on_cited_share = on_cited_share(conn, res.coords, trails)

    checks: dict[str, Any] = {}
    d = res.declared
    start = (activity.get("partenza") or {}).get("quota_m") or points[0].dem_ele
    if start is None and points[0].place:
        start = dem.elevation(points[0].place.lon, points[0].place.lat)
    if d["salita_m"] and d["quota_max_m"] and start:
        minimum = float(d["quota_max_m"]) - float(start)
        if float(d["salita_m"]) < minimum - 50:
            res.reasons.append(
                f"dislivello dichiarato incoerente: {d['salita_m']} m < {minimum:.0f} m tra "
                f"partenza ({start:.0f} m) e quota massima ({d['quota_max_m']} m)"
            )
            d = {**d, "salita_m": None}  # non confrontabile
    if d["distanza_km"]:
        pct = _pct(res.computed["distanza_km"], float(d["distanza_km"]))
        checks["distanza"] = {"scarto": round(pct, 3), "ok": abs(pct) <= TOL_DISTANCE}
    if d["salita_m"]:
        pct = _pct(res.computed["salita_m"], float(d["salita_m"]))
        checks["salita"] = {"scarto": round(pct, 3), "ok": abs(pct) <= TOL_ASCENT}
    if d["quota_max_m"]:
        diff = res.computed["quota_max_m"] - float(d["quota_max_m"])
        checks["quota_max"] = {"scarto_m": round(diff), "ok": abs(diff) <= TOL_MAX_ELE_M}
    if kind == "anello":
        gap = haversine_m(coords[0][:2], coords[-1][:2])
        checks["anello_chiuso"] = {"distanza_m": round(gap), "ok": gap <= LOOP_CLOSE_M}
    res.checks = checks

    for name, c in checks.items():
        if not c["ok"]:
            if name == "distanza":
                res.reasons.append(f"distanza fuori tolleranza ({c['scarto']:+.0%})")
            elif name == "salita":
                res.reasons.append(f"dislivello in salita fuori tolleranza ({c['scarto']:+.0%})")
            elif name == "quota_max":
                res.reasons.append(f"quota massima fuori tolleranza ({c['scarto_m']:+d} m)")
            else:
                res.reasons.append(f"l'anello non si chiude ({c['distanza_m']} m)")
    numeric = [k for k in checks if k in {"distanza", "salita"}]
    all_ok = all(c["ok"] for c in checks.values())
    geocoded_share = 1 - len(missing) / len(points)
    if not numeric:
        res.reasons.append("nessuna distanza o dislivello dichiarati utilizzabili per il confronto")
    # tollerato un solo punto intermedio non trovato, se i numeri tornano
    if all_ok and numeric and (geocoded_share >= 0.75 or len(missing) <= 1):
        res.status = "auto_ok"
    else:
        res.status = "da_rivedere"
    res.seconds = round(time.perf_counter() - t0, 1)
    return res


def result_dict(res: Result) -> dict[str, Any]:
    return asdict(res)
