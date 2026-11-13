"""Waymarked Trails: API pubblica per relazioni escursionistiche ordinate ed export GPX.

Uso previsto (SPEC §6): verifica incrociata dell'ordinamento delle relazioni OSM. Uso moderato,
mai dal client.
"""

from __future__ import annotations

import re

from .base import STATUS_BLOCKED, STATUS_OK, STATUS_PARTIAL, ProbeContext, ProbeResult

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

    # 2) ricerca per ref: i sentieri citati dalla fixture
    for ref in ("332", "360", "326"):
        hit = next((x for x in routes if x.get("ref") in {ref, f"E{ref}", f"O{ref}"}), None)
        detail = f"id {hit['id']} – {hit.get('name', '')}" if hit else "non presente nell'elenco"
        r.check(f"sentiero {ref} presente nell'area", hit is not None, detail)

    # 3) dettaglio + GPX di una relazione
    target = next(
        (x for x in routes if x.get("ref") in {"332", "E332"}), routes[0] if routes else None
    )
    if target:
        rel_id = target["id"]
        details = ctx.try_get(r, "dettaglio relazione", f"{API}/details/relation/{rel_id}")
        if details:
            info = details.json()
            r.samples.append(ctx.save_sample(PROBE_ID, f"details_{rel_id}.json", info))
            tags = info.get("tags", {})
            r.notes.append(
                f"Relazione {rel_id}: ref={info.get('ref')!r}, name={info.get('name')!r}, "
                f"lunghezza mappata {info.get('mapped_length')} m, "
                f"cai_scale={tags.get('cai_scale')!r}, osmc:symbol={tags.get('osmc:symbol')!r}"
            )
        gpx = ctx.try_get(r, "export GPX", f"{API}/details/relation/{rel_id}/geometry/gpx")
        if gpx:
            points = len(re.findall(r"<trkpt ", gpx.text()))
            segments = len(re.findall(r"<trkseg>", gpx.text()))
            r.check(
                "il GPX contiene punti traccia", points > 0, f"{points} punti, {segments} segmenti"
            )
            r.samples.append(ctx.save_sample(PROBE_ID, f"relation_{rel_id}.gpx", gpx.content))
            r.examples.append(gpx.url)
            r.notes.append(
                "Il GPX non contiene quote (<ele>): l'altimetria va comunque calcolata dal DEM."
                if "<ele>" not in gpx.text()
                else "Il GPX contiene le quote (<ele>)."
            )

    r.reachable = any(c.ok for c in r.checks)
    failed = [c for c in r.checks if not c.ok]
    r.status = STATUS_BLOCKED if not r.reachable else (STATUS_PARTIAL if failed else STATUS_OK)
    return r
