"""Test dei tempi di percorrenza: fixture golden Val d'Inferno (SPEC §2 e §8)."""

from __future__ import annotations

import json

import pytest

from cordata_ingest.config import repo_root
from cordata_ingest.timing import din33466_hours, format_hours


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
    # pianura: conta solo l'orizzontale
    assert din33466_hours(8, 0, 0) == pytest.approx(2.0)
    # salita ripida e corta: prevale il verticale (600/300 = 2 h) + metà dell'orizzontale (0,25 h)
    assert din33466_hours(2, 600, 0) == pytest.approx(2.25)
    # discesa: 500 m/h
    assert din33466_hours(0, 0, 1000) == pytest.approx(2.0)


def test_format_hours_rounds_to_five_minutes():
    assert format_hours(7.004) == "7:00"
    assert format_hours(2.26) == "2:15"
    assert format_hours(0.99) == "1:00"
    assert format_hours(3.5, round_to_min=1) == "3:30"
