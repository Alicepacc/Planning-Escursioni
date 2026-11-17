"""Siti delle sezioni SAT (decisione dell'utente al checkpoint della Fase 2).

Il sito centrale (`sat.tn.it`) elenca le sezioni ma non collega i loro siti, e le locandine che
ospita si fermano al 2023. Qui si cercano i siti delle sezioni una per una, con pochi domini
plausibili per sezione (`sat<nome>.it`, come satborgo.it e sattrento.it citati nelle locandine):

- un dominio inesistente costa una connessione rifiutata (nessun carico su server altrui);
- per un host esistente: robots.txt e **una** richiesta alla home, con il `PoliteClient`;
- per i siti WordPress, **una** richiesta all'API dei media per contare i PDF pubblici.

Nessun download di documenti: l'esito va rivisto a mano prima di aggiungere le sezioni a
`config/sources/cai_sections.yaml`.
"""

from __future__ import annotations

import json
import re
import time
from html import unescape
from pathlib import Path
from typing import Any

from ..config import data_dir
from ..http import FetchError, PoliteClient, RobotsDisallowed

SAT_SECTIONS_URL = "https://www.sat.tn.it/sezioni/"
NOT_HIKING = {"coro-della-sat"}
PAUSE_S = 0.5  # pausa tra host diversi, per non creare raffiche attraverso il proxy


def section_slugs(client: PoliteClient) -> list[str]:
    html = client.get(SAT_SECTIONS_URL, ttl=7 * 24 * 3600).raise_for_status().text()
    slugs = sorted(set(re.findall(r'href="/sezioni/([a-z0-9-]+)/"', html)))
    return [s for s in slugs if s not in NOT_HIKING]


def candidate_hosts(slug: str) -> list[str]:
    base = slug.replace("-", "")
    first = slug.split("-")[0]
    hosts = [f"www.sat{base}.it", f"www.sat{first}.it", f"www.sat-{slug}.it"]
    return list(dict.fromkeys(hosts))


def _title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", unescape(m.group(1))).strip()[:120] if m else ""


def probe_host(client: PoliteClient, host: str, slug: str) -> dict[str, Any] | None:
    """Esito per un host esistente, None se non risponde."""
    url = f"https://{host}/"
    try:
        res = client.get(url, ttl=7 * 24 * 3600)
    except RobotsDisallowed:
        origin = f"https://{host}"
        if client._robots.get(origin) is None and origin in client._robots:
            return None  # robots.txt irraggiungibile: l'host non esiste o non risponde
        return {"host": host, "status": "robots.txt vieta l'accesso", "url": url}
    except FetchError:
        return None
    html = res.text()
    words = [w for w in slug.split("-") if len(w) > 2]
    name_hits = sum(1 for w in words if w in html.lower())
    return {
        "host": host,
        "url": str(res.url),
        "status": res.status,
        "title": _title(html),
        "wordpress": "wp-content" in html or "api.w.org" in html,
        "mentions_sat": bool(re.search(r"\bSAT\b|Società degli Alpinisti Tridentini", html)),
        "name_match": name_hits == len(words) if words else False,
    }


def count_pdfs(client: PoliteClient, base_url: str) -> int | None:
    try:
        res = client.get(
            f"{base_url.rstrip('/')}/wp-json/wp/v2/media",
            params={"mime_type": "application/pdf", "per_page": 1, "_fields": "id"},
            ttl=24 * 3600,
        )
    except (RobotsDisallowed, FetchError):
        return None
    if not res.ok:
        return None
    return int(res.header("x-wp-total", "0") or 0)


def find_sites(client: PoliteClient, out: Path | None = None) -> dict[str, Any]:
    out = out or data_dir() / "activities" / "sat_sites.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    found: dict[str, Any] = {}
    tried = 0
    for slug in section_slugs(client):
        for host in candidate_hosts(slug):
            tried += 1
            result = probe_host(client, host, slug)
            time.sleep(PAUSE_S)
            if result and result.get("status") == 200 and result["mentions_sat"]:
                if result["wordpress"]:
                    base = result["url"].split("/", 3)[:3]
                    result["pdf_pubblici"] = count_pdfs(client, "/".join(base))
                found[slug] = result
                break
            if result:
                found.setdefault(f"{slug} (da verificare)", result)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "domini_provati": tried,
        "sezioni": found,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return payload
