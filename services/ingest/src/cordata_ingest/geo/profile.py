"""Profilo altimetrico e statistiche di una traccia (SPEC §8)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge

from ..timing import swiss_track_minutes
from .elevation import ascent_descent, moving_average
from .track import resample_along


class Dem(Protocol):
    def sample(self, coords: Sequence[Sequence[float]]) -> list[float]: ...


@dataclass(frozen=True)
class ProfileParams:
    """Parametri del calcolo, da calibrare (ADR 0007): passo, smoothing, isteresi, tratti."""

    step_m: float = 15.0
    smooth_window: int = 5  # campioni della media mobile (5 × 15 m = 75 m)
    hysteresis_m: float = 10.0
    time_segment_m: float = 100.0


@dataclass
class Profile:
    distances_m: list[float]
    elevations_m: list[float]  # quote già smussate
    coords: list[tuple[float, float]]
    length_m: float
    ascent_m: float
    descent_m: float
    min_ele_m: float
    max_ele_m: float
    minutes_forward: float
    minutes_backward: float
    steep_m: float
    gaps: int = 0  # interruzioni della geometria (parti non collegate)
    params: ProfileParams = field(default_factory=ProfileParams)


def as_single_line(geometry: LineString | MultiLineString) -> tuple[list[tuple[float, float]], int]:
    """Unisce le parti di una MultiLineString; se restano staccate le concatena e le conta."""
    if isinstance(geometry, LineString):
        return [(x, y) for x, y, *_ in geometry.coords], 0
    merged = linemerge(geometry)
    if isinstance(merged, LineString):
        return [(x, y) for x, y, *_ in merged.coords], 0
    parts = list(merged.geoms)
    coords: list[tuple[float, float]] = []
    for part in parts:
        coords.extend((x, y) for x, y, *_ in part.coords)
    return coords, len(parts) - 1


def compute_profile(
    coords: Sequence[Sequence[float]], dem: Dem, params: ProfileParams | None = None, gaps: int = 0
) -> Profile:
    p = params or ProfileParams()
    points, dist = resample_along(coords, p.step_m)
    raw = dem.sample(points)
    smooth = moving_average(raw, p.smooth_window)
    up, down = ascent_descent(smooth, p.hysteresis_m)
    forward = swiss_track_minutes(dist, smooth, p.time_segment_m)
    total = dist[-1] if dist else 0.0
    backward = swiss_track_minutes(
        [total - d for d in reversed(dist)], list(reversed(smooth)), p.time_segment_m
    )
    return Profile(
        distances_m=dist,
        elevations_m=smooth,
        coords=list(points),
        length_m=total,
        ascent_m=up,
        descent_m=down,
        min_ele_m=min(smooth) if smooth else float("nan"),
        max_ele_m=max(smooth) if smooth else float("nan"),
        minutes_forward=forward.minutes,
        minutes_backward=backward.minutes,
        steep_m=forward.steep_m,
        gaps=gaps,
        params=p,
    )
