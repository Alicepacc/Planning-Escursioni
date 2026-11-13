"""Infrastruttura comune degli script di verifica delle fonti (SPEC §6, Fase 0).

Ogni fonte ha un modulo `cordata_ingest.probes.<id>` che espone:

    PROBE_ID = "osm2cai"
    def run(ctx: ProbeContext) -> ProbeResult: ...

Lo script scarica un piccolo campione dell'area Lagorai, lo salva in `data/samples/<id>/`
(non versionato) e restituisce un `ProbeResult` con i controlli eseguiti. Il runner
(`python -m cordata_ingest.probes`) scrive i risultati in `reports/phase0/sources/<id>.json`.

Regola: niente valori inventati. Se un controllo non si può fare, va registrato come fallito
con il motivo reale (stato HTTP, errore di rete, campo assente).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config import Area, areas, data_dir
from ..http import Fetched, FetchError, PoliteClient, RobotsDisallowed

# stati ammessi nel registro docs/data-sources.md
STATUS_OK = "ok"  # tutto verificato, utilizzabile
STATUS_PARTIAL = "parziale"  # utilizzabile con limiti o controlli falliti non bloccanti
STATUS_BLOCKED = "non_raggiungibile"  # non verificabile da questo ambiente
STATUS_TODO = "da_verificare"  # serve un'azione manuale (licenza, registrazione…)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    url: str | None = None


@dataclass
class ProbeResult:
    source_id: str
    name: str
    status: str = STATUS_TODO
    reachable: bool = False
    format: str = ""
    license: str = ""
    license_url: str = ""
    limits: str = ""
    update_frequency: str = ""
    checks: list[Check] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S%z"))

    def check(self, name: str, ok: bool, detail: str = "", url: str | None = None) -> bool:
        self.checks.append(Check(name=name, ok=bool(ok), detail=detail, url=url))
        return bool(ok)

    def finish(self, status: str | None = None) -> ProbeResult:
        """Deriva `reachable` e lo stato dai controlli (salvo stato esplicito)."""
        self.reachable = any(c.ok for c in self.checks)
        if status:
            self.status = status
        elif not self.reachable:
            self.status = STATUS_BLOCKED
        else:
            self.status = STATUS_OK if all(c.ok for c in self.checks) else STATUS_PARTIAL
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProbeContext:
    client: PoliteClient
    lagorai: Area
    pilot: Area
    samples_root: Path

    def samples_dir(self, source_id: str) -> Path:
        path = self.samples_root / source_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_sample(self, source_id: str, filename: str, content: bytes | str | Any) -> str:
        """Salva un campione e ne restituisce il percorso relativo alla cartella dati."""
        path = self.samples_dir(source_id) / filename
        if isinstance(content, bytes):
            path.write_bytes(content)
        elif isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
        return str(path.relative_to(data_dir()))

    def try_get(self, result: ProbeResult, name: str, url: str, **kwargs: Any) -> Fetched | None:
        """GET che registra da solo l'esito come `Check`; None se la risposta non è 2xx."""
        try:
            res = self.client.get(url, **kwargs)
        except RobotsDisallowed:
            result.check(name, False, "vietato da robots.txt", url)
            return None
        except FetchError as exc:
            result.check(name, False, f"errore di rete: {exc.reason}", url)
            return None
        size = len(res.content)
        ctype = res.header("content-type", "") or ""
        result.check(name, res.ok, f"HTTP {res.status}, {size} byte, {ctype}", res.url)
        return res if res.ok else None


def default_context(client: PoliteClient | None = None) -> ProbeContext:
    all_areas = areas()
    return ProbeContext(
        client=client or PoliteClient(),
        lagorai=all_areas["lagorai"],
        pilot=all_areas["pilot"],
        samples_root=data_dir() / "samples",
    )


ProbeFn = Callable[[ProbeContext], ProbeResult]
