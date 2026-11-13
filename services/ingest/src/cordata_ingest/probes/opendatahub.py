"""Open Data Hub Alto Adige (NOI Techpark): itinerari escursionistici, GPX, webcam."""

from __future__ import annotations

from collections import Counter

from .base import ProbeContext, ProbeResult

PROBE_ID = "opendatahub"
API = "https://tourism.api.opendatahub.com/v1"
FIELDS = (
    "Id,Shortname,LicenseInfo,DistanceLength,DistanceDuration,AltitudeSumUp,AltitudeSumDown,"
    "AltitudeHighestPoint,Difficulty,Ratings,GpsTrack,GpsInfo,HasLanguage,Source"
)
MERANO = (46.67, 11.16)
VAL_INFERNO = (46.15, 11.55)


def _query(lat: float, lon: float, radius: int, size: int = 50) -> dict:
    return {
        "tagfilter": "hiking",
        "latitude": lat,
        "longitude": lon,
        "radius": radius,
        "pagesize": size,
        "fields": FIELDS,
    }


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="Open Data Hub Alto Adige – Tourism API (ODHActivityPoi, WebcamInfo)",
        format="JSON paginato (TotalResults, NextPage); tracce GPX collegate (GpsTrack)",
        license="Per record: LicenseInfo.License (CC0 oppure «Closed») e LicenseInfo.ClosedData; "
        "si usano solo i record con ClosedData=false",
        license_url="https://docs.opendatahub.com/en/latest/licenses.html",
        update_frequency="Continua (sincronizzazione dalle fonti LTS, IDM, SIAT…)",
    )
    merano = ctx.try_get(
        r, "itinerari entro 15 km da Merano", f"{API}/ODHActivityPoi", params=_query(*MERANO, 15000)
    )
    if merano:
        data = merano.json()
        items = data["Items"]
        licenses = Counter((i.get("LicenseInfo") or {}).get("License") for i in items)
        open_items = [i for i in items if not (i.get("LicenseInfo") or {}).get("ClosedData", True)]
        r.check("paginazione presente", "TotalResults" in data and "NextPage" in data)
        r.check("campo LicenseInfo su tutti i record", all(i.get("LicenseInfo") for i in items))
        r.check("esistono record con licenza aperta", bool(open_items), str(dict(licenses)))
        with_track = [i for i in open_items if i.get("GpsTrack")]
        with_stats = [i for i in open_items if i.get("DistanceLength")]
        closed_track = [i for i in items if i.get("GpsTrack") and i not in open_items]
        r.notes.append(
            f"Merano, raggio 15 km: {data['TotalResults']} itinerari; campione di {len(items)}: "
            f"licenze {dict(licenses)}, fonti {dict(Counter(i.get('Source') for i in items))}; "
            f"tra i {len(open_items)} aperti, {len(with_track)} hanno una traccia GPX e "
            f"{len(with_stats)} hanno la distanza; i record con traccia e licenza «Closed» sono "
            f"{len(closed_track)} (rete sentieri provinciale, fonte civis.geoserver)"
        )
        r.check(
            "record aperti con traccia GPX nel campione",
            bool(with_track),
            "nel campione i record CC0 (LTS) non hanno traccia né distanza; quelli con traccia "
            "sono «Closed»",
        )
        limit = {k: v for k, v in merano.headers.items() if "ratelimit" in k or "quota" in k}
        r.limits = (
            f"Accesso anonimo senza chiave; header di quota: {limit or 'nessuno'}. "
            "Per volumi maggiori Open Data Hub chiede di registrarsi (vedi documentazione)."
        )
        r.samples.append(ctx.save_sample(PROBE_ID, "hiking_merano.json", data))
        r.examples.append(merano.url)
        if with_track:
            one = with_track[0]
            track = one["GpsTrack"][0]
            url = track.get("GpxTrackUrl")
            r.notes.append(
                f"Aperto con traccia: «{one['Shortname']}» – {one.get('DistanceLength')} m, "
                f"+{one.get('AltitudeSumUp')} m, {one.get('DistanceDuration')} h, difficoltà "
                f"{one.get('Difficulty')}, lingue {one.get('HasLanguage')}; campi GpsTrack: "
                f"{sorted(track)}"
            )
            if url:
                gpx = ctx.try_get(r, "download GPX di un itinerario aperto", url, ttl=30 * 86400)
                if gpx:
                    points = gpx.text().count("<trkpt") + gpx.text().count("<rtept")
                    r.check(
                        "il GPX contiene punti", points > 0, f"{points} punti, {len(gpx.content)} B"
                    )
                    r.samples.append(ctx.save_sample(PROBE_ID, "sample_track.gpx", gpx.content))

    lagorai = ctx.try_get(
        r,
        "itinerari entro 10 km dalla Val d'Inferno (Trentino)",
        f"{API}/ODHActivityPoi",
        params=_query(*VAL_INFERNO, 10000, 25),
    )
    if lagorai:
        data = lagorai.json()
        items = data["Items"]
        r.notes.append(
            f"Val d'Inferno, raggio 10 km: {data['TotalResults']} record; fonti "
            f"{dict(Counter(i.get('Source') for i in items))}, licenze "
            f"{dict(Counter((i.get('LicenseInfo') or {}).get('License') for i in items))}; "
            f"esempi: {[i['Shortname'] for i in items[:4]]}"
        )
        r.check(
            "copertura anche in Trentino (Lagorai)",
            data["TotalResults"] > 0,
            str(data["TotalResults"]),
        )
        r.samples.append(ctx.save_sample(PROBE_ID, "hiking_val_inferno.json", data))

    cams = ctx.try_get(
        r,
        "webcam entro 10 km da Merano",
        f"{API}/WebcamInfo",
        params={
            "latitude": MERANO[0],
            "longitude": MERANO[1],
            "radius": 10000,
            "pagesize": 20,
            "fields": "Id,Shortname,LicenseInfo,GpsInfo",
        },
    )
    if cams:
        data = cams.json()
        licenses = Counter((i.get("LicenseInfo") or {}).get("License") for i in data["Items"])
        r.notes.append(
            f"Webcam entro 10 km da Merano: {data['TotalResults']}; licenze {dict(licenses)}"
        )
    return r.finish()
