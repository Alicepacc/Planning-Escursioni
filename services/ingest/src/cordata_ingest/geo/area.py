"""Area del catalogo (ADR 0015): Trentino-Alto Adige con Dolomiti e Prealpi venete, decisa dalla
meta dell'escursione.

Il poligono è in `config/areas/catalogo.geojson`. Un'escursione è nell'area se ci cade
la maggior parte della sua traccia o, senza traccia, la partenza e i punti chiave.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.prepared import prep

from ..config import repo_root

AREA_FILE = "catalogo.geojson"
# quota della traccia che deve cadere nell'area
MIN_SHARE = 0.5


@lru_cache(maxsize=1)
def _area(path: str | None = None):
    p = Path(path) if path else repo_root() / "config" / "areas" / AREA_FILE
    geom = shape(json.loads(p.read_text(encoding="utf-8"))["features"][0]["geometry"])
    return geom, prep(geom)


def area_geometry():
    return _area()[0]


def contains(lon: float, lat: float) -> bool:
    return _area()[1].contains(Point(lon, lat))


def share_inside(points: Iterable[tuple[float, float]]) -> float | None:
    """Quota dei punti dentro l'area (None se non ci sono punti)."""
    pts = list(points)
    if not pts:
        return None
    return sum(contains(lon, lat) for lon, lat in pts) / len(pts)


def in_area(line: list[list[float]] | None, places: Iterable[tuple[float, float]] = ()) -> bool:
    """Dentro se ci cade almeno metà della traccia; senza traccia, almeno metà dei punti."""
    if line:
        step = max(1, len(line) // 200)  # basta un campione della traccia
        share = share_inside((p[0], p[1]) for p in line[::step])
    else:
        share = share_inside(places)
    return share is not None and share >= MIN_SHARE
