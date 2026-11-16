"""Esecuzione del pilota (SPEC §7.6): le 20 attività riviste più la fixture #0 (fuori conteggio)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from ..config import data_dir, repo_root
from ..db import connect
from ..geo.elevation import TerrariumDem
from ..http import PoliteClient
from .evaluate import load_reviewed
from .reconstruct import reconstruct, result_dict

FIXTURE_ID = "fixture-0-val-d-inferno"


def fixture_activity() -> dict[str, Any]:
    """La fixture golden del §2 nello stesso formato delle attività riviste."""
    g = json.loads((repo_root() / "fixtures" / "golden" / "val-d-inferno.json").read_text("utf-8"))
    points = []
    for raw in g["punti_chiave_in_ordine"]:
        m = re.match(r"^(.*?)\s*\((\d{3,4})\)\s*$", raw)
        points.append({"nome": m.group(1), "quota_m": int(m.group(2))} if m else {"nome": raw})
    return {
        "sezione": ", ".join(g.get("organizzatori", [])),
        "titolo": g["titolo"],
        "data": g["data"],
        "zona": g.get("gruppo_montuoso"),
        "tipo_percorso": g["tipo_percorso"],
        "difficolta": g["difficolta_cai"],
        "durata": g["durata_dichiarata"],
        "distanza_km": g["distanza_km"],
        "salita_m": g["dislivello_salita_m"],
        "discesa_m": g["dislivello_discesa_m"],
        "quota_max_m": g["quota_max_m"],
        "partenza": {"nome": g["partenza"]["nome"], "quota_m": g["partenza"]["quota_m"]},
        "sentieri": g["sentieri_citati"],
        "punti_chiave": points,
    }


def activities() -> dict[str, dict[str, Any]]:
    out = {FIXTURE_ID: fixture_activity()}
    out.update(load_reviewed())
    return out


def tracks_dir() -> Path:
    return data_dir() / "activities" / "tracks"


def run_reconstruction(only: list[str] | None = None) -> list[dict[str, Any]]:
    out = tracks_dir()
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    with PoliteClient(timeout=60) as client, connect() as conn:
        dem = TerrariumDem(data_dir() / "dem" / "mapterhorn", client, zoom=12)
        for activity_id, activity in activities().items():
            if only and activity_id not in only:
                continue
            t0 = time.perf_counter()
            res = result_dict(reconstruct(conn, dem, activity_id, activity))
            res["seconds"] = round(time.perf_counter() - t0, 1)
            (out / f"{activity_id}.json").write_text(
                json.dumps(res, ensure_ascii=False), encoding="utf-8"
            )
            summary.append({k: res[k] for k in ("id", "status", "reasons", "checks", "seconds")})
    return summary
