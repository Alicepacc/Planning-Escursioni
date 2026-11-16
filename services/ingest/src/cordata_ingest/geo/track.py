"""Operazioni di base sulle tracce (liste di punti lon/lat in WGS84)."""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence

EARTH_RADIUS_M = 6_371_008.8
LonLat = tuple[float, float]


def haversine_m(a: Sequence[float], b: Sequence[float]) -> float:
    """Distanza sulla sfera tra due punti (lon, lat[, …]) in metri."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def cumulative_distances_m(coords: Sequence[Sequence[float]]) -> list[float]:
    """Distanza progressiva (m) di ogni punto dall'inizio della traccia."""
    out = [0.0]
    for prev, cur in itertools.pairwise(coords):
        out.append(out[-1] + haversine_m(prev, cur))
    return out


def length_m(coords: Sequence[Sequence[float]]) -> float:
    """Lunghezza planimetrica della traccia in metri."""
    return cumulative_distances_m(coords)[-1] if coords else 0.0


def resample_along(
    coords: Sequence[Sequence[float]], step_m: float = 15.0
) -> tuple[list[LonLat], list[float]]:
    """Ricampiona la traccia a passo costante e restituisce anche la distanza progressiva.

    La distanza restituita è quella misurata **lungo la traccia originale** (i, i·passo, …,
    totale), non la somma delle corde tra i punti ricampionati: sui tornanti le corde tagliano
    le curve e accorcerebbero il percorso. Primo e ultimo punto sono sempre conservati.
    Serve per interrogare il DEM in modo uniforme (SPEC §8: un punto ogni 10-20 m).
    """
    if step_m <= 0:
        raise ValueError("step_m deve essere positivo")
    if len(coords) < 2:
        return [(c[0], c[1]) for c in coords], [0.0] * len(coords)
    cum = cumulative_distances_m(coords)
    total = cum[-1]
    if total == 0:
        return [(coords[0][0], coords[0][1])], [0.0]
    targets = [i * step_m for i in range(int(total // step_m) + 1)]
    if total - targets[-1] > 1e-6:
        targets.append(total)
    out: list[LonLat] = []
    seg = 0
    for target in targets:
        while seg < len(cum) - 2 and cum[seg + 1] < target:
            seg += 1
        span = cum[seg + 1] - cum[seg]
        t = 0.0 if span == 0 else (target - cum[seg]) / span
        a, b = coords[seg], coords[seg + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out, targets


def resample(coords: Sequence[Sequence[float]], step_m: float = 15.0) -> list[LonLat]:
    """Solo i punti di `resample_along`."""
    return resample_along(coords, step_m)[0]
