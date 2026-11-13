"""OSM2CAI – catasto dei sentieri CAI (SOSEC). Fonte primaria per i sentieri (SPEC §6.1)."""

from __future__ import annotations

from ..config import areas
from .base import ProbeContext, ProbeResult

PROBE_ID = "osm2cai"
BASE = "https://osm2cai.cai.it"
API = f"{BASE}/api/v2"
FIXTURE_REFS = ("332", "360", "326")


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="OSM2CAI – catasto sentieri CAI (SOSEC)",
        format="JSON (indici {id: updated_at}), GeoJSON (dettaglio, MultiLineString), GPX",
        license="Uso consentito con citazione dei crediti CAI (conferma scritta all'utente, §3); "
        "geometrie derivate da OpenStreetMap (ODbL)",
        license_url=f"{BASE}/api/documentation",
        update_frequency="Sincronizzazione con OSM; indici con updated_at per l'incrementale",
    )
    bbox = ctx.lagorai.bbox_str

    docs = ctx.try_get(r, "documentazione OpenAPI", f"{BASE}/docs?api-docs.json")
    if docs:
        spec = docs.json()
        paths = spec.get("paths", {})
        r.notes.append(
            f"OpenAPI «{spec['info']['title']}» {spec['info']['version']}: {len(paths)} path"
        )
        sda_doc = next(
            (
                p["description"]
                for p in paths["/api/v2/hiking-routes/region/{region_code}/{sda}"]["get"][
                    "parameters"
                ]
                if p["name"] == "sda"
            ),
            "",
        )
        r.check("legenda sda nella documentazione", "SDA=4" in sda_doc, sda_doc)
        r.check(
            "endpoint di dettaglio itinerario documentato",
            any(p.startswith("/api/v2/itinerary/{") for p in paths),
            "la documentazione elenca solo /api/v2/itinerary/list",
        )

    # indici per bbox: un oggetto {id: updated_at} per ciascun valore di sda
    counts: dict[int, int] = {}
    index4: dict[str, str] = {}
    for sda in (4, 3):
        idx = ctx.try_get(
            r, f"indice bbox Lagorai sda={sda}", f"{API}/hiking-routes/bb/{bbox}/{sda}"
        )
        if idx:
            data = idx.json()
            counts[sda] = len(data)
            if sda == 4:
                index4 = data
                limit = idx.header("x-ratelimit-limit")
                r.limits = (
                    f"Header X-RateLimit-Limit: {limit} (richieste al minuto, limite standard "
                    "Laravel); robots.txt senza divieti; nessuna chiave richiesta"
                )
                r.samples.append(ctx.save_sample(PROBE_ID, "index_lagorai_sda4.json", data))
    r.check("la bbox Lagorai contiene sentieri validati (sda 4)", counts.get(4, 0) > 0, str(counts))

    # dettagli: cerca i sentieri della fixture tra quelli validati attorno alla Val d'Inferno
    # (la bbox campione "Lagorai" della SPEC si ferma a 46,16°N e taglia fuori il 326)
    fixture_bbox = areas()["val_inferno"].bbox_str
    fx = ctx.try_get(r, "indice bbox fixture sda=4", f"{API}/hiking-routes/bb/{fixture_bbox}/4")
    found: dict[str, dict] = {}
    candidates = dict(index4) | (fx.json() if fx else {})
    r.notes.append(
        "L'indice per bbox restituisce solo i sentieri interamente contenuti nel riquadro: il 332 "
        "(11,9 km) compare nella bbox Lagorai ma non in quella stretta della fixture, il 326 il "
        "contrario. Per la sincronizzazione usare gli indici per regione o una bbox con margine."
    )
    for rid in candidates:
        if len(found) == len(FIXTURE_REFS):
            break
        res = ctx.client.get(f"{API}/hiking-route/{rid}", ttl=7 * 86400)
        if not res.ok:
            r.check(f"dettaglio sentiero {rid}", False, f"HTTP {res.status}", res.url)
            continue
        props = res.json()["properties"]
        if props.get("ref") in FIXTURE_REFS:
            found[props["ref"]] = props
            r.samples.append(ctx.save_sample(PROBE_ID, f"hiking_route_{rid}.geojson", res.json()))
    for ref in FIXTURE_REFS:
        p = found.get(ref)
        detail = (
            f"id {p['id']}, relazione OSM {p['relation_id']}, cai_scale {p['cai_scale']}, "
            f"{p['distance']} km, +{p['ascent']}/-{p['descent']} m, "
            f"{p['duration_forward']}/{p['duration_backward']} min, sda {p['sda']}, "
            f"validato il {p['validation_date']}, percorribilità: {p['issues_status']}"
            if p
            else "non trovato tra i sentieri sda 4 della bbox della fixture"
        )
        r.check(f"sentiero {ref} della fixture", p is not None, detail)
    if found:
        sample = next(iter(found.values()))
        r.notes.append("Campi del dettaglio: " + ", ".join(sorted(sample)))

    # dimensione dell'area pilota (solo indici)
    for sda in (4, 3):
        idx = ctx.try_get(
            r, f"indice bbox pilota sda={sda}", f"{API}/hiking-routes/bb/{ctx.pilot.bbox_str}/{sda}"
        )
        if idx:
            r.notes.append(
                f"Area pilota {ctx.pilot.bbox_str}: {len(idx.json())} sentieri con sda={sda}"
            )

    # codici regione (convenzione CAI): verificati leggendo il comune di un sentiero campione
    for code in ("C", "B"):
        idx = ctx.try_get(r, f"indice regione {code} sda=4", f"{API}/hiking-routes/region/{code}/4")
        if idx and idx.json():
            first = next(iter(idx.json()))
            one = ctx.client.get(f"{API}/hiking-route/{first}", ttl=7 * 86400)
            where = one.json()["properties"].get("taxonomy_where") if one.ok else None
            towns = ", ".join(v.get("it", "?") for v in (where or {}).values())[:80]
            r.notes.append(
                f"Regione CAI «{code}»: {len(idx.json())} sentieri sda 4; es. {first} → {towns}"
            )

    # itinerari, POI, settori
    itin = ctx.try_get(r, "elenco itinerari", f"{API}/itinerary/list")
    if itin:
        first = next(iter(itin.json()))
        r.notes.append(f"Itinerari in elenco: {len(itin.json())}")
        one = ctx.client.get(f"{API}/itinerary/{first}", ttl=3600)
        r.check(
            "dettaglio itinerario /api/v2/itinerary/{id}",
            one.ok,
            f"HTTP {one.status} ({one.header('content-type')}): endpoint non documentato",
            one.url,
        )
    if found.get("360"):
        hr = found["360"]["id"]
        pois = ctx.try_get(r, "POI entro 1 km da un sentiero (way)", f"{API}/ecpois/{hr}/W")
        if pois:
            r.notes.append(f"ecpois del sentiero 360 (tipo W): {len(pois.json())} elementi")
    pois_bb = ctx.client.get(f"{API}/ecpois/bb/{bbox}/N", ttl=3600)
    r.check("POI per bbox /ecpois/bb/{bbox}/N", pois_bb.ok, f"HTTP {pois_bb.status}", pois_bb.url)
    sectors = ctx.try_get(
        r, "settori CAI (v3) per bbox", f"{BASE}/api/v3/sectors/list", params={"bbox": bbox}
    )
    if sectors:
        names = [s["name"]["it"] for s in sectors.json()][:6]
        r.notes.append(f"Settori nella bbox Lagorai: {names}")
    gpx = ctx.try_get(r, "export GPX di un sentiero", f"{API}/hiking-routes/12711.gpx")
    if gpx:
        r.notes.append(
            "Il GPX di OSM2CAI ha <ele>0</ele> su tutti i punti: le quote vanno prese dal DEM."
            if "<ele>0</ele>" in gpx.text()
            else "Il GPX contiene quote."
        )
    r.examples += [f"{API}/hiking-routes/bb/{bbox}/4", f"{API}/hiking-route/12711"]
    return r.finish()
