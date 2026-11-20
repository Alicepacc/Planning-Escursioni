"""Documenti delle attività CAI per la PWA (archivio attività, SPEC §5.2 e §7.5).

Ogni attività rivista con una traccia ricostruita diventa un documento nel formato degli
itinerari (`kind: "attivita"`), letto dalla stessa pagina della fixture. Contenuti:

- **sintesi** composta solo dai dati (tipo, km, dislivello, punti chiave con quota): nessun
  testo copiato dalla locandina, come consente la risposta del CAI (sintesi + link + data);
- link alla **locandina originale** sul sito della sezione e data dell'attività;
- **stato della ricostruzione** (auto_ok / da rivedere con i motivi): le tracce non verificate
  sono marcate come tali nella PWA;
- attrezzatura **indicativa**, derivata da difficoltà, stagione e quota.

Nessun dato personale: i campi rivisti non ne contengono.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import yaml

from ..activities.dedup import group
from ..activities.reliability import THRESHOLD, score
from ..config import data_dir, repo_root
from ..difficulty import normalize_cai
from ..geo.area import in_area
from ..geo.profile import compute_profile
from .documents import (
    DEFAULT_PARAMS,
    SCHEMA_VERSION,
    computed_payload,
    profile_payload,
    simplified_line,
    stages,
    trails_along,
)

KIND_LABEL = {"anello": "Anello", "traversata": "Traversata", "andata_ritorno": "Andata e ritorno"}
WINTER_MONTHS = {12, 1, 2, 3}


def slug(text: str) -> str:
    """Accenti e dieresi tolti («Pederü» → «pederu», «Günther» → «gunther»)."""
    text = unicodedata.normalize("NFKD", text.lower().replace("ß", "ss"))
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60]


def activity_slug(activity_id: str, act: dict[str, Any]) -> str:
    """Indirizzo leggibile e stabile: data + titolo (+ sezione per evitare collisioni)."""
    when = str(act.get("data") or "senza-data")
    section = slug(str(act.get("sezione", "")).replace("CAI ", "").replace("SAT ", "sat-"))
    return f"{when}-{slug(act.get('titolo', activity_id))}-{section}"[:90].strip("-")


def summary(act: dict[str, Any], computed: dict[str, Any], verified: bool = True) -> str:
    """Una frase composta dai soli dati: tipo, lunghezza, dislivello, partenza, punti chiave.
    Con una traccia non verificata, solo i valori dichiarati (i calcolati potrebbero essere
    falsi)."""
    kind = KIND_LABEL.get(act.get("tipo_percorso") or "", "Itinerario")
    km = act.get("distanza_km") or (computed["distance_km"] if verified else None)
    up = act.get("salita_m") or (computed["ascent_m"] if verified else None)
    start = (act.get("partenza") or {}).get("nome")
    points = [
        p["nome"] + (f" ({p['quota_m']} m)" if p.get("quota_m") else "")
        for p in act.get("punti_chiave") or []
        if p.get("nome") and p.get("nome") != start
    ]
    seen: list[str] = []
    for p in points:
        if p not in seen:
            seen.append(p)
    measures = [
        f"circa {round(float(km))} km" if km else "",
        f"{round(float(up))} m di dislivello" if up else "",
    ]
    measures = [m for m in measures if m]
    text = kind + (" di " + " e ".join(measures) if measures else "")
    if start:
        text += f" con partenza da {start}"
    if seen:
        text += ": " + ", ".join(seen[:6]) + ("…" if len(seen) > 6 else "")
    return text + "."


def equipment(act: dict[str, Any], max_ele: float) -> list[str]:
    out = [
        "calzature da escursionismo",
        "acqua e cibo",
        "kit di primo soccorso",
        "carta dei sentieri",
    ]
    day = act.get("data")
    month = day.month if isinstance(day, date) else int(str(day)[5:7]) if day else None
    diff = (act.get("difficolta") or "").upper()
    if diff.startswith("EAI") or (month in WINTER_MONTHS and max_ele > 1200):
        out += ["ciaspole e ramponcini", "ARTVA, pala e sonda dove il bollettino lo richiede"]
    if max_ele > 2000:
        out.append("giacca antivento e strato caldo")
    if diff in {"EE", "EEA", "E-EE"}:
        out.append("scarponi con suola rigida, passo sicuro")
    if diff == "EEA":
        out.append("set da ferrata dove indicato")
    if "notturna" in (act.get("titolo") or "").lower():
        out.append("frontale")
    return out


def _status_text(track: dict[str, Any]) -> str:
    if track["status"] == "fallita":
        reasons = [r for r in track["reasons"] if not r.startswith("nota:")]
        return (
            "Percorso non ricostruito dai dati della locandina: sulla mappa ci sono solo i punti "
            "trovati. Motivi: " + "; ".join(reasons) + "."
        )
    if track["status"] == "auto_ok":
        return (
            "Traccia ricostruita automaticamente da OSM e OSM2CAI: distanza, dislivello e quota "
            "massima coerenti con la locandina."
        )
    reasons = [r for r in track["reasons"] if not r.startswith("nota:")]
    return (
        "Traccia ricostruita automaticamente e non ancora verificata: può non coincidere con il "
        "percorso della sezione. Motivi: " + "; ".join(reasons) + "."
    )


NO_TRACK_BBOX_PAD = 0.03  # gradi attorno alla partenza, se manca la traccia
AREA_BBOX = [10.38, 44.79, 13.1, 47.09]  # Trentino-Alto Adige e Veneto, se non c'è alcun punto


def _no_track_computed(act: dict[str, Any]) -> dict[str, Any]:
    """Senza traccia nessun valore è calcolato: zeri che l'app non mostra (traccia non
    verificata), con la sola quota massima della locandina per la stagione."""
    keys = ("distance_km", "ascent_m", "descent_m", "min_ele_m", "cai_forward_min")
    keys += ("cai_backward_min", "din_forward_min", "din_backward_min", "steep_m", "gaps")
    return {**dict.fromkeys(keys, 0), "max_ele_m": act.get("quota_max_m") or 0, "method": {}}


def activity_document(
    activity_id: str, act: dict[str, Any], track: dict[str, Any], url: str | None, conn, dem
) -> dict[str, Any]:
    """Scheda dell'attività. Con la ricostruzione fallita (ADR 0013) la scheda resta, senza
    linea né valori calcolati. I punti trovati vanno sulla mappa solo se la locandina indica la
    partenza e la gita non è segnata fuori area in revisione (`fuori_area`): un punto isolato,
    senza un secondo che lo confermi, può essere un omonimo lontano."""
    has_line = track["status"] != "fallita" and len(track.get("coords") or []) >= 2
    waypoints = [
        {
            "nome": p["nome"],
            "quota_dichiarata": p.get("quota_dichiarata"),
            "lon": p["lon"],
            "lat": p["lat"],
        }
        for p in track["points"]
        if p.get("lon") is not None
    ]
    if not has_line and (not act.get("partenza") or act.get("fuori_area")):
        waypoints = []
    places = [{"name": w["nome"], "lon": w["lon"], "lat": w["lat"]} for w in waypoints]
    if has_line:
        coords = track["coords"]
        prof = compute_profile(coords, dem, DEFAULT_PARAMS)
        computed = computed_payload(prof)
        xs, ys = [c[0] for c in coords], [c[1] for c in coords]
    elif waypoints:
        coords = [[waypoints[0]["lon"], waypoints[0]["lat"]]]
        prof = None
        computed = _no_track_computed(act)
        xs = [w["lon"] for w in waypoints] + [coords[0][0] - NO_TRACK_BBOX_PAD]
        xs.append(coords[0][0] + NO_TRACK_BBOX_PAD)
        ys = [w["lat"] for w in waypoints] + [coords[0][1] - NO_TRACK_BBOX_PAD]
        ys.append(coords[0][1] + NO_TRACK_BBOX_PAD)
    else:
        coords, prof, computed = [], None, _no_track_computed(act)
        xs, ys = AREA_BBOX[::2], AREA_BBOX[1::2]
    if act.get("tipo_percorso") == "andata_ritorno" and waypoints:
        waypoints.append(dict(waypoints[0]))  # ritorno alla partenza
    start = act.get("partenza") or {}
    diff_raw = act.get("difficolta") or act.get("difficolta_testo")
    declared = {
        "distance_km": act.get("distanza_km"),
        "ascent_m": act.get("salita_m"),
        "descent_m": act.get("discesa_m"),
        "max_ele_m": act.get("quota_max_m"),
        "duration": act.get("durata"),
        "difficulty": diff_raw,
    }
    when = str(act["data"]) if act.get("data") else None
    future = bool(when and when >= time.strftime("%Y-%m-%d"))
    return {
        "schema": SCHEMA_VERSION,
        "kind": "attivita",
        "id": activity_slug(activity_id, act),
        "title": act["titolo"],
        "group": act.get("zona") or "",
        "type": act.get("tipo_percorso") or "",
        "start": {
            "nome": start.get("nome") or "",
            "quota_m": start.get("quota_m"),
            "comune": start.get("comune") or "",
            **({"ora": act["ora_ritrovo"]} if act.get("ora_ritrovo") else {}),
            "lon": coords[0][0] if coords else None,
            "lat": coords[0][1] if coords else None,
        },
        "difficulty": {"cai": normalize_cai(str(act.get("difficolta") or "")), "raw": diff_raw},
        "declared": declared,
        "computed": computed,
        "trails": trails_along(conn, coords) if has_line else [],
        "networks": act.get("reti") or [],
        "off_trail": [],
        "stages": stages(prof, waypoints) if prof and waypoints else [],
        **({} if has_line else {"places": places}),
        "equipment": equipment(act, computed["max_ele_m"]),
        "notes": [],
        "map_reference": "",
        "summary": summary(act, computed, track["status"] == "auto_ok"),
        "activity": {
            "date": when,
            "future": future,
            "organizers": [act.get("sezione") or ""],
            "signup_note": (
                "Iscrizione sul sito della sezione, se l'attività è ancora in programma: "
                "l'app non gestisce le iscrizioni CAI."
                if future
                else "Attività già svolta: proposta d'archivio della sezione."
            ),
            "source_url": url,
            "source_page": act.get("pagina"),
            "transport": act.get("mezzi"),
        },
        "verification": {
            "status": track["status"],
            "reasons": [r for r in track["reasons"] if not r.startswith("nota:")],
            "on_cited_share": track.get("on_cited_share"),
        },
        "bbox": [round(min(xs), 5), round(min(ys), 5), round(max(xs), 5), round(max(ys), 5)],
        "line": simplified_line(coords) if has_line else [],
        "profile": (
            profile_payload(prof)
            if prof
            else {"columns": ["dist_m", "ele_m", "lon", "lat", "min"], "points": []}
        ),
        "reconstruction": _status_text(track),
        "attribution": [
            f"Attività: {act.get('sezione')} "
            "(sintesi dei dati della locandina, con link all'originale)",
            "© OpenStreetMap contributors (ODbL)",
            "© Club Alpino Italiano – INFOMONT (ODbL)",
            "Quote: Mapterhorn",
        ],
        "generated_at": time.strftime("%Y-%m-%d"),
    }


def link_duplicates(docs: list[dict[str, Any]], coords: dict[str, list]) -> dict[str, int]:
    """Itinerari canonici e varianti (SPEC §7.5), scritti nei documenti."""
    by_id = {d["id"]: d for d in docs}
    tracks = {
        d["id"]: {
            "coords": coords[d["id"]],
            "bbox": d["bbox"],
            "verified": (d.get("verification") or {}).get("status") == "auto_ok",
            "date": (d.get("activity") or {}).get("date"),
        }
        for d in docs
    }
    groups, relations = group(tracks)
    for g in groups:
        proposals = [
            {
                "id": m,
                "section": ", ".join(by_id[m]["activity"]["organizers"]),
                "date": by_id[m]["activity"]["date"],
            }
            for m in sorted(g.members, key=lambda m: str(by_id[m]["activity"]["date"] or ""))
        ]
        for m in g.members:
            by_id[m]["canonical"] = g.canonical
        by_id[g.canonical]["proposals"] = proposals
    for r in relations:
        if r["relation"] != "variante":
            continue
        for a, b in ((r["a"], r["b"]), (r["b"], r["a"])):
            by_id[a].setdefault("related", []).append(
                {
                    "id": b,
                    "title": by_id[b]["title"],
                    "relation": "variante",
                    "hausdorff_m": r["hausdorff_m"],
                }
            )
    return {"gruppi": len(groups), "varianti": sum(r["relation"] == "variante" for r in relations)}


def zone_for(conn: psycopg.Connection, coords: list[list[float]]) -> str:
    """Zona di un'escursione del catalogo: la valle con nome più vicina al centro della traccia,
    altrimenti il paese più vicino (per le schede rivedute la zona l'ha scritta una persona)."""
    lon = sum(p[0] for p in coords) / len(coords)
    lat = sum(p[1] for p in coords) / len(coords)
    for kind, km in (("valle", 6), ("paese", 12)):
        row = conn.execute(
            """SELECT coalesce(name_it, name) FROM gazetteer
               WHERE kind = %s AND ST_DWithin(geom::geography, ST_MakePoint(%s, %s)::geography, %s)
               ORDER BY geom::geography <-> ST_MakePoint(%s, %s)::geography LIMIT 1""",
            (kind, lon, lat, km * 1000, lon, lat),
        ).fetchone()
        if row and row[0]:
            return row[0]
    return ""


def build_activities(conn: psycopg.Connection, dem, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    reviewed_dirs = [
        repo_root() / "config" / "pilot" / "reviewed",
        repo_root() / "config" / "activities" / "reviewed",  # blocchi della Fase 3
    ]
    tracks = data_dir() / "activities" / "tracks"
    manifest = json.loads((data_dir() / "activities" / "raw" / "manifest.json").read_text("utf-8"))
    docs: list[dict[str, Any]] = []
    skipped = {"revisionate": 0, "catalogo": 0}
    coords: dict[str, list] = {}
    statuses: dict[str, str] = {}
    for path in sorted(p for d in reviewed_dirs if d.exists() for p in d.glob("*.yaml")):
        activity_id = path.stem
        act = yaml.safe_load(path.read_text(encoding="utf-8"))
        track_path = tracks / f"{activity_id}.json"
        if not track_path.exists():
            continue
        track = json.loads(track_path.read_text(encoding="utf-8"))
        url = manifest.get(act.get("documento", activity_id), {}).get("url")
        # ADR 0015: solo le escursioni affidabili (da 80 su 100) e nell'area del catalogo
        reliability = score(track)
        if reliability["punteggio"] < THRESHOLD or not in_area(track.get("coords")):
            skipped["revisionate"] += 1
            continue
        doc = activity_document(activity_id, act, track, url, conn, dem)
        doc["reliability"] = reliability["punteggio"]
        doc["_section"] = act.get("sezione")
        docs.append(doc)
        coords[doc["id"]] = track["coords"]
        statuses[doc["id"]] = track["status"]
    # catalogo a lotti (ADR 0015): le schede pubblicabili ricostruite dal solo parser
    catalog = data_dir() / "activities" / "catalogo"
    seen = {d["id"] for d in docs}
    for rec_path in sorted((catalog / "record").glob("*.json")) if catalog.exists() else []:
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        if rec.get("esito") != "pubblicabile" or not rec.get("area"):
            continue
        track_path = catalog / "tracce" / f"{rec['id']}.json"
        if not track_path.exists():
            continue
        track = json.loads(track_path.read_text(encoding="utf-8"))
        act = {k: v for k, v in rec["attivita"].items() if k != "punti_dal_testo"}
        act["sezione"] = rec["sezione"]
        act["zona"] = zone_for(conn, track["coords"])
        doc = activity_document(rec["id"], act, track, rec["url"], conn, dem)
        if doc["id"] in seen:
            continue
        seen.add(doc["id"])
        doc["reliability"] = rec["affidabilita"]["punteggio"]
        doc["_section"] = rec["sezione"]
        docs.append(doc)
        coords[doc["id"]] = track["coords"]
        statuses[doc["id"]] = track["status"]
        skipped["catalogo"] += 1
    # la deduplica confronta le tracce: le attività senza linea restano a sé
    dedup = link_duplicates([d for d in docs if d["line"]], coords)
    index = []
    for doc in docs:
        section = doc.pop("_section")
        (out_dir / f"{doc['id']}.json").write_text(
            json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        index.append(
            {
                "id": doc["id"],
                "title": doc["title"],
                "section": section,
                "date": doc["activity"]["date"],
                "status": statuses[doc["id"]],
                "canonical": doc.get("canonical"),
            }
        )
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    # schede di attività non più costruite (ricostruzione diventata fallita, id cambiato)
    keep = {f"{d['id']}.json" for d in docs} | {"index.json"}
    stale = [p for p in out_dir.glob("*.json") if p.name not in keep]
    for p in stale:
        p.unlink()
    return {
        "attivita": len(index),
        "dal_catalogo": skipped["catalogo"],
        "revisionate_escluse": skipped["revisionate"],
        "rimosse": len(stale),
        **dedup,
    }
