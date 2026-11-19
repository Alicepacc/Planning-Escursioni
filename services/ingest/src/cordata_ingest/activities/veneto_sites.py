"""Siti delle sezioni CAI del Veneto (ADR 0013).

La directory delle sezioni del Gruppo regionale risponde solo alle richieste della propria pagina
(«Origin header mancante»): non la si aggira. L'elenco dei nomi è quindi compilato a mano e per
ogni sezione si provano pochi indirizzi plausibili, come per i siti SAT:

- `organizzazione.cai.it/sez-<nome>/` (il multisite del CAI, es. `sez-vicenza`);
- `www.cai<nome>.it` (siti propri, es. caimestre.it, caiverona.it).

Per ogni indirizzo esistente: robots.txt e **una** richiesta alla home con il `PoliteClient`;
per i siti WordPress, **una** richiesta all'API dei media per contare i PDF pubblici. Nessun
download di documenti: l'esito va rivisto a mano prima di registrare le sezioni in
`config/sources/cai_sections.yaml`.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from ..config import data_dir
from ..http import FetchError, PoliteClient, RobotsDisallowed
from .sat_sites import PAUSE_S, _title, count_pdfs

MULTISITE = "https://organizzazione.cai.it"

# sezioni CAI del Veneto (nomi delle sedi; elenco compilato a mano, può essere incompleto)
SECTIONS = [
    # Belluno
    "agordo", "alpago", "auronzo", "belluno", "calalzo", "cortina", "domegge", "feltre",
    "livinallongo", "longarone", "lorenzago", "pieve-di-cadore", "ponte-nelle-alpi",
    "san-vito-di-cadore", "val-comelico", "val-di-zoldo", "valzoldana", "caprile",
    # Treviso
    "treviso", "conegliano", "vittorio-veneto", "castelfranco-veneto", "montebelluna",
    "oderzo", "pieve-di-soligo", "valdobbiadene", "asolo",
    # Vicenza
    "vicenza", "schio", "thiene", "valdagno", "arzignano", "bassano-del-grappa", "bassano",
    "asiago", "marostica", "recoaro-terme", "malo", "montecchio-maggiore", "lonigo",
    "noventa-vicentina",
    # Padova
    "padova", "camposampiero", "cittadella", "este", "montagnana", "piove-di-sacco",
    # Venezia
    "venezia", "mestre", "dolo", "mirano", "noale", "san-dona-di-piave", "portogruaro",
    "chioggia", "spinea",
    # Verona
    "verona", "bardolino", "legnago", "san-bonifacio",
    # Rovigo
    "rovigo", "adria",
]  # fmt: skip


def candidate_urls(slug: str) -> list[str]:
    compact = slug.replace("-", "")
    return [f"{MULTISITE}/sez-{slug}/", f"https://www.cai{compact}.it/"]


def probe(client: PoliteClient, url: str, slug: str) -> dict[str, Any] | None:
    """Esito per un indirizzo che risponde con una pagina della sezione, None altrimenti."""
    try:
        res = client.get(url, ttl=7 * 24 * 3600)
    except RobotsDisallowed:
        origin = "/".join(url.split("/", 3)[:3])
        if client._robots.get(origin) is None and origin in client._robots:
            return None  # robots.txt irraggiungibile: l'host non esiste o non risponde
        return {"url": url, "status": "robots.txt vieta l'accesso"}
    except FetchError:
        return None
    if res.status != 200:
        return None
    if url.startswith(MULTISITE) and f"/sez-{slug}" not in str(res.url):
        return None  # il multisite rimanda alla home generale: la sezione non c'è
    html = res.text()
    words = [w for w in slug.split("-") if len(w) > 2]
    low = html.lower()
    return {
        "url": str(res.url),
        "title": _title(html),
        "wordpress": "wp-content" in html or "api.w.org" in html,
        "mentions_cai": bool(re.search(r"\bCAI\b|Club Alpino Italiano", html)),
        "name_match": all(w in low for w in words) if words else False,
    }


def find_sites(client: PoliteClient, out: Path | None = None) -> dict[str, Any]:
    out = out or data_dir() / "activities" / "cai_veneto_sites.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    client.host_intervals.setdefault("organizzazione.cai.it", 2.0)
    found: dict[str, Any] = {}
    tried = 0
    for slug in SECTIONS:
        for url in candidate_urls(slug):
            tried += 1
            result = probe(client, url, slug)
            time.sleep(PAUSE_S)
            if result and result.get("mentions_cai") and result.get("name_match"):
                if result["wordpress"]:
                    result["pdf_pubblici"] = count_pdfs(client, result["url"].rstrip("/"))
                found.setdefault(slug, []).append(result)
            elif result:
                found.setdefault(f"{slug} (da verificare)", []).append(result)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "indirizzi_provati": tried,
        "sezioni": found,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return payload
