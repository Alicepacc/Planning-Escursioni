"""Sincronizzazione incrementale dei sentieri OSM2CAI (SPEC §6.1).

1. Scarica gli indici `{id: updated_at}` per regione e stato di accatastamento (`sda`).
2. Li confronta con lo stato locale: scarica solo i sentieri nuovi o modificati, uno alla volta
   e con pausa (l'API dichiara `X-RateLimit-Limit: 60` al minuto).
3. Salva ogni sentiero come GeoJSON in `<out>/routes/<id>.geojson` e lo stato in
   `<out>/state.json`, aggiornato a blocchi: un'interruzione non fa perdere il lavoro fatto.

Si usano gli indici per regione e non per bbox perché l'indice per bbox esclude i sentieri che
escono dal riquadro (verificato nella Fase 0). Codici regione CAI: C = Trentino-Alto Adige,
B = Veneto.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..http import FetchError, PoliteClient

log = logging.getLogger(__name__)

API = "https://osm2cai.cai.it/api/v2"
HOST = "osm2cai.cai.it"
MIN_INTERVAL_S = 1.2  # 50 richieste al minuto, sotto il limite dichiarato di 60
SAVE_EVERY = 25


@dataclass
class RemoteEntry:
    updated_at: str
    sda: int
    regions: list[str]


@dataclass
class SyncPlan:
    to_fetch: list[str]
    unchanged: list[str]
    removed: list[str]


@dataclass
class SyncReport:
    started_at: str
    finished_at: str = ""
    indexes: dict[str, int] = field(default_factory=dict)
    remote_total: int = 0
    fetched: int = 0
    unchanged: int = 0
    removed: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    pending: int = 0  # sentieri da scaricare rimasti per il limite `max_fetch`


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def fetch_indexes(
    client: PoliteClient, regions: Iterable[str], sdas: Iterable[int], report: SyncReport
) -> dict[str, RemoteEntry]:
    """Unisce gli indici di più regioni e stati; un sentiero può comparire in più regioni."""
    remote: dict[str, RemoteEntry] = {}
    for region in regions:
        for sda in sdas:
            url = f"{API}/hiking-routes/region/{region}/{sda}"
            data = client.get(url, ttl=None).raise_for_status().json()
            report.indexes[f"{region}/{sda}"] = len(data)
            for rid, updated_at in data.items():
                entry = remote.get(rid)
                if entry is None:
                    remote[rid] = RemoteEntry(updated_at=updated_at, sda=sda, regions=[region])
                elif region not in entry.regions:
                    entry.regions.append(region)
    return remote


def plan(
    remote: dict[str, RemoteEntry], local: dict[str, dict[str, Any]], files: set[str]
) -> SyncPlan:
    """Decide cosa scaricare: nuovi, modificati, o senza file locale (es. download fallito)."""
    to_fetch, unchanged = [], []
    for rid, entry in sorted(remote.items(), key=lambda kv: int(kv[0])):
        known = local.get(rid)
        if known and known.get("updated_at") == entry.updated_at and rid in files:
            unchanged.append(rid)
        else:
            to_fetch.append(rid)
    removed = sorted((rid for rid in local if rid not in remote), key=int)
    return SyncPlan(to_fetch=to_fetch, unchanged=unchanged, removed=removed)


class Osm2caiStore:
    """Stato e file locali della sincronizzazione."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.routes_dir = self.root / "routes"
        self.state_path = self.root / "state.json"
        self.routes_dir.mkdir(parents=True, exist_ok=True)
        self.state: dict[str, Any] = (
            json.loads(self.state_path.read_text(encoding="utf-8"))
            if self.state_path.exists()
            else {"routes": {}, "runs": []}
        )

    @property
    def routes(self) -> dict[str, dict[str, Any]]:
        return self.state["routes"]

    def files(self) -> set[str]:
        return {p.stem for p in self.routes_dir.glob("*.geojson")}

    def route_path(self, rid: str) -> Path:
        return self.routes_dir / f"{rid}.geojson"

    def put(self, rid: str, feature: dict[str, Any], entry: RemoteEntry) -> None:
        tmp = self.route_path(rid).with_suffix(".tmp")
        tmp.write_text(json.dumps(feature, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.route_path(rid))
        self.routes[rid] = {**asdict(entry), "fetched_at": _now()}

    def drop(self, rid: str) -> None:
        self.route_path(rid).unlink(missing_ok=True)
        self.routes.pop(rid, None)

    def save(self) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=0), encoding="utf-8")
        tmp.replace(self.state_path)

    def features(self) -> Iterable[dict[str, Any]]:
        for rid in sorted(self.routes, key=int):
            path = self.route_path(rid)
            if path.exists():
                yield json.loads(path.read_text(encoding="utf-8"))


def sync(
    client: PoliteClient,
    store: Osm2caiStore,
    regions: Iterable[str] = ("C", "B"),
    sdas: Iterable[int] = (3, 4),
    max_fetch: int | None = None,
) -> SyncReport:
    report = SyncReport(started_at=_now())
    client.host_intervals.setdefault(HOST, MIN_INTERVAL_S)
    remote = fetch_indexes(client, list(regions), list(sdas), report)
    report.remote_total = len(remote)
    todo = plan(remote, store.routes, store.files())
    report.unchanged = len(todo.unchanged)

    for rid in todo.removed:
        store.drop(rid)
    report.removed = len(todo.removed)

    batch = todo.to_fetch if max_fetch is None else todo.to_fetch[:max_fetch]
    report.pending = len(todo.to_fetch) - len(batch)
    for n, rid in enumerate(batch, start=1):
        try:
            res = client.get(f"{API}/hiking-route/{rid}", ttl=None)
        except FetchError as exc:
            report.errors[rid] = exc.reason
            continue
        if not res.ok:
            report.errors[rid] = f"HTTP {res.status}"
            continue
        feature = res.json()
        if feature.get("type") != "Feature" or "properties" not in feature:
            report.errors[rid] = "risposta senza Feature GeoJSON"
            continue
        store.put(rid, feature, remote[rid])
        report.fetched += 1
        if n % SAVE_EVERY == 0:
            store.save()
            log.info("osm2cai: %d/%d sentieri scaricati", n, len(batch))
    report.finished_at = _now()
    store.state["runs"] = ([*store.state.get("runs", []), asdict(report)])[-20:]
    store.save()
    return report
