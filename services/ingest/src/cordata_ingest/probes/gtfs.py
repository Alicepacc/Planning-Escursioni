"""GTFS del trasporto pubblico: Alto Adige (STA via Open Data Hub) e Trentino Trasporti."""

from __future__ import annotations

import csv
import io
import zipfile

from .base import ProbeContext, ProbeResult

PROBE_ID = "gtfs"
ODH = "https://gtfs.api.opendatahub.com/v1"
TT_PAGE = "https://dati.trentino.it/dataset/trasporti-pubblici-del-trentino-formato-gtfs"
TT_GTFS = "https://www.trentinotrasporti.it/opendata/google_transit_extraurbano_tte.zip"
MAX_SAMPLE_BYTES = 30_000_000


def _stops_in(bbox: tuple[float, ...], archive: zipfile.ZipFile) -> tuple[int, int]:
    w, s, e, n = bbox
    with archive.open("stops.txt") as fh:
        rows = list(csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig")))
    inside = sum(
        1
        for row in rows
        if row.get("stop_lat")
        and w <= float(row["stop_lon"]) <= e
        and s <= float(row["stop_lat"]) <= n
    )
    return len(rows), inside


def _feed(ctx: ProbeContext, r: ProbeResult, label: str, url: str, filename: str) -> None:
    res = ctx.try_get(r, f"{label}: download GTFS", url, ttl=7 * 86400)
    if not res:
        return
    if len(res.content) <= MAX_SAMPLE_BYTES:
        r.samples.append(ctx.save_sample(PROBE_ID, filename, res.content))
    archive = zipfile.ZipFile(io.BytesIO(res.content))
    names = set(archive.namelist())
    required = {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
    r.check(f"{label}: file GTFS obbligatori", required <= names, ", ".join(sorted(names))[:160])
    total, pilot = _stops_in(ctx.pilot.bbox, archive)
    _, lagorai = _stops_in(ctx.lagorai.bbox, archive)
    validity = ""
    for cal in ("feed_info.txt", "calendar.txt"):
        if cal in names:
            with archive.open(cal) as fh:
                rows = list(csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig")))
            ends = [x.get("feed_end_date") or x.get("end_date") for x in rows]
            validity = (
                f"; validità fino al {max(e for e in ends if e)} ({cal})" if any(ends) else ""
            )
            break
    r.notes.append(
        f"{label}: {len(res.content) / 1e6:.1f} MB, {total} fermate ({pilot} nell'area pilota, "
        f"{lagorai} nella bbox Lagorai){validity}"
    )
    r.examples.append(url)


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="GTFS – STA Alto Adige e Trentino Trasporti",
        format="GTFS (ZIP di CSV); per STA anche GTFS-Realtime",
        license="STA: CC0 (dichiarata dall'API Open Data Hub); Trentino Trasporti: CC BY 4.0 "
        "(catalogo dati.trentino.it)",
        license_url=TT_PAGE,
        limits="File statici; nessun limite pubblicato.",
        update_frequency="Per cambio orario: la validità di ogni feed si legge nei suoi file",
    )
    listing = ctx.try_get(r, "Open Data Hub: elenco dataset GTFS", f"{ODH}/dataset", ttl=86400)
    sta_url = f"{ODH}/dataset/sta-time-tables/raw"
    if listing:
        sta = listing.json().get("sta-time-tables", {})
        r.check("STA: licenza dichiarata CC0", sta.get("license") == "CC0", str(sta.get("license")))
        sta_url = sta.get("endpoint", sta_url)
    _feed(ctx, r, "STA Alto Adige", sta_url, "sta-time-tables.zip")

    # il catalogo CKAN vieta /api/ via robots.txt: la licenza si legge dalla pagina del dataset
    page = ctx.try_get(r, "pagina del dataset su dati.trentino.it", TT_PAGE, ttl=86400)
    if page:
        r.check(
            "Trentino Trasporti: licenza CC BY 4.0",
            "Creative Commons Attribution 4.0" in page.text() or "CC-BY" in page.text(),
            "licenza indicata nella pagina del dataset",
        )
    _feed(ctx, r, "Trentino extraurbano", TT_GTFS, "trentino_extraurbano.zip")
    return r.finish()
