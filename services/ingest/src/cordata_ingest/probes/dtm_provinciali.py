"""DTM provinciali ad alta risoluzione: Provincia di Bolzano (WCS) e Provincia di Trento."""

from __future__ import annotations

import re

from .base import STATUS_PARTIAL, ProbeContext, ProbeResult

PROBE_ID = "dtm_provinciali"
BZ_WCS = "https://geoservices9.civis.bz.it/geoserver/ows"
BZ_CATALOG_PAGE = "https://data.civis.bz.it/it/dataset?q=DTM"
BZ_COVERAGE = "p_bz-Elevation__DigitalTerrainModel-2.5m"
MERANO_UTM = (665000, 5170000)  # EPSG:25832, zona di Merano


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="DTM provinciali – Alto Adige (2,5 m / 0,5 m) e Trentino (LiDAR)",
        format="Bolzano: WCS 2.0.1 (GeoTIFF), EPSG:25832; Trento: vedi note",
        license="Bolzano: CC0 (catalogo dati della Provincia); Trento: CC BY 2.5 secondo il "
        "catalogo delle sorgenti di Mapterhorn (da confermare alla fonte)",
        license_url=BZ_CATALOG_PAGE,
        limits="Servizi OGC pubblici senza limiti pubblicati: scaricare a blocchi piccoli e una "
        "sola volta.",
        update_frequency="Rilievi LiDAR pluriennali",
    )
    caps = ctx.try_get(
        r,
        "Bolzano: WCS GetCapabilities",
        BZ_WCS,
        params={"service": "WCS", "version": "2.0.1", "request": "GetCapabilities"},
        ttl=7 * 86400,
    )
    if caps:
        ids = re.findall(r"<wcs:CoverageId>([^<]+)", caps.text())
        dtm = [i for i in ids if "DigitalTerrainModel" in i and "Hillshade" not in i]
        r.check("coverage DTM presenti", BZ_COVERAGE in ids, ", ".join(dtm)[:300])
    desc = ctx.try_get(
        r,
        "Bolzano: DescribeCoverage DTM 2,5 m",
        BZ_WCS,
        params={
            "service": "WCS",
            "version": "2.0.1",
            "request": "DescribeCoverage",
            "coverageId": BZ_COVERAGE,
        },
        ttl=7 * 86400,
    )
    if desc:
        text = desc.text()
        srs = re.search(r"EPSG/0/(\d+)", text)
        step = re.search(r"<gml:offsetVector[^>]*>([\d.]+)", text)
        axes = re.findall(r'axisLabels="([^"]+)"', text)[:1]
        r.notes.append(
            f"DTM Bolzano 2,5 m: EPSG:{srs.group(1) if srs else '?'}, passo "
            f"{step.group(1) if step else '?'} m, assi {axes}"
        )
    e, n = MERANO_UTM
    cov = ctx.try_get(
        r,
        "Bolzano: GetCoverage di un riquadro 250×250 m",
        BZ_WCS,
        params={
            "service": "WCS",
            "version": "2.0.1",
            "request": "GetCoverage",
            "coverageId": BZ_COVERAGE,
            "subset": [f"E({e},{e + 250})", f"N({n},{n + 250})"],
            "format": "image/tiff",
        },
        ttl=30 * 86400,
    )
    if cov:
        is_tiff = cov.content[:4] in (b"II*\x00", b"MM\x00*")
        r.check("la risposta è un GeoTIFF", is_tiff, f"{len(cov.content)} byte")
        if is_tiff:
            r.samples.append(ctx.save_sample(PROBE_ID, "bz_dtm_2.5m_sample.tif", cov.content))
            r.examples.append(cov.url)
    # l'API CKAN del catalogo è esclusa da robots.txt: la licenza si legge dalla pagina HTML
    page = ctx.try_get(r, "Bolzano: pagina del catalogo dati", BZ_CATALOG_PAGE, ttl=7 * 86400)
    if page:
        text = page.text()
        r.check(
            "Bolzano: licenza CC0 indicata nel catalogo",
            "CCZero" in text or "CC0" in text,
            "ricerca «DTM» sul catalogo data.civis.bz.it",
        )
    r.check(
        "Trento: download diretto del DTM LiDAR individuato",
        False,
        "il WCS di siat.provincia.tn.it non elenca coverage DTM; il portale geocartografico "
        "distribuisce il LiDAR per fogli (da individuare a mano)",
    )
    r.notes.append(
        "Per il Trentino il LiDAR PAT 2014/2018 è già integrato nei tile Mapterhorn (sorgente "
        "«ittrentino»): per la Fase 1 basta Mapterhorn; il download diretto resta da verificare."
    )
    r.notes.append(
        "Per l'Alto Adige Mapterhorn usa TINITALY 10 m / GLO-30: il DTM provinciale a 2,5 m (CC0) "
        "è il candidato per migliorare il dislivello in Alto Adige."
    )
    return r.finish(STATUS_PARTIAL if r.reachable else None)
