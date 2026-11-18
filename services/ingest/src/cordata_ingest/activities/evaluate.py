"""Harness del pilota: parser a regole contro la verità di riferimento (SPEC §7.6).

La verità di riferimento (`config/pilot/reviewed/*.yaml`) è la lettura dei PDF fatta a mano
nella sessione di lavoro, cioè la revisione "Claude Code" del flusso scelto dall'utente. Qui si
misura quanto il solo parser a regole ci si avvicina, campo per campo:

- precisione = corretti / estratti (quanto ci si può fidare di un valore estratto);
- copertura = corretti / presenti nella verità (quanto il parser trova da solo);
- carico di revisione = campi con confidenza < 0.8 o mancanti, da controllare a mano.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from ..config import data_dir, repo_root
from .extract import load_text
from .gazetteer import normalize
from .parse import calendar_entry, parse

FIELDS = [
    "titolo",
    "data",
    "difficolta",
    "tipo_percorso",
    "durata",
    "distanza_km",
    "salita_m",
    "discesa_m",
    "quota_max_m",
    "partenza_nome",
    "partenza_quota_m",
    "arrivo_nome",
    "ora_ritrovo",
    "mezzi",
    "quota_eur",
    "sentieri",
    "punti_chiave",
]
REVIEW_THRESHOLD = 0.8


def reviewed_dir() -> Path:
    return repo_root() / "config" / "pilot" / "reviewed"


def holdout_dir() -> Path:
    return repo_root() / "config" / "pilot" / "holdout"


def load_reviewed(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    out = {}
    for path in sorted((directory or reviewed_dir()).glob("*.yaml")):
        out[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return out


def truth_fields(gt: dict[str, Any]) -> dict[str, Any]:
    """Appiattisce la verità di riferimento sui campi del parser."""
    start = gt.get("partenza") or {}
    end = gt.get("arrivo") or {}
    data = gt.get("data")
    return {
        "titolo": gt.get("titolo"),
        "data": str(data) if data else None,
        "difficolta": gt.get("difficolta"),
        "tipo_percorso": gt.get("tipo_percorso"),
        "durata": gt.get("durata"),
        "distanza_km": gt.get("distanza_km"),
        "salita_m": gt.get("salita_m"),
        "discesa_m": gt.get("discesa_m"),
        "quota_max_m": gt.get("quota_max_m"),
        "partenza_nome": start.get("nome"),
        "partenza_quota_m": start.get("quota_m"),
        "arrivo_nome": end.get("nome"),
        "ora_ritrovo": gt.get("ora_ritrovo"),
        "mezzi": gt.get("mezzi"),
        "quota_eur": gt.get("quota_eur"),
        "sentieri": [str(s).upper() for s in gt.get("sentieri") or []],
        "punti_chiave": [p["nome"] for p in gt.get("punti_chiave") or []],
    }


def _tokens(text: str) -> set[str]:
    stop = {"di", "del", "della", "dei", "e", "al", "alla", "da", "la", "il", "lo", "a", "in"}
    return {w for w in normalize(text).split() if w not in stop}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0


def _same_place(a: str, b: str) -> bool:
    na, nb = normalize(a), normalize(b)
    return bool(na and nb) and (na in nb or nb in na or _jaccard(a, b) >= 0.5)


def _minutes(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def _list_f1(found: list[str], truth: list[str], same) -> float:
    if not found and not truth:
        return 1.0
    if not found or not truth:
        return 0.0
    hit_f = sum(1 for f in found if any(same(f, t) for t in truth))
    hit_t = sum(1 for t in truth if any(same(f, t) for f in found))
    p, r = hit_f / len(found), hit_t / len(truth)
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def compare(field: str, value: Any, truth: Any) -> tuple[bool, float | None]:
    """(corretto, punteggio) per un campo; punteggio = F1 per le liste."""
    if field == "sentieri":
        f1 = _list_f1(value or [], truth or [], lambda a, b: a == b)
        return set(value or []) == set(truth or []), f1
    if field == "punti_chiave":
        names = [p["nome"] if isinstance(p, dict) else p for p in value or []]
        f1 = _list_f1(names, truth or [], _same_place)
        return f1 >= 0.5, f1
    if value is None or truth is None:
        return value is None and truth is None, None
    if field == "titolo":
        # basta il nome principale (prima del « – »): i sottotitoli sono una scelta di stile
        main = normalize(str(truth).split(" – ")[0])
        return _jaccard(str(value), str(truth)) >= 0.5 or (
            bool(main) and main in normalize(str(value))
        ), None
    if field in {"partenza_nome", "arrivo_nome"}:
        return _same_place(str(value), str(truth)), None
    if field == "durata":
        return abs(_minutes(value) - _minutes(truth)) <= 5, None
    if field == "distanza_km":
        return abs(float(value) - float(truth)) <= max(0.1, 0.02 * float(truth)), None
    if field in {"salita_m", "discesa_m", "quota_max_m", "partenza_quota_m"}:
        return abs(float(value) - float(truth)) <= 5, None
    if field == "quota_eur":
        return abs(float(value) - float(truth)) < 0.01, None
    if field == "mezzi":
        return normalize(str(value)) == normalize(str(truth)), None
    return str(value) == str(truth), None


def _extracted(field: str, value: Any) -> bool:
    if field in {"sentieri", "punti_chiave"}:
        return bool(value)
    return value is not None


def _present(field: str, truth: Any) -> bool:
    if field in {"sentieri", "punti_chiave"}:
        return bool(truth)
    return truth is not None


def parse_activity(activity_id: str, gt: dict[str, Any]) -> dict[str, Any]:
    doc_id = gt.get("documento", activity_id)
    text = load_text(doc_id)
    pages = [(p["n"], p["text"]) for p in text["pages"]]
    if gt.get("documento"):  # voce di un calendario o libretto
        pages = calendar_entry(pages, str(gt["data"]))
        return parse(pages, entry_date=str(gt["data"]))
    # «2025/05/Locandina.pdf»: nome del file e cartella di caricamento (anno delle date senza anno)
    return parse(pages, hint="/".join(text["url"].rsplit("/", 3)[-3:]))


def evaluate_all(out: Path | None = None, directory: Path | None = None) -> dict[str, Any]:
    """Valuta il parser sulle annotazioni di `directory` (default: le 20 del pilota)."""
    out = out or data_dir() / "activities" / ("parsed" if directory is None else "parsed-holdout")
    out.mkdir(parents=True, exist_ok=True)
    per_activity: dict[str, Any] = {}
    stats = {f: {"estratti": 0, "corretti": 0, "presenti": 0, "da_rivedere": 0} for f in FIELDS}
    f1s: dict[str, list[float]] = {"sentieri": [], "punti_chiave": []}
    for activity_id, gt in load_reviewed(directory).items():
        parsed = parse_activity(activity_id, gt)
        truth = truth_fields(gt)
        rows = {}
        for field in gt.get("campi_valutati", FIELDS):
            got = parsed[field]
            ok, score = compare(field, got["value"], truth[field])
            ext, pres = _extracted(field, got["value"]), _present(field, truth[field])
            review = (not ext and pres) or (ext and got["confidence"] < REVIEW_THRESHOLD)
            s = stats[field]
            s["estratti"] += ext
            s["presenti"] += pres
            s["corretti"] += ok and ext
            s["da_rivedere"] += review
            if score is not None:
                f1s[field].append(score)
            rows[field] = {**got, "verita": truth[field], "corretto": ok, "f1": score}
        per_activity[activity_id] = rows
        (out / f"{activity_id}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    for field, s in stats.items():
        s["precisione"] = round(s["corretti"] / s["estratti"], 3) if s["estratti"] else None
        s["copertura"] = round(s["corretti"] / s["presenti"], 3) if s["presenti"] else None
        if f1s.get(field):
            s["f1_medio"] = round(sum(f1s[field]) / len(f1s[field]), 3)
    return {"per_campo": stats, "per_attivita": per_activity}
