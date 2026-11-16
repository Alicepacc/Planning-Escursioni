"""Test del DEM Terrarium e del profilo (tile sintetici, nessuna chiamata di rete)."""

from __future__ import annotations

import io
import math

import numpy as np
import pytest
from PIL import Image
from shapely.geometry import LineString, MultiLineString

from cordata_ingest.geo.elevation import (
    TERRARIUM_TILE_PX,
    TerrariumDem,
    decode_terrarium,
    lonlat_to_global_px,
)
from cordata_ingest.geo.profile import ProfileParams, as_single_line, compute_profile
from cordata_ingest.timing import swiss_segment_minutes


def terrarium_png(heights: np.ndarray) -> bytes:
    v = heights + 32768.0
    r = np.floor(v / 256)
    g = np.floor(v - r * 256)
    b = np.round((v - r * 256 - g) * 256)
    rgb = np.stack([r, g, b], axis=-1).clip(0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, format="PNG")
    return buf.getvalue()


def test_decode_terrarium_roundtrip():
    heights = np.array([[1350.0, 2253.5], [0.0, -10.25]])
    assert decode_terrarium(terrarium_png(heights)) == pytest.approx(heights, abs=0.01)


def test_global_pixel_coordinates():
    x, y = lonlat_to_global_px(0, 0, 0)
    assert (x, y) == pytest.approx((256, 256))
    x, y = lonlat_to_global_px(-180, 85.0511287798, 2)
    assert (x, y) == pytest.approx((0, 0), abs=1e-6)


class PlaneDem(TerrariumDem):
    """DEM sintetico: la quota cresce verso nord di `grad` metri per pixel globale."""

    def __init__(self, tmp_path, grad: float = 1.0, zoom: int = 13):
        super().__init__(tmp_path, client=None, zoom=zoom)
        self.grad = grad

    def _tile(self, tx, ty):
        key = (tx, ty)
        if key not in self._tiles:
            rows = (ty * TERRARIUM_TILE_PX + np.arange(TERRARIUM_TILE_PX) + 0.5)[:, None]
            plane = 5000 - self.grad * (rows - 2_900_000 / 1000) * np.ones((1, TERRARIUM_TILE_PX))
            self._tiles[key] = decode_terrarium(terrarium_png(plane))
        return self._tiles[key]


def test_bilinear_is_continuous_across_tile_edges(tmp_path):
    dem = PlaneDem(tmp_path)
    lat_edge = None
    # trova una latitudine sul bordo tra due tile (pixel globale multiplo di 512)
    lo, hi = 46.0, 46.2
    target_y = (math.floor(lonlat_to_global_px(11.5, 46.1, 13)[1] / 512) + 1) * 512
    for _ in range(60):
        mid = (lo + hi) / 2
        if lonlat_to_global_px(11.5, mid, 13)[1] > target_y:
            lo = mid
        else:
            hi = mid
    lat_edge = (lo + hi) / 2
    north = dem.elevation(11.5, lat_edge + 1e-5)
    south = dem.elevation(11.5, lat_edge - 1e-5)
    assert abs(north - south) < 2, "nessun salto tra tile adiacenti"
    assert north > south


def test_missing_tile_without_client(tmp_path):
    with pytest.raises(FileNotFoundError):
        TerrariumDem(tmp_path).elevation(11.5, 46.1)


class LinearDem:
    """DEM finto: quota = 1000 + 100 m per km verso nord (pendenza 10% lungo un meridiano)."""

    def sample(self, coords):
        return [1000 + (c[1] - 46.0) * 111_195 * 0.1 for c in coords]


def test_profile_of_a_straight_climb():
    line = [(11.5, 46.0), (11.5, 46.0 + 1000 / 111_195)]  # 1 km verso nord
    prof = compute_profile(line, LinearDem(), ProfileParams(step_m=15, smooth_window=1))
    assert prof.length_m == pytest.approx(1000, rel=1e-3)
    assert prof.ascent_m == pytest.approx(100, abs=10)  # isteresi 10 m: al massimo un gradino
    assert prof.descent_m == 0
    assert prof.max_ele_m - prof.min_ele_m == pytest.approx(100, abs=0.5)
    assert prof.minutes_forward == pytest.approx(swiss_segment_minutes(1000, 100), abs=0.5)
    assert prof.minutes_backward == pytest.approx(swiss_segment_minutes(1000, -100), abs=0.5)


def test_as_single_line_merges_parts_and_counts_gaps():
    joined = MultiLineString([[(0, 0), (1, 0)], [(1, 0), (2, 0)]])
    coords, gaps = as_single_line(joined)
    assert gaps == 0 and coords[0] == (0, 0) and coords[-1] == (2, 0)
    broken = MultiLineString([[(0, 0), (1, 0)], [(5, 0), (6, 0)]])
    coords, gaps = as_single_line(broken)
    assert gaps == 1 and len(coords) == 4
    assert as_single_line(LineString([(0, 0), (1, 1)])) == ([(0, 0), (1, 1)], 0)
