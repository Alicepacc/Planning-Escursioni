"""Indice di Esplora (SPEC §5.1): un elenco unico e leggero di tutto ciò che si può proporre.

- sentieri del catasto CAI (schede della Fase 1), attività CAI (archivio del pilota), itinerari;
- per ciascuno: metriche per filtri e card (tempo, km, D+, D−, quota massima, difficoltà, tipo),
  partenza, riquadro, **mini-profilo** (24 quote), **etichette** (lago, cima, rifugio, acqua,
  panorama) dai luoghi OSM vicini alla traccia, **stagione indicativa** dalla quota;
- un indice dei **luoghi** (cime, rifugi, laghi, paesi, passi, valli) per la ricerca testuale e
  per «distanza da una località», tutto lato client: nessun geocoder esterno.

Scrive `static/data/esplora/index.json` e `static/data/esplora/luoghi.json`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import psycopg

PROFILE_SAMPLES = 24
# etichetta → (tipi di luogo, distanza massima dalla traccia in metri)
TAGS: dict[str, tuple[tuple[str, ...], float]] = {
    "lago": (("lago",), 250.0),
    "cima": (("cima",), 60.0),
    "rifugio": (("rifugio",), 120.0),
    "acqua": (("sorgente", "acqua_potabile"), 80.0),
    "panorama": (("panorama",), 100.0),
}
PLACE_KINDS = {
    "cima": "c",
    "rifugio": "r",
    "bivacco": "b",
    "lago": "l",
    "paese": "p",
    "frazione": "f",
    "sella": "s",
    "passo": "s",
    "valle": "v",
    "ghiacciaio": "g",
}


def _n(value: Any) -> float | None:
    """Numero da un valore del catasto, che a volte è una stringa ("939", "9,7", "")."""
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def season(max_ele: float, difficulty: str | None) -> list[int]:
    """Mesi consigliati (indicativi) dalla quota massima; le ciaspolate d'inverno."""
    if difficulty and difficulty.upper().startswith("EAI"):
        return [12, 1, 2, 3]
    if max_ele < 1200:
        return [3, 4, 5, 6, 7, 8, 9, 10, 11]
    if max_ele < 1800:
        return [5, 6, 7, 8, 9, 10]
    if max_ele < 2400:
        return [6, 7, 8, 9, 10]
    return [7, 8, 9]


def mini_profile(points: list[list[float]], n: int = PROFILE_SAMPLES) -> list[int]:
    if not points:
        return []
    total = points[-1][0] or 1.0
    out, j = [], 0
    for k in range(n):
        target = total * k / (n - 1)
        while j + 1 < len(points) and points[j + 1][0] <= target:
            j += 1
        out.append(round(points[j][1]))
    return out


def _tags_for(conn: psycopg.Connection, lines: dict[str, list[list[float]]]) -> dict[str, set[str]]:
    """Etichette per ogni elemento: luoghi OSM entro una certa distanza dalla traccia."""
    out: dict[str, set[str]] = {k: set() for k in lines}
    with conn.cursor() as cur:
        cur.execute("CREATE TEMP TABLE IF NOT EXISTS esplora_linee (id text, geom geometry)")
        cur.execute("TRUNCATE esplora_linee")
        with cur.copy("COPY esplora_linee (id, geom) FROM STDIN") as copy:
            for item_id, coords in lines.items():
                if len(coords) < 2:
                    continue
                wkt = "LINESTRING(" + ",".join(f"{c[0]} {c[1]}" for c in coords) + ")"
                copy.write_row((item_id, f"SRID=4326;{wkt}"))
        cur.execute("CREATE INDEX ON esplora_linee USING gist (geom)")
        cur.execute("ANALYZE esplora_linee")
        for tag, (kinds, meters) in TAGS.items():
            deg = meters / 80000  # filtro grossolano in gradi, poi distanza vera in metri
            cur.execute(
                """SELECT DISTINCT l.id FROM esplora_linee l JOIN osm_pois p
                   ON p.kind = ANY(%s) AND ST_DWithin(l.geom, p.geom, %s)
                   WHERE ST_DWithin(l.geom::geography, p.geom::geography, %s)""",
                (list(kinds), deg, meters),
            )
            for (item_id,) in cur.fetchall():
                out[item_id].add(tag)
    return out


def _trail_items(sentieri_dir: Path) -> list[dict[str, Any]]:
    index = json.loads((sentieri_dir / "index.json").read_text(encoding="utf-8"))["trails"]
    items = []
    for entry in index:
        doc = json.loads((sentieri_dir / f"{entry['id']}.json").read_text(encoding="utf-8"))
        c, o = doc["computed"], doc["official"]
        minutes = _n(o.get("duration_forward_min")) or c["cai_forward_min"]
        name = doc["name"] or (f"{doc['from']} – {doc['to']}" if doc["from"] else "")
        items.append(
            {
                "id": doc["id"],
                "k": "s",  # sentiero
                "t": f"{doc['ref']} {name}".strip() if doc["ref"] else name or "Sentiero",
                "sub": f"{doc['from']} – {doc['to']}" if doc["from"] and doc["to"] else "",
                "src": "Catasto CAI (OSM2CAI)" if doc.get("sda") else "Rete OSM",
                "min": round(minutes),
                "km": round(_n(o.get("distance_km")) or c["distance_km"], 1),
                "up": round(_n(o.get("ascent_m")) or c["ascent_m"]),
                "dn": round(_n(o.get("descent_m")) or c["descent_m"]),
                "max": round(c["max_ele_m"]),
                "d": doc["difficulty"]["cai"],
                "ty": "anello" if doc.get("roundtrip") else "traversata",
                "s": [round(doc["line"][0][0], 5), round(doc["line"][0][1], 5)],
                "b": doc["bbox"],
                "p": mini_profile(doc["profile"]["points"]),
                "sda": doc.get("sda"),
                "iss": doc["issues"]["status"] if doc.get("issues") else None,
                "_line": doc["line"],
            }
        )
    return items


NAME_TAGS: dict[str, tuple[str, ...]] = {
    "lago": ("lago", "laghi", "laghetto", "laghetti", "see"),
    "cima": ("cima", "monte", "corno", "punta", "croda", "spitze", "kofel", "dosso", "piz"),
    "rifugio": ("rifugio", "malga", "baita", "hutte", "hütte", "alm"),
    "acqua": ("sorgente", "fontana"),
}


def tags_from_names(names: list[str]) -> set[str]:
    """Etichette dai nomi dei punti chiave, quando la traccia non è verificata: conta la prima
    parola («Rifugio Monte Cavone» è un rifugio, non una cima) o il suffisso tedesco («See»)."""
    out = set()
    for name in names:
        words = name.lower().replace("-", " ").split()
        if not words:
            continue
        for tag, keys in NAME_TAGS.items():
            if words[0] in keys or (tag in {"lago", "rifugio"} and words[-1] in keys):
                out.add(tag)
    return out


def _minutes(duration: str | None) -> int | None:
    if not duration:
        return None
    h, m = str(duration).split(":")
    return int(h) * 60 + int(m)


def _itinerary_items(folder: Path, kind: str) -> list[dict[str, Any]]:
    """Attività e itinerari. Se la traccia non è verificata, solo i valori dichiarati: un
    valore calcolato su una traccia forse sbagliata sarebbe un'informazione falsa."""
    items = []
    if not folder.exists():
        return items
    for path in sorted(folder.glob("*.json")):
        if path.name == "index.json":
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        d, c = doc["declared"], doc["computed"]
        act = doc.get("activity") or {}
        organizers = ", ".join(o for o in act.get("organizers", []) if o)
        when = act.get("date")
        src = f"{organizers}, {'/'.join(reversed(when.split('-')))}" if when else organizers
        verification = doc.get("verification") or {}
        verified = verification.get("status", "auto_ok") == "auto_ok"

        def pick(declared: Any, computed: Any, digits: int = 0, ok: bool = verified) -> Any:
            value = declared if declared is not None else (computed if ok else None)
            return None if value is None else round(float(value), digits or None)

        stage_names = [s["name"] for s in doc.get("stages") or []]
        stage_eles = [
            s["declared_ele_m"] for s in doc.get("stages") or [] if s.get("declared_ele_m")
        ]
        items.append(
            {
                "id": doc["id"],
                "k": "a" if kind == "attivita" else "i",
                "t": doc["title"],
                "sub": doc.get("group") or "",
                "src": src,
                "date": when,
                "fut": bool(act.get("future")),
                "min": pick(_minutes(d.get("duration")), c["cai_forward_min"]),
                "km": pick(d.get("distance_km"), c["distance_km"], 1),
                "up": pick(d.get("ascent_m"), c["ascent_m"]),
                "dn": pick(d.get("descent_m"), c["descent_m"]),
                "max": pick(d.get("max_ele_m"), c["max_ele_m"]),
                "d": (doc.get("difficulty") or {}).get("cai")
                or ((doc.get("difficulty") or {}).get("raw") or None),
                "ty": doc.get("type") or "traversata",
                "s": [round(doc["line"][0][0], 5), round(doc["line"][0][1], 5)],
                "b": doc["bbox"],
                "p": mini_profile(doc["profile"]["points"]) if verified else [],
                "ok": verified,
                # deduplica (§7.5): altre proposte dello stesso itinerario, membri nascosti
                **({"alt": len(doc["proposals"]) - 1} if doc.get("proposals") else {}),
                **({"hide": True} if doc.get("canonical") not in (None, doc["id"]) else {}),
                "_line": doc["line"],
                "_names": None if verified else stage_names,
                "_season_ele": d.get("max_ele_m")
                or (max(stage_eles) if stage_eles else None)
                or c["max_ele_m"],
            }
        )
    return items


def build_places(conn: psycopg.Connection) -> list[list[Any]]:
    """[nome, tipo, lon, lat, quota] dei luoghi da cercare, senza doppioni nodo/area."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT DISTINCT ON (kind_code, lower(name), round(ST_X(geom)::numeric, 2),
                                  round(ST_Y(geom)::numeric, 2))
                      name, kind_code, ST_X(geom), ST_Y(geom), ele
               FROM (SELECT name, CASE kind """
            + " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in PLACE_KINDS.items())
            + """ END AS kind_code, geom, ele FROM gazetteer
                     WHERE kind = ANY(%s) AND name IS NOT NULL) g
               ORDER BY kind_code, lower(name), round(ST_X(geom)::numeric, 2),
                        round(ST_Y(geom)::numeric, 2), ele NULLS LAST""",
            (list(PLACE_KINDS),),
        )
        rows = cur.fetchall()
    return [
        [name, code, round(x, 5), round(y, 5), round(ele) if ele else None]
        for name, code, x, y, ele in rows
    ]


def build_explore(conn: psycopg.Connection, static_dir: Path) -> dict[str, Any]:
    data = static_dir / "data"
    items = (
        _itinerary_items(data / "attivita", "attivita")
        + _itinerary_items(data / "itinerari", "itinerario")
        + _trail_items(data / "sentieri")
    )
    tags = _tags_for(conn, {it["id"]: it["_line"] for it in items})
    for it in items:
        names = it.pop("_names", None)
        it["tag"] = sorted(
            tags_from_names(names) if names is not None else tags.get(it["id"], set())
        )
        it["mo"] = season(it.pop("_season_ele", None) or it["max"], it.get("d"))
        del it["_line"]
    out = data / "esplora"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1,
        "generated_at": time.strftime("%Y-%m-%d"),
        "fields": {
            "k": "s=sentiero del catasto, a=attività CAI, i=itinerario",
            "min": "tempo in minuti (dichiarato o calcolato, senza soste)",
            "mo": "mesi consigliati, indicativi (dalla quota massima)",
            "p": f"mini-profilo: {PROFILE_SAMPLES} quote equidistanti",
            "tag": "luoghi OSM vicini alla traccia",
        },
        "items": items,
    }
    (out / "index.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    places = build_places(conn)
    (out / "luoghi.json").write_text(
        json.dumps({"schema": 1, "places": places}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return {"elementi": len(items), "luoghi": len(places)}
