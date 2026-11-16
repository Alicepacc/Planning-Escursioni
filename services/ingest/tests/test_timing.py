"""Test dei tempi di percorrenza: fixture golden Val d'Inferno e casi del modello CAI (SPEC §8)."""

from __future__ import annotations

import json

import pytest

from cordata_ingest.config import repo_root
from cordata_ingest.timing import (
    SWISS_MAX_SLOPE_PCT,
    din33466_hours,
    format_hours,
    personal_minutes,
    swiss_minutes_per_km,
    swiss_segment_minutes,
    swiss_track_minutes,
)


def test_din33466_golden_fixture_is_seven_hours():
    fixture = json.loads(
        (repo_root() / "fixtures" / "golden" / "val-d-inferno.json").read_text(encoding="utf-8")
    )
    hours = din33466_hours(
        fixture["distanza_km"], fixture["dislivello_salita_m"], fixture["dislivello_discesa_m"]
    )
    assert hours == pytest.approx(7.0, abs=0.01)
    assert format_hours(hours) == fixture["durata_dichiarata"] == "7:00"


def test_din33466_takes_the_larger_component_plus_half_the_smaller():
    assert din33466_hours(8, 0, 0) == pytest.approx(2.0)
    assert din33466_hours(2, 600, 0) == pytest.approx(2.25)
    assert din33466_hours(0, 0, 1000) == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("height_diff_m", "expected_min", "tolerance"),
    [
        (100, 20, 0.5),  # SPEC §8: +100 m su 1 km ≈ 20 min
        (300, 49, 0.5),  # +300 m ≈ 49 min
        (-100, 14, 0.5),  # −100 m ≈ 14 min
        (-300, 27.5, 0.5),  # −300 m ≈ 27-28 min
    ],
)
def test_cai_swiss_model_spec_cases_on_one_km(height_diff_m, expected_min, tolerance):
    assert swiss_segment_minutes(1000, height_diff_m) == pytest.approx(expected_min, abs=tolerance)


def test_cai_swiss_model_flat_speed_is_4_2_km_h():
    # manuale ASTRA «Signalisation Wanderwege» §3.1.2: 4,2 km/h in piano
    assert 60 / swiss_minutes_per_km(0) == pytest.approx(4.2, abs=0.01)


def test_cai_swiss_model_reproduces_official_diagram_apex():
    # diagramma ufficiale: l'isocrona dei 60 min ha l'apice a circa 4,53 km con −218 m
    # (punto più lontano raggiungibile in un'ora, in leggera discesa)
    assert swiss_segment_minutes(4530, -218) == pytest.approx(60, abs=1)
    best = min(range(-30, 31), key=swiss_minutes_per_km)
    assert -10 <= best <= -3, "la pendenza più veloce è una leggera discesa"


def test_cai_swiss_model_is_clamped_beyond_40_percent():
    assert swiss_minutes_per_km(60) == swiss_minutes_per_km(SWISS_MAX_SLOPE_PCT)
    assert swiss_minutes_per_km(-80) == swiss_minutes_per_km(-SWISS_MAX_SLOPE_PCT)


def test_track_time_sums_segments_and_flags_steep_parts():
    distances = [0, 500, 1000, 1500, 2000]
    flat = swiss_track_minutes(distances, [1000] * 5, segment_m=500)
    assert flat.minutes == pytest.approx(2 * 14.271, abs=0.01) and flat.steep_m == 0
    steep = swiss_track_minutes([0, 100, 200], [1000, 1060, 1120], segment_m=100)
    assert steep.steep_m == pytest.approx(200)
    with pytest.raises(ValueError):
        swiss_track_minutes([0, 1], [1])


def test_track_time_handles_trivial_inputs():
    assert swiss_track_minutes([], []).minutes == 0
    assert swiss_track_minutes([0], [1000]).minutes == 0


def test_personal_factors():
    assert personal_minutes(100) == 100
    assert personal_minutes(100, fitness=0.7, group=1.5, stops=1.2) == pytest.approx(126)
    with pytest.raises(ValueError):
        personal_minutes(100, fitness=2.0)
    with pytest.raises(ValueError):
        personal_minutes(100, stops=0.9)


def test_format_hours_rounds_to_five_minutes():
    assert format_hours(7.004) == "7:00"
    assert format_hours(2.26) == "2:15"
    assert format_hours(0.99) == "1:00"
    assert format_hours(3.5, round_to_min=1) == "3:30"
