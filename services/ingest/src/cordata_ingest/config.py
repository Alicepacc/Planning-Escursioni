"""Configurazione condivisa: percorsi del repository, aree geografiche, User-Agent."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from . import __version__


def repo_root() -> Path:
    """Radice del monorepo (override con CORDATA_ROOT, utile nei container)."""
    env = os.environ.get("CORDATA_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "areas.yaml").exists():
            return parent
    raise RuntimeError("Radice del repository non trovata: imposta CORDATA_ROOT")


def data_dir() -> Path:
    """Cartella dei dati scaricati (non versionata)."""
    return Path(os.environ.get("CORDATA_DATA_DIR", repo_root() / "data")).resolve()


def lonlat_to_mercator(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 → Web Mercator (EPSG:3857), in metri."""
    radius = 6378137.0
    x = math.radians(lon) * radius
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * radius
    return x, y


@dataclass(frozen=True)
class Area:
    key: str
    name: str
    bbox: tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat

    @property
    def bbox_str(self) -> str:
        """Formato `min_lon,min_lat,max_lon,max_lat` (OSM2CAI, Waymarked Trails…)."""
        return ",".join(f"{v:g}" for v in self.bbox)

    @property
    def overpass_bbox(self) -> str:
        """Formato Overpass `south,west,north,east`."""
        w, s, e, n = self.bbox
        return f"{s:g},{w:g},{n:g},{e:g}"

    @property
    def mercator_bbox(self) -> str:
        """bbox in Web Mercator (EPSG:3857), `min_x,min_y,max_x,max_y` (Waymarked Trails)."""
        w, s, e, n = self.bbox
        (x1, y1), (x2, y2) = lonlat_to_mercator(w, s), lonlat_to_mercator(e, n)
        return f"{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}"

    @property
    def center(self) -> tuple[float, float]:
        w, s, e, n = self.bbox
        return ((w + e) / 2, (s + n) / 2)


@lru_cache(maxsize=1)
def areas() -> dict[str, Area]:
    raw = yaml.safe_load((repo_root() / "config" / "areas.yaml").read_text(encoding="utf-8"))
    return {
        key: Area(key=key, name=val["name"], bbox=tuple(val["bbox"]))  # type: ignore[arg-type]
        for key, val in raw.items()
    }


def user_agent() -> str:
    """User-Agent identificativo richiesto dal §3 della SPEC.

    Il contatto (email o URL del progetto) si imposta con CORDATA_CONTACT: non va mai scritto
    nel codice. Senza contatto lo User-Agent lo dichiara in modo esplicito.
    """
    contact = os.environ.get("CORDATA_CONTACT", "").strip()
    suffix = f"+{contact}" if contact else "contatto non ancora configurato"
    return f"Cordata/{__version__} (PWA escursioni open data; {suffix})"
