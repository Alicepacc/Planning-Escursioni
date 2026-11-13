"""Mappa base vettoriale da OSM: Protomaps (PMTiles) e OpenFreeMap."""

from __future__ import annotations

from .base import ProbeContext, ProbeResult

PROBE_ID = "basemap"
PM_BUILDS = "https://build-metadata.protomaps.dev/builds.json"
OFM = "https://tiles.openfreemap.org"


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="Basemap vettoriale – Protomaps e OpenFreeMap",
        format="Protomaps: PMTiles planetario giornaliero; OpenFreeMap: TileJSON, tile MVT, stili",
        license="Dati ODbL 1.0 (© OpenStreetMap contributors); Protomaps: codice BSD, schema e "
        "stili aperti; OpenFreeMap: servizio gratuito «as-is»",
        license_url="https://openfreemap.org/tos/",
        limits="OpenFreeMap: niente raccolta automatica di tile, salvo download offline fino a "
        "3.000 tile o 50 MB, max 4 richieste parallele, User-Agent identificativo. Protomaps: "
        "`pmtiles extract` scarica solo l'area richiesta con richieste HTTP range.",
        update_frequency="Protomaps: build giornaliero; OpenFreeMap: settimanale",
    )
    builds = ctx.try_get(r, "Protomaps: elenco dei build", PM_BUILDS, ttl=86400)
    if builds:
        last = builds.json()[-1]
        r.check("build recente disponibile", last["key"].endswith(".pmtiles"), str(last["key"]))
        r.notes.append(
            f"Ultimo build Protomaps: {last['key']} ({last['size'] / 1e9:.0f} GB, versione schema "
            f"{last['version']}), URL https://build.protomaps.com/{last['key']}"
        )
        r.examples.append(f"https://build.protomaps.com/{last['key']}")
    tilejson = ctx.try_get(r, "OpenFreeMap: TileJSON", f"{OFM}/planet", ttl=86400)
    if tilejson:
        meta = tilejson.json()
        layers = [layer["id"] for layer in meta.get("vector_layers", [])]
        r.check("schema OpenMapTiles", "transportation" in layers, ", ".join(layers))
        r.notes.append(
            f"OpenFreeMap: zoom {meta.get('minzoom')}-{meta.get('maxzoom')}, attribuzione "
            f"«{meta.get('attribution', '')[:120]}»"
        )
    style = ctx.try_get(r, "OpenFreeMap: stile «liberty»", f"{OFM}/styles/liberty", ttl=86400)
    if style:
        r.check(
            "stile MapLibre valido",
            style.json().get("version") == 8,
            f"{len(style.json()['layers'])} layer",
        )
    tos = ctx.try_get(
        r, "OpenFreeMap: termini di servizio", "https://openfreemap.org/tos/", ttl=86400
    )
    if tos:
        r.check(
            "i termini indicano i limiti per l'offline",
            "3,000 tiles" in " ".join(tos.text().split()),
        )
    r.notes.append(
        "CLI `pmtiles` (go-pmtiles): distribuita come binario su GitHub Releases e come immagine "
        "Docker; da questo ambiente GitHub Releases non è raggiungibile, quindi l'estrazione "
        "dell'area pilota va provata in CI o in locale (Fase 1)."
    )
    r.notes.append(
        "Lo screenshot dello spike di routing (reports/phase0/routing-spike) usa lo stile "
        "OpenFreeMap «liberty» con MapLibre GL JS: rendering verificato."
    )
    return r.finish()
