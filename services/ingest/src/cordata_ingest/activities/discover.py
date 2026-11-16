"""Scoperta dei documenti delle sezioni (SPEC §7.1): elenco dei PDF via REST di WordPress.

Scarica solo i **metadati** (titolo, data, URL), mai i PDF: il download avviene dopo, per i
soli documenti selezionati (`archive.py`). L'elenco finisce in `data/activities/index.json`.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from ..config import data_dir, repo_root
from ..http import PoliteClient
from .classify import classify_name

WP_FIELDS = "id,date,modified,title,source_url,mime_type,link"
HOST_INTERVAL_S = 2.0


@dataclass
class DocumentRef:
    section: str
    wp_id: int
    title: str
    date: str
    modified: str
    url: str
    page: str
    guess: str  # classificazione preliminare dal solo nome (vedi classify.py)


def sections(pilot_only: bool = True) -> list[dict[str, Any]]:
    config = yaml.safe_load(
        (repo_root() / "config" / "sources" / "cai_sections.yaml").read_text(encoding="utf-8")
    )
    out = []
    for s in config["sections"]:
        if pilot_only and not s.get("pilot"):
            continue
        if s.get("site_type", "").startswith("wordpress") and s.get("base_url"):
            out.append(s)
    return out


def list_pdfs(
    client: PoliteClient, section: dict[str, Any], totals: dict[str, int] | None = None
) -> list[DocumentRef]:
    """PDF pubblici della sezione. In `totals` il numero dichiarato da `X-WP-Total`, che può
    essere maggiore: WordPress conta anche gli allegati di contenuti non pubblici."""
    base = section["base_url"].rstrip("/")
    refs: list[DocumentRef] = []
    page = 1
    while True:
        res = client.get(
            f"{base}/wp-json/wp/v2/media",
            params={
                "mime_type": "application/pdf",
                "per_page": 100,
                "page": page,
                "_fields": WP_FIELDS,
            },
            ttl=6 * 3600,
        ).raise_for_status()
        for item in res.json():
            title = item.get("title", {}).get("rendered", "")
            url = item.get("source_url", "")
            refs.append(
                DocumentRef(
                    section=section["slug"],
                    wp_id=int(item["id"]),
                    title=title,
                    date=item.get("date", ""),
                    modified=item.get("modified", ""),
                    url=url,
                    page=item.get("link", ""),
                    guess=classify_name(f"{title} {url.rsplit('/', 1)[-1]}"),
                )
            )
        if totals is not None:
            totals[section["slug"]] = int(res.header("x-wp-total", "0") or 0)
        total_pages = int(res.header("x-wp-totalpages", "1") or 1)
        if page >= total_pages:
            break
        page += 1
    return refs


def discover(client: PoliteClient, out: Path | None = None, pilot_only: bool = True) -> dict:
    out = out or data_dir() / "activities" / "index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    for s in sections(pilot_only):
        host = s["base_url"].split("/")[2]
        client.host_intervals.setdefault(host, HOST_INTERVAL_S)
    docs: list[DocumentRef] = []
    per_section: dict[str, int] = {}
    declared: dict[str, int] = {}
    for s in sections(pilot_only):
        found = list_pdfs(client, s, declared)
        per_section[s["slug"]] = len(found)
        docs.extend(found)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "per_section": per_section,
        "declared_total": declared,  # X-WP-Total: include allegati non pubblici
        "documents": [asdict(d) for d in docs],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return payload
