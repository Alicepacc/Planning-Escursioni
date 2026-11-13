"""Script di verifica delle fonti dati (SPEC §6). Vedi `base.py` per il contratto."""

from __future__ import annotations

import importlib
import pkgutil

from .base import ProbeFn

_SKIP = {"base", "__main__"}


def discover() -> dict[str, ProbeFn]:
    """Trova tutti i moduli di verifica: {PROBE_ID: run}."""
    found: dict[str, ProbeFn] = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name in _SKIP or info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        probe_id = getattr(module, "PROBE_ID", None)
        run = getattr(module, "run", None)
        if probe_id and callable(run):
            found[probe_id] = run
    return dict(sorted(found.items()))
