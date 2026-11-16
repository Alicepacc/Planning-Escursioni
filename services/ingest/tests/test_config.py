"""Test della configurazione delle aree."""

from __future__ import annotations

import pytest

from cordata_ingest.config import PROJECT_URL, Area, areas, lonlat_to_mercator, user_agent


def test_areas_are_loaded_from_yaml():
    all_areas = areas()
    assert {"pilot", "lagorai", "val_inferno"} <= set(all_areas)
    lagorai = all_areas["lagorai"]
    assert lagorai.bbox == (11.40, 46.05, 11.62, 46.16)
    assert lagorai.bbox_str == "11.4,46.05,11.62,46.16"
    assert lagorai.overpass_bbox == "46.05,11.4,46.16,11.62"


def test_mercator_conversion_matches_known_values():
    x, y = lonlat_to_mercator(11.40, 46.05)
    assert x == pytest.approx(1269042, abs=2)
    assert y == pytest.approx(5788365, abs=2)
    area = Area(key="t", name="t", bbox=(11.40, 46.05, 11.62, 46.16))
    assert area.mercator_bbox == "1269042,5788365,1293532,5806027"


def test_user_agent_uses_project_url_unless_overridden(monkeypatch):
    monkeypatch.delenv("CORDATA_CONTACT", raising=False)
    assert user_agent().startswith("Cordata/") and user_agent().endswith(f"+{PROJECT_URL})")
    monkeypatch.setenv("CORDATA_CONTACT", "https://example.org/contatti")
    assert "+https://example.org/contatti)" in user_agent() and PROJECT_URL not in user_agent()
