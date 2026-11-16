"""Stima dei tempi di percorrenza (SPEC §8).

Due modelli:

1. **CAI / Sentieri Svizzeri** (predefinito per i sentieri). Il Quaderno n. 1 «Sentieri» del CAI
   (p. 51) rimanda, per il calcolo preciso, al diagramma dei tempi dell'Ente Svizzero Pro
   Sentieri (Schweizer Wanderwege, © 1986, riprodotto anche nel manuale ASTRA «Signalisation
   Wanderwege», 2013, p. 66). Il diagramma è la rappresentazione grafica di un polinomio nella
   pendenza: tempo [min] = distanza orizzontale [km] × f(pendenza %), con f(0) = 14,271 min/km
   (4,2 km/h in piano, come dichiarato nel manuale ASTRA §3.1.2). I coefficienti sono verificati
   contro il diagramma ufficiale digitalizzato
   (vedi `docs/decisions/0007-modelli-dei-tempi-e-delle-quote.md`).
   Il manuale ASTRA esclude i tratti con pendenza oltre il 40%: lì il tempo va stimato a parte.
2. **DIN 33466** (usata da DAV/AVS), come confronto.

Entrambi restituiscono il **tempo netto**, senza soste.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# Coefficienti C0…C15 del polinomio dei Sentieri Svizzeri; pendenza in percento, risultato in
# minuti per km di distanza orizzontale.
SWISS_COEFFICIENTS: tuple[float, ...] = (
    14.271,
    3.6992e-1,
    2.5922e-2,
    -1.4384e-3,
    3.2105e-5,
    8.1542e-6,
    -9.0261e-8,
    -2.0757e-8,
    1.0192e-10,
    2.8588e-11,
    -5.7466e-14,
    -2.1842e-14,
    1.5176e-17,
    8.6894e-18,
    -1.3584e-21,
    -1.4026e-21,
)
SWISS_MAX_SLOPE_PCT = 40.0  # oltre, il manuale ASTRA chiede una stima «per esperienza»

DEFAULT_STOPS_FACTOR = 1.20  # tempo con soste: +20% (SPEC §8: +15-20%; fixture: 5:50 × 1,2 ≈ 7:00)


def swiss_minutes_per_km(slope_pct: float) -> float:
    """Minuti per km di distanza orizzontale alla pendenza data (in percento, + = salita).

    La pendenza viene limitata a ±40%: il polinomio non è definito oltre e il manuale svizzero
    prevede in quei casi una stima sul terreno.
    """
    s = max(-SWISS_MAX_SLOPE_PCT, min(SWISS_MAX_SLOPE_PCT, slope_pct))
    total = 0.0
    for coefficient in reversed(SWISS_COEFFICIENTS):  # schema di Horner
        total = total * s + coefficient
    return total


def swiss_segment_minutes(horizontal_m: float, height_diff_m: float) -> float:
    """Tempo netto di un tratto con distanza orizzontale e dislivello (+ salita, − discesa)."""
    if horizontal_m <= 0:
        return 0.0
    return horizontal_m / 1000 * swiss_minutes_per_km(100 * height_diff_m / horizontal_m)


@dataclass(frozen=True)
class TrackTime:
    minutes: float
    steep_m: float  # metri di traccia con pendenza oltre il 40% (tempo poco affidabile)


def swiss_track_minutes(
    distances_m: Sequence[float], elevations_m: Sequence[float], segment_m: float = 100.0
) -> TrackTime:
    """Tempo netto di una traccia, sommando tratti di circa `segment_m` metri.

    `distances_m` è la distanza orizzontale progressiva di ogni punto, `elevations_m` la quota.
    La lunghezza dei tratti conta, perché il polinomio non è lineare: è un parametro calibrato
    contro i tempi ufficiali OSM2CAI (ADR 0007).
    """
    if len(distances_m) != len(elevations_m):
        raise ValueError("distanze e quote devono avere la stessa lunghezza")
    if len(distances_m) < 2:
        return TrackTime(0.0, 0.0)
    minutes = steep = 0.0
    start = 0
    last = len(distances_m) - 1
    for i in range(1, len(distances_m)):
        span = distances_m[i] - distances_m[start]
        if span >= segment_m or i == last:
            dh = elevations_m[i] - elevations_m[start]
            minutes += swiss_segment_minutes(span, dh)
            if span > 0 and abs(100 * dh / span) > SWISS_MAX_SLOPE_PCT:
                steep += span
            start = i
    return TrackTime(minutes, steep)


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


def personal_minutes(
    net_minutes: float, fitness: float = 1.0, group: float = 1.0, stops: float = 1.0
) -> float:
    """Applica il fattore di allenamento (0,7-1,4), il fattore gruppo e le soste (SPEC §8)."""
    if not 0.7 <= fitness <= 1.4:
        raise ValueError("il fattore di allenamento va da 0,7 a 1,4")
    if group < 1.0 or stops < 1.0:
        raise ValueError("i fattori gruppo e soste non possono ridurre il tempo")
    return net_minutes * fitness * group * stops


def format_hours(hours: float, round_to_min: int = 5) -> str:
    """Formatta le ore come `h:mm`, arrotondando ai `round_to_min` minuti."""
    minutes = round(hours * 60 / round_to_min) * round_to_min
    return f"{minutes // 60}:{minutes % 60:02d}"
