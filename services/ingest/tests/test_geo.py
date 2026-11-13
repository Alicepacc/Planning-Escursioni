"""Test di distanze, ricampionamento e dislivello con isteresi."""

from __future__ import annotations

import gzip
import itertools

import numpy as np
import pytest

from cordata_ingest.geo.elevation import HGT_SIZE, HgtDem, ascent_descent, moving_average, tile_name
from cordata_ingest.geo.track import cumulative_distances_m, haversine_m, length_m, resample


def test_haversine_one_degree_of_latitude():
    assert haversine_m((11.5, 46.0), (11.5, 47.0)) == pytest.approx(111_195, rel=1e-3)


def test_haversine_ignores_extra_dimensions():
    assert haversine_m((11.5, 46.0, 1350.0), (11.5, 46.0, 2253.0)) == 0


def test_length_and_cumulative():
    coords = [(11.5, 46.0), (11.5, 46.001), (11.5, 46.002)]
    cum = cumulative_distances_m(coords)
    assert cum[0] == 0 and cum[2] == pytest.approx(2 * cum[1])
    assert length_m(coords) == pytest.approx(222.4, abs=0.5)
    assert length_m([]) == 0


def test_resample_keeps_endpoints_and_spacing():
    coords = [(11.5, 46.0), (11.5, 46.001), (11.501, 46.001)]
    pts = resample(coords, step_m=15)
    assert pts[0] == coords[0] and pts[-1] == pytest.approx(coords[-1])
    gaps = [haversine_m(a, b) for a, b in itertools.pairwise(pts)]
    assert all(g <= 15.01 for g in gaps)
    assert all(g == pytest.approx(15, abs=0.2) for g in gaps[:5])
    # l'angolo a 90° viene tagliato al massimo di un passo
    assert length_m(coords) - 15 <= length_m(pts) <= length_m(coords)


def test_resample_rejects_bad_step():
    with pytest.raises(ValueError):
        resample([(0, 0), (1, 1)], step_m=0)


def test_ascent_descent_without_threshold_sums_everything():
    assert ascent_descent([100, 103, 101, 110, 90], threshold_m=0) == (12, 22)


def test_hysteresis_filters_dem_noise():
    # salita reale di 100 m con rumore di ±2 m a ogni campione
    noisy = [1000 + i + (2 if i % 2 else -2) for i in range(101)]
    raw_up, raw_down = ascent_descent(noisy, threshold_m=0)
    up, down = ascent_descent(noisy, threshold_m=5)
    assert raw_up > 200 and raw_down > 100, "senza soglia il rumore gonfia il dislivello"
    assert up == pytest.approx(100, abs=6) and down == 0


def test_hysteresis_keeps_real_ups_and_downs():
    profile = [1350, 1752, 1950, 2253, 1985, 1924, 1848, 1460, 1350]
    assert ascent_descent(profile, threshold_m=10) == (903, 903)
    assert ascent_descent([], 5) == (0, 0)
    assert ascent_descent([1000], 5) == (0, 0)


def test_moving_average():
    assert moving_average([0, 10, 0, 10, 0], 3) == [
        5,
        pytest.approx(10 / 3),
        pytest.approx(20 / 3),
        pytest.approx(10 / 3),
        5,
    ]
    assert moving_average([1, 2], 3) == [1, 2]


def test_tile_name():
    assert tile_name(11.55, 46.15) == "N46E011"
    assert tile_name(-0.5, -33.2) == "S34W001"


def test_hgt_bilinear_interpolation(tmp_path):
    # tile sintetico: quota = riga (0 a nord … 3600 a sud), così la quota dipende solo dalla lat
    rows = np.arange(HGT_SIZE, dtype=">i2").reshape(-1, 1)
    grid = np.repeat(rows, HGT_SIZE, axis=1)
    with gzip.open(tmp_path / "N46E011.hgt.gz", "wb") as fh:
        fh.write(grid.tobytes())
    dem = HgtDem(tmp_path)
    assert dem.elevation(11.5, 46.9999999) == pytest.approx(0, abs=1e-3)
    assert dem.elevation(11.5, 46.0) == pytest.approx(3600)
    assert dem.elevation(11.123, 46.5) == pytest.approx(1800)
    assert dem.elevation(11.9, 46.25 + 0.5 / 3600) == pytest.approx(2699.5)
    assert dem.sample([(11.5, 46.75), (11.5, 46.25)]) == [pytest.approx(900), pytest.approx(2700)]


def test_missing_tile_without_client_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        HgtDem(tmp_path).elevation(11.5, 46.5)
