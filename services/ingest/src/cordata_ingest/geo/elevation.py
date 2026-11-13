"""Altimetria: lettura di un DEM e calcolo del dislivello con soglia di isteresi (SPEC §8)."""

from __future__ import annotations

import gzip
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
    punto di riferimento: così il rumore del DEM non gonfia il D+ (SPEC §8). Con soglia 0 si
    ottiene la somma grezza di tutte le variazioni.
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
    return up, down


def moving_average(values: Sequence[float], window: int) -> list[float]:
    """Media mobile centrata (finestra dispari); i bordi usano la finestra disponibile."""
    if window <= 1 or len(values) < 3:
        return list(values)
    half = window // 2
    out = []
    for i in range(len(values)):
        chunk = values[max(0, i - half) : i + half + 1]
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
