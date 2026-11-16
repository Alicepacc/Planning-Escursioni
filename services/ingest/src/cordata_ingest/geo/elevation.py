"""Altimetria: lettura di un DEM e calcolo del dislivello con soglia di isteresi (SPEC §8)."""

from __future__ import annotations

import gzip
import io
import math
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np

from ..http import PoliteClient

SKADI_URL = "https://elevation-tiles-prod.s3.amazonaws.com/skadi"  # SRTM 1", AWS Open Data
HGT_SIZE = 3601  # campioni per lato di un tile da 1 arcosecondo
HGT_VOID = -32768


def ascent_descent(elevations: Sequence[float], threshold_m: float = 5.0) -> tuple[float, float]:
    """Dislivello positivo e negativo con soglia di isteresi.

    Una variazione di quota viene contata solo quando supera `threshold_m` rispetto all'ultimo
    punto di riferimento: così il rumore del DEM non gonfia il D+ (SPEC §8). Alla fine si somma
    anche il tratto residuo sotto soglia, in modo che salita − discesa = quota finale − iniziale
    (altrimenti una traccia che termina in salita perderebbe fino a `threshold_m` metri).
    Con soglia 0 si ottiene la somma grezza di tutte le variazioni.
    """
    up = down = 0.0
    if not elevations:
        return up, down
    ref = elevations[0]
    for ele in elevations[1:]:
        diff = ele - ref
        if diff >= threshold_m and diff > 0:
            up += diff
            ref = ele
        elif diff <= -threshold_m and diff < 0:
            down -= diff
            ref = ele
    tail = elevations[-1] - ref
    if tail > 0:
        up += tail
    else:
        down -= tail
    return up, down


def moving_average(values: Sequence[float], window: int) -> list[float]:
    """Media mobile centrata con finestra dispari, simmetrica anche ai bordi.

    Vicino agli estremi la finestra si restringe in modo simmetrico, quindi il primo e l'ultimo
    valore restano quelli misurati: la quota di partenza e di arrivo non viene spostata.
    """
    if window <= 1 or len(values) < 3:
        return list(values)
    half = window // 2
    n = len(values)
    out = []
    for i in range(n):
        h = min(half, i, n - 1 - i)
        chunk = values[i - h : i + h + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def tile_name(lon: float, lat: float) -> str:
    lat0, lon0 = math.floor(lat), math.floor(lon)
    ns, ew = ("N" if lat0 >= 0 else "S"), ("E" if lon0 >= 0 else "W")
    return f"{ns}{abs(lat0):02d}{ew}{abs(lon0):03d}"


class HgtDem:
    """DEM SRTM 1" in tile `.hgt.gz` (formato "skadi"), con interpolazione bilineare.

    I tile mancanti vengono scaricati nella cache tramite `PoliteClient`. È il DEM di confronto
    usato nello spike di routing della Fase 0; nella Fase 1 si affianca un DEM più fine.
    """

    def __init__(self, cache_dir: Path, client: PoliteClient | None = None):
        self.cache_dir = Path(cache_dir)
        self.client = client
        self._tiles: dict[str, np.ndarray] = {}

    def _load(self, name: str) -> np.ndarray:
        if name not in self._tiles:
            path = self.cache_dir / f"{name}.hgt.gz"
            if not path.exists():
                if self.client is None:
                    raise FileNotFoundError(f"tile DEM mancante: {path}")
                self.client.download(f"{SKADI_URL}/{name[:3]}/{name}.hgt.gz", path)
            with gzip.open(path, "rb") as fh:
                data = np.frombuffer(fh.read(), dtype=">i2")
            if data.size != HGT_SIZE * HGT_SIZE:
                raise ValueError(f"{path}: dimensione inattesa ({data.size} campioni)")
            self._tiles[name] = data.reshape((HGT_SIZE, HGT_SIZE))
        return self._tiles[name]

    def elevation(self, lon: float, lat: float) -> float:
        """Quota (m) nel punto, con interpolazione bilineare; NaN se il dato è assente."""
        tile = self._load(tile_name(lon, lat))
        x = (lon - math.floor(lon)) * (HGT_SIZE - 1)
        y = (1.0 - (lat - math.floor(lat))) * (HGT_SIZE - 1)  # la riga 0 è il bordo nord
        x0, y0 = min(int(x), HGT_SIZE - 2), min(int(y), HGT_SIZE - 2)
        fx, fy = x - x0, y - y0
        window = tile[y0 : y0 + 2, x0 : x0 + 2].astype(float)
        if (window == HGT_VOID).any():
            return float("nan")
        top = window[0, 0] * (1 - fx) + window[0, 1] * fx
        bottom = window[1, 0] * (1 - fx) + window[1, 1] * fx
        return float(top * (1 - fy) + bottom * fy)

    def sample(self, coords: Iterable[Sequence[float]]) -> list[float]:
        return [self.elevation(c[0], c[1]) for c in coords]


MAPTERHORN_TILES = "https://tiles.mapterhorn.com"
TERRARIUM_TILE_PX = 512


def lonlat_to_global_px(lon: float, lat: float, zoom: int, tile_px: int = TERRARIUM_TILE_PX):
    """Coordinate pixel globali Web Mercator (origine in alto a sinistra) al livello `zoom`."""
    scale = tile_px * 2**zoom
    x = (lon + 180.0) / 360.0 * scale
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * scale
    return x, y


def decode_terrarium(image_bytes: bytes) -> np.ndarray:
    """Tile Terrarium (PNG/WebP RGB) → matrice di quote in metri: R·256 + G + B/256 − 32768."""
    from PIL import Image  # import locale: Pillow serve solo per il DEM

    rgb = np.asarray(Image.open(io.BytesIO(image_bytes)).convert("RGB"), dtype=np.float64)
    return rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0


class TerrariumDem:
    """DEM da tile Terrarium (Mapterhorn), con cache su disco e interpolazione bilineare.

    È lo stesso dato che la mappa usa per l'ombreggiatura, quindi profili e rilievo sono
    coerenti. Fonti sull'area pilota: LiDAR della Provincia di Trento, TINITALY 10 m,
    Copernicus GLO-30 (attribuzioni in docs/data-sources.md).
    """

    def __init__(
        self,
        cache_dir: Path,
        client: PoliteClient | None = None,
        zoom: int = 13,
        base_url: str = MAPTERHORN_TILES,
    ):
        self.cache_dir = Path(cache_dir)
        self.client = client
        self.zoom = zoom
        self.base_url = base_url
        self._tiles: dict[tuple[int, int], np.ndarray] = {}
        self.tiles_downloaded = 0

    def _tile(self, tx: int, ty: int) -> np.ndarray:
        key = (tx, ty)
        if key not in self._tiles:
            path = self.cache_dir / str(self.zoom) / str(tx) / f"{ty}.webp"
            if not path.exists():
                if self.client is None:
                    raise FileNotFoundError(f"tile DEM mancante: {path}")
                url = f"{self.base_url}/{self.zoom}/{tx}/{ty}.webp"
                res = self.client.get(url, ttl=None).raise_for_status()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(res.content)
                self.tiles_downloaded += 1
            self._tiles[key] = decode_terrarium(path.read_bytes())
        return self._tiles[key]

    def _pixel(self, gx: int, gy: int) -> float:
        size = TERRARIUM_TILE_PX
        tile = self._tile(gx // size, gy // size)
        return float(tile[gy % size, gx % size])

    def elevation(self, lon: float, lat: float) -> float:
        """Quota (m) nel punto: bilineare sui centri dei pixel, anche a cavallo tra due tile."""
        px, py = lonlat_to_global_px(lon, lat, self.zoom)
        x, y = px - 0.5, py - 0.5
        x0, y0 = math.floor(x), math.floor(y)
        fx, fy = x - x0, y - y0
        top = self._pixel(x0, y0) * (1 - fx) + self._pixel(x0 + 1, y0) * fx
        bottom = self._pixel(x0, y0 + 1) * (1 - fx) + self._pixel(x0 + 1, y0 + 1) * fx
        return top * (1 - fy) + bottom * fy

    def sample(self, coords: Iterable[Sequence[float]]) -> list[float]:
        return [self.elevation(c[0], c[1]) for c in coords]
