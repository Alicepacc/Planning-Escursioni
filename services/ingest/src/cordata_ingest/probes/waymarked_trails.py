"""Waymarked Trails: API pubblica per relazioni escursionistiche ordinate ed export GPX.

Uso previsto (SPEC §6): verifica incrociata dell'ordinamento delle relazioni OSM. Uso moderato,
mai dal client.
"""

from __future__ import annotations

from .base import ProbeContext, ProbeResult

PROBE_ID = "waymarked_trails"
API = "https://hiking.waymarkedtrails.org/api/v1"


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="Waymarked Trails (hiking)",
        format="JSON (elenchi, dettagli), GPX/KML/GeoJSON (geometria della relazione)",
        license="ODbL 1.0 (dati OpenStreetMap); rendering CC BY-SA 3.0",
        license_url="https://hiking.waymarkedtrails.org/help/legal",
        limits="Nessun limite numerico pubblicato: servizio volontario, uso moderato e in cache.",
        update_frequency="Aggiornamento continuo dai diff OSM (ritardo di minuti)",
    )

    # 1) elenco delle relazioni nella bbox del Lagorai
    listing = ctx.try_get(
        r,
        "elenco relazioni per bbox",
        f"{API}/list/by_area",
        params={"bbox": ctx.lagorai.mercator_bbox, "limit": 100},  # l'API vuole EPSG:3857
    )
    routes = listing.json().get("results", []) if listing else []
    r.check("la bbox Lagorai contiene relazioni escursionistiche", bool(routes), f"{len(routes)}")
    if listing:
        r.samples.append(ctx.save_sample(PROBE_ID, "list_by_area.json", listing.json()))
        r.examples.append(listing.url)

    # 2) i sentieri citati dalla fixture (il 326 è fuori dalla bbox campione: ricerca per nome)
    for ref in ("332", "360"):
        hit = next((x for x in routes if x.get("ref") == ref), None)
        detail = f"id {hit['id']} – {hit.get('name', '')}" if hit else "non presente nell'elenco"
        r.check(f"sentiero {ref} presente nell'area", hit is not None, detail)
    search = ctx.try_get(r, "ricerca testuale", f"{API}/list/search", params={"query": "326"})
    if search:
        hits = [x for x in search.json().get("results", []) if x.get("ref") == "326"]
        r.check("la ricerca per numero trova relazioni «326»", bool(hits), f"{len(hits)} risultati")
        r.notes.append(
            "I numeri dei sentieri non sono univoci (più relazioni «326» in regioni diverse): la "
            "ricerca va sempre filtrata per distanza dalla partenza (SPEC §7.4)."
        )

    # 3) dettaglio di una relazione: contiene già la geometria ordinata
    target = next((x for x in routes if x.get("ref") == "332"), routes[0] if routes else None)
    if target:
        rel_id = target["id"]
        details = ctx.try_get(r, "dettaglio relazione", f"{API}/details/relation/{rel_id}")
        if details:
            info = details.json()
            r.samples.append(ctx.save_sample(PROBE_ID, f"details_{rel_id}.json", info))
            tags = info.get("tags", {})
            route = info.get("route", {})
            ways = [w for part in route.get("main", []) for w in part.get("ways", [])]
            r.check(
                "il dettaglio contiene la geometria ordinata (route.main[].ways[])",
                bool(ways) and "geometry" in ways[0],
                f"{len(ways)} way ordinate, lunghezza {route.get('length')} m, "
                f"lineare={route.get('linear')}",
            )
            r.notes.append(
                f"Relazione {rel_id}: ref={info.get('ref')!r}, name={info.get('name')!r}, "
                f"cai_scale={tags.get('cai_scale')!r}, osmc:symbol={tags.get('osmc:symbol')!r}; "
                "geometrie in EPSG:3857 (anche la bbox di by_area va passata in EPSG:3857)"
            )
            r.examples.append(details.url)
        old = ctx.client.get(f"{API}/details/relation/{rel_id}/geometry/gpx", ttl=86400)
        r.notes.append(
            f"L'export GPX indicato nella SPEC (/details/relation/{{id}}/geometry/gpx) risponde "
            f"HTTP {old.status}: l'API attuale restituisce la geometria ordinata dentro il "
            "dettaglio JSON, che è ciò che serve per la verifica incrociata dell'ordinamento."
        )
    return r.finish()
