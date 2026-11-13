"""Open-Meteo: previsione oraria con downscaling per quota e Elevation API (SPEC §5.5)."""

from __future__ import annotations

from .base import ProbeContext, ProbeResult

PROBE_ID = "open_meteo"
API = "https://api.open-meteo.com/v1"
VARIABLES = (
    "temperature_2m,precipitation,freezing_level_height,wind_speed_10m,wind_gusts_10m,"
    "cloud_cover,cape,weather_code"
)
CIMA_NASSERE = (11.550534, 46.150821, 2253)
TEDON = (11.521522, 46.148609, 1350)
# api.open-meteo.com ha `Disallow: /` nel robots.txt (vale per i crawler); l'uso programmatico
# dell'API è regolato dai termini d'uso, che lo consentono entro i limiti indicati sotto.
API_TERMS = {"respect_robots": False}


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="Open-Meteo (Forecast + Elevation API)",
        format="JSON",
        license="CC BY 4.0 (dati API); uso gratuito solo non commerciale",
        license_url="https://open-meteo.com/en/terms",
        limits="Free API: meno di 10.000 chiamate/giorno, 5.000/ora e 600/minuto, contate per "
        "indirizzo IP (header X-RateLimit-*). Nessuna chiave.",
        update_frequency="Modelli aggiornati più volte al giorno; previsione fino a 16 giorni",
    )
    lon, lat, ele = CIMA_NASSERE
    fc = ctx.try_get(
        r,
        "previsione oraria con parametro elevation",
        f"{API}/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "elevation": ele,
            "hourly": VARIABLES,
            "forecast_days": 3,
            "timezone": "Europe/Rome",
        },
        ttl=3600,
        **API_TERMS,
    )
    if fc:
        data = fc.json()
        hourly = data["hourly"]
        missing = [v for v in VARIABLES.split(",") if v not in hourly]
        r.check("tutte le variabili richieste sono presenti", not missing, f"mancanti: {missing}")
        r.check("la quota usata è quella passata", data["elevation"] == ele, str(data["elevation"]))
        nulls = {v: sum(x is None for x in hourly[v]) for v in VARIABLES.split(",") if v in hourly}
        r.check("nessun valore nullo nelle 72 ore", not any(nulls.values()), str(nulls))
        i = 12  # mezzogiorno del primo giorno
        r.notes.append(
            f"Cima Nassere ({ele} m) alle {hourly['time'][i]}: {hourly['temperature_2m'][i]} °C, "
            f"zero termico {hourly['freezing_level_height'][i]} m, vento "
            f"{hourly['wind_speed_10m'][i]} km/h (raffiche {hourly['wind_gusts_10m'][i]}), "
            f"CAPE {hourly['cape'][i]} J/kg, codice meteo {hourly['weather_code'][i]}"
        )
        r.notes.append(
            f"Limiti letti dagli header: X-RateLimit-Limit={fc.header('x-ratelimit-limit')} "
            f"su finestra di {fc.header('x-ratelimit-window')} s"
        )
        r.samples.append(ctx.save_sample(PROBE_ID, "forecast_cima_nassere.json", data))
        r.examples.append(fc.url)

    el = ctx.try_get(
        r,
        "Elevation API su due punti",
        f"{API}/elevation",
        params={"latitude": f"{lat},{TEDON[1]}", "longitude": f"{lon},{TEDON[0]}"},
        ttl=30 * 86400,
        **API_TERMS,
    )
    if el:
        got = el.json()["elevation"]
        r.check(
            "quote plausibili (cima ±50 m, parcheggio ±30 m)",
            abs(got[0] - ele) <= 50 and abs(got[1] - TEDON[2]) <= 30,
            f"Cima Nassere {got[0]} m (OSM {ele}), Tedon {got[1]} m (OSM {TEDON[2]})",
        )
    r.notes.append(
        "Il 12/11/2026 la stessa API ha risposto 429 «Daily API request limit exceeded» "
        "(X-RateLimit-Limit 10000 / 86400 s) perché il limite è per IP e l'ambiente cloud "
        "condivide l'IP di uscita con altri: in produzione servono IP proprio e cache lato "
        "server, oppure l'immagine Docker self-hosted di open-meteo."
    )
    return r.finish()
