"""Sincronizzazione del catasto sentieri CAI (OSM2CAI / INFOMONT, licenza ODbL)."""

from __future__ import annotations

from typing import Any


def localized(value: Any, lang: str = "it") -> str | None:
    """Alcuni campi OSM2CAI (es. `name`) sono testi o dizionari per lingua: `{"it": "…"}`."""
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        text = value.get(lang) or next((v for v in value.values() if v), None)
        return str(text) if text else None
    return str(value)
