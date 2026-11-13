"""Stima dei tempi di percorrenza (SPEC §8). Fase 0: solo DIN 33466; il modello CAI è in Fase 1."""

from __future__ import annotations


def din33466_hours(
    distance_km: float,
    ascent_m: float,
    descent_m: float,
    *,
    ascent_rate_m_h: float = 300.0,
    descent_rate_m_h: float = 500.0,
    flat_speed_km_h: float = 4.0,
) -> float:
    """Tempo di cammino netto in ore secondo DIN 33466 (usata da DAV/AVS).

    300 m/h in salita, 500 m/h in discesa, 4 km/h in orizzontale; il tempo è il maggiore tra
    tempo orizzontale e tempo verticale più metà del minore.
    """
    horizontal = distance_km / flat_speed_km_h
    vertical = ascent_m / ascent_rate_m_h + descent_m / descent_rate_m_h
    return max(horizontal, vertical) + min(horizontal, vertical) / 2


def format_hours(hours: float, round_to_min: int = 5) -> str:
    """Formatta le ore come `h:mm`, arrotondando ai `round_to_min` minuti."""
    minutes = round(hours * 60 / round_to_min) * round_to_min
    return f"{minutes // 60}:{minutes % 60:02d}"
