"""Test della difficoltà e dei documenti per le schede (DEM sintetico, niente rete né DB)."""

from __future__ import annotations

import itertools

import pytest

from cordata_ingest.build.documents import (
    DEFAULT_PARAMS,
    index_entry,
    profile_payload,
    stages,
    trail_document,
)
from cordata_ingest.difficulty import cai_from_sac, cai_rank, max_cai, normalize_cai, osmc_color
from cordata_ingest.geo.profile import compute_profile
from cordata_ingest.osm2cai import localized

DEG_PER_KM = 1 / 111.195  # gradi di latitudine per km


class NorthSlopeDem:
    """Quota = 1000 m + 100 m per km verso nord (pendenza costante del 10%)."""

    def sample(self, coords):
        return [1000 + (c[1] - 46.0) / DEG_PER_KM * 100 for c in coords]


def straight_north(km: float, steps: int = 50) -> list[tuple[float, float]]:
    return [(11.5, 46.0 + km * DEG_PER_KM * i / steps) for i in range(steps + 1)]


def test_cai_scale_normalization_and_ranking():
    assert normalize_cai("EEA:PD") == "EEA"
    assert normalize_cai(" ee ") == "EE"
    assert normalize_cai("EAI") is None and normalize_cai(None) is None
    assert cai_rank("T") < cai_rank("E") < cai_rank("EE") < cai_rank("EEA")
    assert max_cai(["E", None, "EE", "T"]) == "EE"
    assert max_cai([None]) is None


def test_sac_scale_mapping_is_indicative():
    assert cai_from_sac("mountain_hiking") == "E"
    assert cai_from_sac("demanding_mountain_hiking") == "EE"
    assert cai_from_sac("alpine_hiking") == "EEA"
    assert cai_from_sac(None, "track") == "T"
    assert cai_from_sac(None, "path") is None, "un sentiero senza sac_scale resta senza stima"


def test_osmc_color():
    assert osmc_color("red:red:white_stripe:332:black") == "red"
    assert osmc_color(None) is None


def test_localized_osm2cai_fields():
    assert localized({"it": "Sentiero della Pace", "de": "Friedensweg"}) == "Sentiero della Pace"
    assert localized({"de": "Friedensweg"}) == "Friedensweg"
    assert localized("332") == "332"
    assert localized("") is None and localized(None) is None


def test_profile_payload_columns_and_cumulative_time():
    prof = compute_profile(straight_north(2), NorthSlopeDem(), DEFAULT_PARAMS)
    payload = profile_payload(prof)
    points = payload["points"]
    assert payload["columns"] == ["dist_m", "ele_m", "lon", "lat", "min"]
    assert points[0][0] == 0 and points[-1][0] == pytest.approx(2000, abs=1)
    assert points[-1][1] == pytest.approx(1200, abs=2)
    # 2 km al 10%: circa 2 × 20 min con il modello CAI
    assert points[-1][4] == pytest.approx(40, abs=1.5)
    assert all(b[4] >= a[4] for a, b in itertools.pairwise(points))


def test_stages_follow_the_track_in_order():
    prof = compute_profile(straight_north(2), NorthSlopeDem(), DEFAULT_PARAMS)
    wps = [
        {"nome": "Partenza", "lon": 11.5, "lat": 46.0},
        {"nome": "Metà", "lon": 11.5005, "lat": 46.0 + 1 * DEG_PER_KM},
        {"nome": "Arrivo", "lon": 11.5, "lat": 46.0 + 2 * DEG_PER_KM},
    ]
    out = stages(prof, wps)
    assert [s["name"] for s in out] == ["Partenza", "Metà", "Arrivo"]
    assert out[1]["dist_km"] == pytest.approx(1.0, abs=0.02)
    assert out[1]["offset_m"] == pytest.approx(39, abs=3), "distanza dal punto chiave alla traccia"
    assert out[0]["cai_min"] < out[1]["cai_min"] < out[2]["cai_min"]


def test_trail_document_keeps_official_values_and_adds_computed():
    feature = {
        "type": "Feature",
        "properties": {
            "id": 12711,
            "relation_id": 7034586,
            "ref": "332",
            "name": {"it": "Sentiero di Rava e di Caldenave"},
            "cai_scale": "E",
            "from": "Bieno",
            "to": "Tedon",
            "sda": 4,
            "distance": 2.0,
            "ascent": 205,
            "descent": 0,
            "duration_forward": 45,
            "duration_backward": 30,
            "issues_status": "percorribile",
            "public_page": "https://osm2cai.cai.it/hiking-route/id/12711",
        },
        "geometry": {"type": "LineString", "coordinates": straight_north(2)},
    }
    doc = trail_document(
        feature, {"network": "lwn", "osmc": "red:red:white_stripe:332:black"}, NorthSlopeDem()
    )
    assert doc["id"] == "12711" and doc["name"] == "Sentiero di Rava e di Caldenave"
    assert doc["official"]["duration_forward_min"] == 45
    assert doc["computed"]["ascent_m"] == pytest.approx(200, abs=10)
    assert doc["computed"]["cai_forward_min"] == pytest.approx(40, abs=2)
    assert doc["difficulty"] == {"cai": "E", "raw": "E"}
    assert doc["color"] == "red" and doc["links"]["osm"].endswith("/7034586")
    entry = index_entry(doc)
    assert entry["min"] == 45 and entry["up"] == 205, "nell'indice prevalgono i valori ufficiali"
