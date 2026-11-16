"""Test della sincronizzazione incrementale OSM2CAI (nessuna chiamata di rete)."""

from __future__ import annotations

import json

import httpx

from cordata_ingest.http import PoliteClient
from cordata_ingest.osm2cai.sync import Osm2caiStore, RemoteEntry, plan, sync


def feature(rid: str, ref: str) -> dict:
    return {
        "type": "Feature",
        "properties": {"id": int(rid), "ref": ref, "sda": 4},
        "geometry": {"type": "MultiLineString", "coordinates": [[[11.5, 46.1], [11.51, 46.11]]]},
    }


class FakeOsm2cai:
    """API finta: indici per regione/sda e dettagli, con contatori delle richieste."""

    def __init__(self, indexes: dict[str, dict[str, str]], broken: set[str] | None = None):
        self.indexes = indexes
        self.broken = broken or set()
        self.detail_calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        parts = request.url.path.strip("/").split("/")
        if parts[2] == "hiking-routes" and parts[3] == "region":
            return httpx.Response(200, json=self.indexes.get(f"{parts[4]}/{parts[5]}", {}))
        if parts[2] == "hiking-route":
            rid = parts[3]
            self.detail_calls.append(rid)
            if rid in self.broken:
                return httpx.Response(500, text="Server Error")
            return httpx.Response(200, json=feature(rid, f"ref{rid}"))
        return httpx.Response(404)


def client_for(api: FakeOsm2cai, tmp_path) -> PoliteClient:
    return PoliteClient(
        cache_dir=tmp_path / "cache",
        ua="Cordata-test/0",
        transport=httpx.MockTransport(api),
        respect_robots=False,
        max_retries=0,
        min_interval=0,
        host_intervals={"osm2cai.cai.it": 0},
        sleep=lambda s: None,
    )


def test_plan_classifies_new_updated_unchanged_removed():
    remote = {
        "1": RemoteEntry("2026-01-01", 4, ["C"]),
        "2": RemoteEntry("2026-02-02", 4, ["C"]),
        "3": RemoteEntry("2026-03-03", 3, ["B"]),
    }
    local = {
        "1": {"updated_at": "2026-01-01"},  # invariato
        "2": {"updated_at": "2025-12-31"},  # modificato
        "9": {"updated_at": "2025-01-01"},  # sparito dagli indici
    }
    result = plan(remote, local, files={"1", "2", "9"})
    assert result.unchanged == ["1"]
    assert result.to_fetch == ["2", "3"]
    assert result.removed == ["9"]


def test_plan_refetches_when_local_file_is_missing():
    remote = {"1": RemoteEntry("2026-01-01", 4, ["C"])}
    result = plan(remote, {"1": {"updated_at": "2026-01-01"}}, files=set())
    assert result.to_fetch == ["1"]


def test_first_sync_then_incremental(tmp_path):
    api = FakeOsm2cai({"C/4": {"10": "t1", "11": "t1"}, "B/4": {"11": "t1", "12": "t1"}})
    store = Osm2caiStore(tmp_path / "osm2cai")
    report = sync(client_for(api, tmp_path), store, regions=["C", "B"], sdas=[4])

    assert report.remote_total == 3 and report.fetched == 3 and not report.errors
    assert sorted(api.detail_calls) == ["10", "11", "12"]
    assert store.routes["11"]["regions"] == ["C", "B"], "un sentiero di confine sta in due regioni"
    saved = json.loads((tmp_path / "osm2cai" / "routes" / "12.geojson").read_text())
    assert saved["properties"]["ref"] == "ref12"

    # secondo giro: cambia solo il sentiero 11, il 12 sparisce, arriva il 13
    api.indexes = {"C/4": {"10": "t1", "11": "t2"}, "B/4": {"11": "t2", "13": "t1"}}
    api.detail_calls.clear()
    store = Osm2caiStore(tmp_path / "osm2cai")  # riletto dal disco
    report = sync(client_for(api, tmp_path), store, regions=["C", "B"], sdas=[4])

    assert sorted(api.detail_calls) == ["11", "13"]
    assert report.unchanged == 1 and report.removed == 1 and report.fetched == 2
    assert not (tmp_path / "osm2cai" / "routes" / "12.geojson").exists()


def test_failed_detail_is_retried_next_time(tmp_path):
    api = FakeOsm2cai({"C/4": {"20": "t1", "21": "t1"}}, broken={"21"})
    store = Osm2caiStore(tmp_path / "osm2cai")
    report = sync(client_for(api, tmp_path), store, regions=["C"], sdas=[4])
    assert report.fetched == 1 and report.errors == {"21": "HTTP 500"}
    assert "21" not in store.routes

    api.broken.clear()
    api.detail_calls.clear()
    report = sync(client_for(api, tmp_path), Osm2caiStore(tmp_path / "osm2cai"), ["C"], [4])
    assert api.detail_calls == ["21"] and report.fetched == 1 and not report.errors


def test_max_fetch_leaves_the_rest_pending(tmp_path):
    api = FakeOsm2cai({"C/4": {str(i): "t1" for i in range(1, 6)}})
    store = Osm2caiStore(tmp_path / "osm2cai")
    report = sync(client_for(api, tmp_path), store, regions=["C"], sdas=[4], max_fetch=2)
    assert report.fetched == 2 and report.pending == 3
    report = sync(client_for(api, tmp_path), Osm2caiStore(tmp_path / "osm2cai"), ["C"], [4])
    assert report.fetched == 3 and report.unchanged == 2 and report.pending == 0
