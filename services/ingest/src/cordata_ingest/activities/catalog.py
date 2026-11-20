"""Catalogo a lotti (ADR 0015): dalle locandine archiviate alle escursioni pubblicabili.

Per ogni documento non ancora rivisto a mano:

1. campi della locandina con il parser a regole (senza revisione);
2. tipo di attività: si tengono solo le escursioni (niente bici, corsi, serate, programmi
   annuali in questo primo passo);
3. punti del percorso dal parser o, se ne trova meno di tre, dal testo con il gazetteer;
4. ricostruzione della traccia e confronto con la locandina;
5. area del catalogo (Trentino-Alto Adige, Dolomiti e Prealpi venete) decisa dalla traccia;
6. punteggio di affidabilità: da 80 in su l'escursione entra nell'app.

Tutto resta nell'archivio privato (`data/activities/catalogo/`): per ogni documento un record
con l'esito e, se ricostruita, la traccia. La build legge solo le schede pubblicabili.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import yaml

from ..config import data_dir, repo_root
from ..geo.area import in_area
from .itinerary import extract_points
from .parse import parse
from .reliability import THRESHOLD, score

# scale di difficoltà della mountain bike (cicloescursionismo CAI) e dell'alpinismo
BIKE_GRADE = re.compile(r"^(TC|MC|BC|OC|EC)\b", re.I)
ALPINE_GRADE = re.compile(r"^(F|PD|AD|D|TD|ED)[+-]?$", re.I)
BIKE_WORDS = re.compile(
    r"(?i)\b(ciclo-?escursion\w*|mtb|mountain bike|e-?bike|bicicletta|in bici)\b"
)
NOT_HIKE_WORDS = re.compile(
    r"(?i)\b(corso di|serata|conferenza|proiezione|assemblea|cena sociale|tesseramento|"
    r"convocazione|bilancio|verbale|modulo di iscrizione|informativa privacy|regolamento)\b"
)
DATE_LIKE = re.compile(
    r"(?i)\b(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|"
    r"ottobre|novembre|dicembre)\b"
)
HIKE_GRADES = {"T", "E", "EE", "EEA", "EAI"}


def catalog_dir() -> Path:
    return data_dir() / "activities" / "catalogo"


def section_names() -> dict[str, str]:
    path = repo_root() / "config" / "sources" / "cai_sections.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = {}
    for s in data["sections"]:
        name = re.sub(r"^CAI Sezione di ", "CAI ", s["name"])
        out[s["slug"]] = re.sub(r"^SAT Sezione di ", "SAT ", name)
    return out


def activity_kind(values: dict[str, Any], text: str) -> tuple[str, str | None]:
    """«escursione» o il motivo per cui il documento resta fuori dal catalogo."""
    grade = (values.get("difficolta") or "").strip()
    if BIKE_GRADE.match(grade) or (BIKE_WORDS.search(text) and grade not in HIKE_GRADES):
        return "bici", "cicloescursionismo"
    if ALPINE_GRADE.match(grade):
        return "alpinismo", f"scala alpinistica {grade}"
    dates = {m.group(0).lower() for m in DATE_LIKE.finditer(text)}
    if len(dates) >= 6:
        return "programma", f"{len(dates)} date: programma o libretto"
    numbers = [values.get(k) for k in ("distanza_km", "salita_m", "durata", "quota_max_m")]
    if NOT_HIKE_WORDS.search(text) and not any(numbers) and grade not in HIKE_GRADES:
        return "altro", "corso, serata o documento amministrativo"
    base = grade.split("-")[0].split("/")[0].upper()
    if grade and base not in HIKE_GRADES and not grade.upper().startswith("EAI"):
        return "altro", f"difficoltà {grade} fuori dalla scala escursionistica"
    if not any(numbers) and not grade:
        return "altro", "nessun dato di percorso"
    return "escursione", None


def activity_from(values: dict[str, Any], text: str, home: str | None) -> dict[str, Any]:
    """Campi per la ricostruzione, come quelli rivisti a mano (`config/activities/reviewed`)."""
    points = [
        {"nome": x["nome"], "quota_m": x.get("quota_m")} for x in values.get("punti_chiave") or []
    ]
    if values.get("partenza_nome"):
        points.insert(0, {"nome": values["partenza_nome"], "quota_m": values["partenza_quota_m"]})
    loop = values.get("tipo_percorso") == "anello"
    from_text = False
    if len({x["nome"] for x in points}) < 3:
        extra = extract_points(text, home=home, title=values.get("titolo"))
        if len(extra["punti"]) >= 2:
            points, from_text = extra["punti"], True
            loop = loop or (extra["anello"] and values.get("tipo_percorso") is None)
    if loop and points:
        points.append(dict(points[0]))
    elif values.get("arrivo_nome") and values.get("tipo_percorso") == "traversata":
        points.append({"nome": values["arrivo_nome"]})
    return {
        "titolo": values.get("titolo"),
        "data": values.get("data"),
        "difficolta": values.get("difficolta"),
        "tipo_percorso": values.get("tipo_percorso") or ("anello" if loop else None),
        "durata": values.get("durata"),
        "distanza_km": values.get("distanza_km"),
        "salita_m": values.get("salita_m"),
        "discesa_m": values.get("discesa_m"),
        "quota_max_m": values.get("quota_max_m"),
        "partenza": {"nome": points[0]["nome"] if points else None, "quota_m": None},
        "ora_ritrovo": values.get("ora_ritrovo"),
        "mezzi": values.get("mezzi"),
        "quota_eur": values.get("quota_eur"),
        "sentieri": values.get("sentieri") or [],
        "punti_chiave": points,
        "punti_dal_testo": from_text,
    }


def process(
    conn: Any, dem: Any, doc_id: str, entry: dict[str, Any], names: dict[str, str]
) -> dict[str, Any]:
    from .reconstruct import reconstruct, result_dict

    text_doc = json.loads(
        (data_dir() / "activities" / "text" / f"{doc_id}.json").read_text(encoding="utf-8")
    )
    pages = [(p["n"], p["text"]) for p in text_doc["pages"]]
    text = "\n".join(t for _, t in pages)
    hint = "/".join(text_doc["url"].rsplit("/", 3)[-3:])
    fields = parse(pages, hint=hint)
    values = {k: v["value"] for k, v in fields.items()}
    section = names.get(entry["section"], entry["section"])
    record: dict[str, Any] = {
        "id": doc_id,
        "sezione": section,
        "url": entry["url"],
        "pubblicato": entry.get("published"),
        "campi": fields,
    }
    kind, why = activity_kind(values, text)
    record["tipo"] = kind
    if kind != "escursione":
        record["esito"] = f"escluso: {why}"
        return record
    home = re.sub(r"^(CAI|SAT)\s+", "", section).split(" - ")[0].strip() or None
    activity = activity_from(values, text, home)
    activity["sezione"] = section
    record["attivita"] = activity
    t0 = time.perf_counter()
    track = result_dict(reconstruct(conn, dem, doc_id, activity))
    track["seconds"] = round(time.perf_counter() - t0, 1)
    record["ricostruzione"] = {k: track[k] for k in ("status", "reasons", "checks")}
    inside = bool(track.get("coords")) and in_area(track["coords"])
    record["area"] = inside
    s = score(track, fields)
    record["affidabilita"] = s
    if track.get("coords"):
        tracks = catalog_dir() / "tracce"
        tracks.mkdir(parents=True, exist_ok=True)
        (tracks / f"{doc_id}.json").write_text(json.dumps(track, ensure_ascii=False), "utf-8")
    if not inside and track.get("coords"):
        record["esito"] = "fuori area"
    elif s["punteggio"] >= THRESHOLD:
        record["esito"] = "pubblicabile"
    else:
        record["esito"] = f"sotto soglia ({s['punteggio']})"
    return record


def run(limit: int | None = None, only_new: bool = True) -> dict[str, int]:
    """Elabora i documenti archiviati con il testo estratto, saltando quelli già elaborati e
    quelli rivisti a mano. Restituisce il conteggio degli esiti."""
    from ..db import connect
    from ..geo.elevation import TerrariumDem
    from ..http import PoliteClient
    from .evaluate import load_reviewed
    from .pilot import blocks_dir

    out = catalog_dir() / "record"
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((data_dir() / "activities" / "raw" / "manifest.json").read_text("utf-8"))
    reviewed = set(load_reviewed()) | set(load_reviewed(blocks_dir()))
    texts = data_dir() / "activities" / "text"
    names = section_names()
    counts: dict[str, int] = {}
    done = 0
    with PoliteClient(timeout=60) as client, connect() as conn:
        dem = TerrariumDem(data_dir() / "dem" / "mapterhorn", client, zoom=12)
        for doc_id, entry in manifest.items():
            if "path" not in entry or doc_id in reviewed:
                continue
            if not (texts / f"{doc_id}.json").exists():
                continue
            target = out / f"{doc_id}.json"
            if only_new and target.exists():
                continue
            try:
                record = process(conn, dem, doc_id, entry, names)
            except Exception as exc:  # un documento storto non ferma il lotto
                conn.rollback()
                record = {"id": doc_id, "esito": f"errore: {type(exc).__name__}: {exc}"[:300]}
            target.write_text(json.dumps(record, ensure_ascii=False, indent=1), "utf-8")
            key = record["esito"].split(":")[0].split(" (")[0]
            counts[key] = counts.get(key, 0) + 1
            done += 1
            if limit and done >= limit:
                break
    return counts
