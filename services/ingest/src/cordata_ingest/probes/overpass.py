"""Overpass API: solo per sviluppo e debug, mai dai client (SPEC §3 e §6)."""

from __future__ import annotations

from ..http import FetchError
from .base import STATUS_PARTIAL, ProbeContext, ProbeResult

PROBE_ID = "overpass"
MAIN = "https://overpass-api.de/api"
MIRROR = "https://maps.mail.ru/osm/tools/overpass/api"
POLICY = "https://dev.overpass-api.de/overpass-doc/en/preface/commons.html"


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="Overpass API",
        format="JSON / XML (Overpass QL)",
        license="ODbL 1.0 (dati OpenStreetMap)",
        license_url=POLICY,
        update_frequency="Replica OSM; ritardo non verificato",
    )
    try:
        status = ctx.client.get(f"{MAIN}/status", ttl=None)
        r.check("istanza principale overpass-api.de", status.ok, f"HTTP {status.status}")
    except FetchError as exc:
        r.check("istanza principale overpass-api.de", False, f"errore di rete: {exc.reason}")
        r.notes.append(
            "overpass-api.de chiude la connessione da questo ambiente cloud (reset durante il "
            "TLS, anche per robots.txt): da verificare da una rete normale."
        )
    except Exception as exc:  # robots.txt irraggiungibile → RobotsDisallowed
        r.check(
            "istanza principale overpass-api.de", False, f"{type(exc).__name__}: irraggiungibile"
        )
        r.notes.append(
            "overpass-api.de chiude la connessione da questo ambiente cloud (reset durante il "
            "TLS, anche per robots.txt): da verificare da una rete normale."
        )

    query = f"[out:json][timeout:25];relation[route=hiking]({ctx.lagorai.overpass_bbox});out tags;"
    res = ctx.try_get(
        r,
        "query di prova su un'istanza alternativa",
        f"{MIRROR}/interpreter",
        params={"data": query},
    )
    if res:
        elements = res.json().get("elements", [])
        refs = sorted({e["tags"].get("ref", "") for e in elements if e["tags"].get("ref")})
        r.check("relazioni escursionistiche nella bbox Lagorai", bool(elements), f"{len(elements)}")
        r.check(
            "i sentieri 332 e 360 sono presenti", {"332", "360"} <= set(refs), ", ".join(refs)[:150]
        )
        r.samples.append(ctx.save_sample(PROBE_ID, "lagorai_hiking_relations.json", res.json()))
        r.examples.append(res.url)
    policy = ctx.try_get(r, "pagina con le regole d'uso", POLICY, ttl=30 * 86400)
    if policy:
        text = " ".join(policy.text().split())
        quote = "a maximum of about 10000 requests per day"
        r.check("la documentazione indica la soglia d'uso", quote in text)
        r.limits = (
            "Istanza principale: «users are expected to send a maximum of about 10000 requests "
            "per day and keep their download volume below about 1 GB per day»; oltre il limite "
            "risponde 429. Le istanze alternative hanno regole proprie."
        )
    r.notes.append(
        "In produzione Overpass non serve: i dati arrivano dall'estratto .osm.pbf locale. Resta "
        "uno strumento da sviluppatore, da usare a mano e con parsimonia."
    )
    return r.finish(STATUS_PARTIAL if r.reachable else None)
