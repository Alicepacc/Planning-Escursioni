"""Mapterhorn: tile del terreno in codifica Terrarium (hillshade, 3D, profilo altimetrico)."""

from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image

from .base import ProbeContext, ProbeResult

PROBE_ID = "mapterhorn"
TILES = "https://tiles.mapterhorn.com"
DOWNLOADS = "https://download.mapterhorn.com"
CIMA_NASSERE = (11.550534, 46.150821, 2253)
LOCAL_SOURCES = ("glo30", "ittrentino", "tinitaly")


def tile_xy(lon: float, lat: float, zoom: int) -> tuple[int, int, float, float]:
    """Tile XYZ che contiene il punto e posizione frazionaria (0-1) al suo interno."""
    n = 2**zoom
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return int(x), int(y), x - int(x), y - int(y)


def terrarium_elevation(image_bytes: bytes, fx: float, fy: float) -> tuple[float, int]:
    """Quota nel punto frazionario del tile: h = R·256 + G + B/256 − 32768."""
    img = np.asarray(Image.open(io.BytesIO(image_bytes)).convert("RGB"), dtype=np.float64)
    size = img.shape[0]
    px, py = min(int(fx * size), size - 1), min(int(fy * size), size - 1)
    r, g, b = img[py, px]
    return r * 256 + g + b / 256 - 32768, size


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="Mapterhorn – terrain tiles (Copernicus GLO-30 + DEM nazionali)",
        format="Tile WebP 512 px in codifica Terrarium; PMTiles (planet z0-12 + riquadri z13-17)",
        license="Dipende dalla sorgente (vedi attribution.json): Copernicus GLO-30 (licenza "
        "Copernicus), TINITALY (CC BY 4.0), LiDAR PAT Trentino (CC BY 2.5)",
        license_url="https://mapterhorn.com/attribution",
        limits="Endpoint pubblico su Cloudflare senza limiti pubblicati; per la produzione "
        "estrarre l'area con `pmtiles extract` e servirla dal proprio object storage.",
        update_frequency="Versioni periodiche (download_urls.json riporta la versione)",
    )
    tj = ctx.try_get(r, "TileJSON", f"{TILES}/tilejson.json", ttl=86400)
    if tj:
        meta = tj.json()
        r.check(
            "codifica Terrarium, tile 512 px",
            meta.get("encoding") == "terrarium" and meta.get("tileSize") == 512,
            f"encoding={meta.get('encoding')}, tileSize={meta.get('tileSize')}",
        )
    lon, lat, expected = CIMA_NASSERE
    best = None
    for zoom in (12, 14, 15, 16):
        x, y, fx, fy = tile_xy(lon, lat, zoom)
        res = ctx.client.get(f"{TILES}/{zoom}/{x}/{y}.webp", ttl=30 * 86400)
        is_image = res.ok and res.content[:4] == b"RIFF"
        if not is_image:
            r.notes.append(f"z{zoom}: nessun tile su Cima Nassere (HTTP {res.status})")
            continue
        ele, size = terrarium_elevation(res.content, fx, fy)
        best = (zoom, ele)
        r.notes.append(
            f"z{zoom}/{x}/{y}: {len(res.content) / 1024:.0f} kB, {size} px, quota decodificata su "
            f"Cima Nassere {ele:.0f} m (OSM {expected} m)"
        )
        if zoom == 14:
            r.samples.append(ctx.save_sample(PROBE_ID, f"tile_{zoom}_{x}_{y}.webp", res.content))
            r.examples.append(res.url)
    r.check(
        "quota di Cima Nassere entro ±30 m al massimo zoom disponibile",
        best is not None and abs(best[1] - expected) <= 30,
        f"z{best[0]}: {best[1]:.0f} m" if best else "nessun tile decodificato",
    )
    attr = ctx.try_get(
        r, "catalogo delle sorgenti (attribution.json)", f"{DOWNLOADS}/attribution.json"
    )
    if attr:
        for src in attr.json():
            if src.get("source") in LOCAL_SOURCES:
                r.notes.append(
                    f"Sorgente «{src['source']}»: {src['name']} – licenza {src['license']} – "
                    f"{src['producer'][:90]}"
                )
    urls = ctx.try_get(r, "elenco PMTiles (download_urls.json)", f"{DOWNLOADS}/download_urls.json")
    if urls:
        data = urls.json()
        w, s, e, n = ctx.pilot.bbox
        hits = [
            i
            for i in data["items"]
            if i["min_zoom"] >= 13
            and i["min_lon"] < e
            and i["max_lon"] > w
            and i["min_lat"] < n
            and i["max_lat"] > s
        ]
        planet = next(i for i in data["items"] if i["name"] == "planet.pmtiles")
        r.notes.append(
            f"Versione {data['version']}: planet.pmtiles z0-12 = {planet['size'] / 1e9:.0f} GB; "
            f"riquadri z13+ che intersecano l'area pilota: "
            f"{[(i['name'], round(i['size'] / 1e9, 1)) for i in hits]} (GB)"
        )
    return r.finish()
