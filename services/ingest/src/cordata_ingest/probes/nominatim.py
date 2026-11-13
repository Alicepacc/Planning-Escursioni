"""Nominatim pubblico: solo fallback di geocoding (il default è la ricerca locale sui POI OSM)."""

from __future__ import annotations

from .base import ProbeContext, ProbeResult

PROBE_ID = "nominatim"
API = "https://nominatim.openstreetmap.org"
POLICY = "https://operations.osmfoundation.org/policies/nominatim/"
# Il robots.txt di Nominatim esclude /search e /reverse per i crawler; l'uso dell'API è invece
# regolato dalla usage policy OSMF (1 richiesta/s, User-Agent identificativo), che rispettiamo.
API_TERMS = {"respect_robots": False}


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="Nominatim (istanza pubblica OSMF)",
        format="JSON / GeoJSON",
        license="ODbL 1.0 (dati OSM), attribuzione obbligatoria",
        license_url=POLICY,
        limits="Massimo assoluto 1 richiesta/secondo, User-Agent o Referer identificativo, "
        "niente autocomplete, risultati da mettere in cache; vietato l'uso massivo.",
        update_frequency="Replica OSM; frequenza non verificata",
    )
    policy = ctx.try_get(r, "usage policy", POLICY, ttl=30 * 86400)
    if policy:
        text = policy.text()
        r.check(
            "la policy indica il limite di 1 richiesta al secondo", "1 request per second" in text
        )
        r.check("la policy vieta l'autocomplete", "auto-complete" in text.lower())
    search = ctx.try_get(
        r,
        "ricerca «Malga Conseria»",
        f"{API}/search",
        params={"q": "Malga Conseria, Scurelle", "format": "jsonv2", "limit": 3},
        ttl=30 * 86400,
        **API_TERMS,
    )
    if search:
        hits = search.json()
        ok = bool(hits) and abs(float(hits[0]["lat"]) - 46.1704) < 0.01
        detail = (
            f"{hits[0]['display_name'][:90]} ({hits[0]['lat']}, {hits[0]['lon']})" if hits else "–"
        )
        r.check("il primo risultato è nel punto atteso", ok, detail)
        r.examples.append(search.url)
    reverse = ctx.try_get(
        r,
        "reverse su Cima Nassere",
        f"{API}/reverse",
        params={"lat": 46.150821, "lon": 11.550534, "format": "jsonv2", "zoom": 14},
        ttl=30 * 86400,
        **API_TERMS,
    )
    if reverse:
        r.notes.append(f"Reverse: {reverse.json().get('display_name', '')[:120]}")
    r.notes.append(
        "Uso previsto: mai dal client e mai per l'autocomplete. La ricerca dell'app usa un indice "
        "locale dei POI OSM; Nominatim pubblico resta un ripiego lato server con cache, oppure "
        "un'istanza self-hosted se serve geocoding di indirizzi."
    )
    return r.finish()
