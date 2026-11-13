"""SAT – Società degli Alpinisti Tridentini: tracciati dei sentieri del Trentino (open data)."""

from __future__ import annotations

import io
import re
import zipfile

from .base import ProbeContext, ProbeResult

PROBE_ID = "sat_trails"
PAGE = "https://www.sat.tn.it/sentieri/mappa-sentieri/"
DOWNLOAD = "https://sentieri.sat.tn.it/download"
FIXTURE_REFS = ("332", "360", "326")


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="SAT – sentieri del Trentino",
        format="ZIP con GPX / KML (WGS84, EPSG:4326) o Shapefile (ETRS89 UTM 32N, EPSG:25832)",
        license="ODbL 1.0; attribuzione richiesta: «© Società degli Alpinisti Tridentini (SAT)» "
        "con link a https://www.sat.tn.it/sentieri/",
        license_url=PAGE,
        limits="File statici, nessun limite pubblicato; la pagina chiede di accettare la licenza.",
        update_frequency="Aggiornamenti all'inizio di ogni mese (dichiarato nella pagina)",
    )
    page = ctx.try_get(r, "pagina di download e licenza", PAGE)
    if page:
        text = page.text()
        r.check("la pagina dichiara la licenza ODbL", "Open Database License" in text)
        r.check(
            "la pagina indica l'attribuzione a SAT",
            "Società degli Alpinisti Tridentini (SAT)" in text,
        )
        links = sorted(set(re.findall(r"https://sentieri\.sat\.tn\.it/download/[\w.]+\.zip", text)))
        r.check("link ai tre formati (GPX, KML, SHP)", len(links) == 3, ", ".join(links))
        r.examples += links

    gpx_zip = ctx.try_get(
        r, "download sentierisat.gpx.zip", f"{DOWNLOAD}/sentierisat.gpx.zip", ttl=7 * 86400
    )
    if gpx_zip:
        r.samples.append(ctx.save_sample(PROBE_ID, "sentierisat.gpx.zip", gpx_zip.content))
        archive = zipfile.ZipFile(io.BytesIO(gpx_zip.content))
        names = archive.namelist()
        r.notes.append(
            f"sentierisat.gpx.zip: {len(gpx_zip.content) / 1e6:.1f} MB, {len(names)} file; "
            f"esempi: {names[:4]}; Last-Modified: {gpx_zip.header('last-modified')}"
        )
        gpx_names = [n for n in names if n.lower().endswith(".gpx")]
        r.check("l'archivio contiene file GPX", bool(gpx_names), f"{len(gpx_names)} GPX")
        for ref in FIXTURE_REFS:
            hits = [
                n for n in gpx_names if re.search(rf"(?<!\d)[EO]?{ref}(?!\d)", n.rsplit("/", 1)[-1])
            ]
            detail = ", ".join(hits[:4]) or "nessun file con questo numero nel nome"
            if not hits and len(gpx_names) == 1:  # un solo GPX con tutte le tracce: cerca nei nomi
                body = archive.read(gpx_names[0]).decode("utf-8", errors="replace")
                found = re.findall(rf"<name>([^<]*\b[EO]?{ref}\b[^<]*)</name>", body)
                hits, detail = found, "; ".join(found[:3]) or "numero non presente nei <name>"
            r.check(f"sentiero {ref} presente nei dati SAT", bool(hits), detail)
        first = archive.read(gpx_names[0]).decode("utf-8", errors="replace") if gpx_names else ""
        if first:
            header = re.sub(r"\s+", " ", first[:300])
            r.notes.append(
                f"Primo GPX ({gpx_names[0]}): {first.count('<trkpt')} punti traccia, "
                f"quote {'presenti' if '<ele>' in first else 'assenti'}; intestazione: {header}"
            )
    r.notes.append(
        "La pagina avverte che solo parte dei tracciati deriva da rilievo GPS di precisione: "
        "come da SPEC, i dati SAT arricchiscono e confrontano ma non sovrascrivono OSM."
    )
    return r.finish()
