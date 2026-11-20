"""Punteggio di affidabilità 0–100 di un'escursione ricostruita da una locandina (ADR 0015).

Si pubblica solo da 80 in su. Il punteggio unisce tre parti:

- **traccia** (65%): quanto la traccia ricostruita coincide con la locandina: distanza, salita,
  quota massima e, se la locandina cita sentieri, quanta traccia ci passa. Ogni confronto vale
  pieno dentro la tolleranza della verifica e scende fino a zero più in là. Con un solo numero
  da confrontare la parte non supera 0,6 (resta sotto soglia); con due 0,9: un confronto solo
  può coincidere per caso.
- **punti** (20%): quanti punti della locandina sono stati trovati sulla carta e, dove la
  locandina dà la quota, se quella del luogo trovato torna.
- **lettura** (15%): la sicurezza del parser sui campi che servono (titolo, difficoltà, numeri).

Una ricostruzione fallita vale 0: non si pubblica.
"""

from __future__ import annotations

from typing import Any

THRESHOLD = 80

WEIGHTS = {"traccia": 0.65, "punti": 0.20, "lettura": 0.15}


def _ramp(value: float, full: float, zero: float) -> float:
    """1 fino a `full`, 0 da `zero` in su, lineare in mezzo (valori assoluti)."""
    v = abs(value)
    if v <= full:
        return 1.0
    if v >= zero:
        return 0.0
    return 1.0 - (v - full) / (zero - full)


def track_part(track: dict[str, Any]) -> tuple[float, list[str]]:
    checks = track.get("checks") or {}
    parts: list[tuple[float, float]] = []  # (valore, peso)
    notes: list[str] = []
    if "distanza" in checks:
        parts.append((_ramp(checks["distanza"]["scarto"], 0.10, 0.35), 1.0))
    if "salita" in checks:
        parts.append((_ramp(checks["salita"]["scarto"], 0.15, 0.45), 1.0))
    if "quota_max" in checks:
        parts.append((_ramp(checks["quota_max"]["scarto_m"], 50, 250), 0.8))
    numeric = len(parts)
    share = track.get("on_cited_share")
    if share is not None and track.get("cited_refs"):
        parts.append((min(1.0, max(0.0, (share - 0.15) / 0.45)), 0.6))
    if not numeric:
        notes.append("nessun numero della locandina da confrontare")
        return 0.0, notes
    value = sum(v * w for v, w in parts) / sum(w for _, w in parts)
    cap = {1: 0.6, 2: 0.9}.get(numeric, 1.0)
    if value > cap:
        notes.append(f"{numeric} confronto/i soltanto: parte traccia al massimo {cap}")
    return min(value, cap), notes


def points_part(track: dict[str, Any]) -> float:
    points = track.get("points") or []
    if not points:
        return 0.0
    found = [p for p in points if p.get("lon") is not None]
    found_share = len(found) / len(points)
    checked = [
        p for p in found if p.get("quota_dichiarata") and (p.get("quota_osm") or p.get("quota_dem"))
    ]
    if not checked:
        return found_share * 0.85
    agree = sum(
        abs(p["quota_dichiarata"] - (p.get("quota_osm") or p.get("quota_dem"))) <= 80
        for p in checked
    ) / len(checked)
    return found_share * (0.6 + 0.4 * agree)


READING_FIELDS = ("titolo", "difficolta", "distanza_km", "salita_m", "durata", "quota_max_m")


def reading_part(parsed: dict[str, Any] | None) -> float:
    """Media della sicurezza del parser sui campi utili (un campo assente vale 0)."""
    if not parsed:
        return 1.0  # campi rivisti a mano sulla locandina: lettura sicura
    values = []
    for field in READING_FIELDS:
        f = parsed.get(field) or {}
        values.append(float(f.get("confidence") or 0) if f.get("value") is not None else 0.0)
    # bastano titolo, difficoltà e due numeri su quattro: la media si fa sui migliori quattro
    values.sort(reverse=True)
    return sum(values[:4]) / 4


def score(track: dict[str, Any], parsed: dict[str, Any] | None = None) -> dict[str, Any]:
    """Punteggio 0–100 con le sue parti e le note per la pagina di revisione."""
    if track.get("status") == "fallita" or not track.get("coords"):
        return {
            "punteggio": 0,
            "parti": {"traccia": 0.0, "punti": 0.0, "lettura": 0.0},
            "note": ["ricostruzione fallita"],
            "pubblicabile": False,
        }
    t, notes = track_part(track)
    p = points_part(track)
    r = reading_part(parsed)
    value = round(100 * (WEIGHTS["traccia"] * t + WEIGHTS["punti"] * p + WEIGHTS["lettura"] * r))
    return {
        "punteggio": value,
        "parti": {"traccia": round(t, 3), "punti": round(p, 3), "lettura": round(r, 3)},
        "note": notes,
        "pubblicabile": value >= THRESHOLD,
    }
