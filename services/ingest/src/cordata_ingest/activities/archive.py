"""Archivio grezzo dei documenti selezionati (SPEC §7.2).

Scarica solo i PDF elencati in `config/pilot/candidates.yaml` (nessun download massivo prima
dell'approvazione del pilota), con il `PoliteClient`: robots.txt, User-Agent con contatto,
intervallo minimo per host, richieste condizionali (ETag / Last-Modified) e SHA-256.

L'archivio è **privato** (`data/activities/raw`, escluso da git): la risposta del CAI consente
di usare i contenuti delle sezioni solo come sintesi con link e data, quindi i PDF non vengono
mai ripubblicati. Il manifest (`manifest.json`) registra URL, hash, dimensione e data di fetch
di ogni documento, per la riproducibilità.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from ..config import data_dir, repo_root
from ..http import FetchError, PoliteClient, RobotsDisallowed

HOST_INTERVAL_S = 3.0


def raw_dir() -> Path:
    return data_dir() / "activities" / "raw"


def load_candidates(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or repo_root() / "config" / "pilot" / "candidates.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data["candidates"])


def raw_path(candidate: dict[str, Any], base: Path | None = None) -> Path:
    return (base or raw_dir()) / candidate["section"] / f"{candidate['id']}.pdf"


def archive(
    client: PoliteClient, candidates: list[dict[str, Any]], base: Path | None = None
) -> dict[str, Any]:
    """Scarica i candidati nell'archivio privato e aggiorna il manifest."""
    base = base or raw_dir()
    base.mkdir(parents=True, exist_ok=True)
    manifest_path = base / "manifest.json"
    manifest: dict[str, Any] = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    for c in candidates:
        client.host_intervals.setdefault(urlsplit(c["url"]).netloc, HOST_INTERVAL_S)
    for c in candidates:
        dest = raw_path(c, base)
        entry: dict[str, Any] = {
            "section": c["section"],
            "url": c["url"],
            "published": c.get("published"),
        }
        try:
            meta = client.download(c["url"], dest)
            entry.update(
                {
                    "path": str(dest.relative_to(base)),
                    "sha256": meta["sha256"],
                    "bytes": meta["bytes"],
                    "fetched_at": meta.get("fetched_at", time.time()),
                    "unchanged": meta.get("unchanged", False),
                }
            )
        except RobotsDisallowed:
            entry["error"] = "escluso dal robots.txt"
        except FetchError as exc:
            entry["error"] = exc.reason
        manifest[c["id"]] = entry
        manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), "utf-8")
    return manifest
