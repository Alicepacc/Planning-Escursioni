"""Deduplica degli itinerari (SPEC §7.5).

Lo stesso itinerario proposto in anni diversi o da sezioni diverse diventa un **itinerario
canonico** con più proposte («proposta da CAI Bolzano il 26/07/2026»). Due tracce sono:

- **stesso itinerario** se la distanza di Hausdorff (simmetrica) è ≤ 300 m e le lunghezze
  differiscono al massimo del 25%; la distanza di Fréchet discreta (anche sulla traccia
  invertita) conferma l'ordine dei passaggi;
- **variante** se una traccia corre quasi tutta lungo l'altra (Hausdorff orientata della più
  corta verso la più lunga ≤ 300 m), ma non sono la stessa: per esempio un'andata e ritorno
  che ripercorre metà di un anello.

Le tracce si confrontano in metri, su un piano locale, dopo semplificazione e ricampionamento
ogni 50 m: il calcolo resta piccolo anche per migliaia di coppie.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

SAME_HAUSDORFF_M = 300.0
SAME_LENGTH_RATIO = 1.25
VARIANT_DIRECTED_M = 300.0
STEP_M = 50.0


def to_xy(coords: Sequence[Sequence[float]], lat0: float) -> list[tuple[float, float]]:
    kx = 111_320.0 * math.cos(math.radians(lat0))
    return [(c[0] * kx, c[1] * 110_950.0) for c in coords]


def length(points: Sequence[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in itertools.pairwise(points))


def resample(
    points: Sequence[tuple[float, float]], step: float = STEP_M
) -> list[tuple[float, float]]:
    """Punti equidistanti lungo la linea (il primo e l'ultimo inclusi)."""
    if len(points) < 2:
        return list(points)
    out = [points[0]]
    carry = 0.0
    for a, b in itertools.pairwise(points):
        seg = math.dist(a, b)
        if seg == 0:
            continue
        pos = step - carry
        while pos <= seg:
            t = pos / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            pos += step
        carry = seg - (pos - step)
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def directed_hausdorff(a: Sequence[tuple[float, float]], b: Sequence[tuple[float, float]]) -> float:
    """Massima distanza di un punto di `a` dal punto più vicino di `b`."""
    worst = 0.0
    for p in a:
        best = min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in b)
        worst = max(worst, best)
    return math.sqrt(worst)


def frechet(a: Sequence[tuple[float, float]], b: Sequence[tuple[float, float]]) -> float:
    """Distanza di Fréchet discreta (programmazione dinamica, memoria lineare)."""
    if not a or not b:
        return math.inf
    prev = [0.0] * len(b)
    for i, p in enumerate(a):
        cur = [0.0] * len(b)
        for j, q in enumerate(b):
            d = math.dist(p, q)
            if i == 0 and j == 0:
                cur[j] = d
            elif i == 0:
                cur[j] = max(cur[j - 1], d)
            elif j == 0:
                cur[j] = max(prev[0], d)
            else:
                cur[j] = max(min(prev[j], prev[j - 1], cur[j - 1]), d)
        prev = cur
    return prev[-1]


@dataclass
class Comparison:
    hausdorff_m: float
    directed_short_to_long_m: float
    frechet_m: float
    length_ratio: float
    relation: str | None  # "stesso", "variante" o None


def compare(a_coords: Sequence[Sequence[float]], b_coords: Sequence[Sequence[float]]) -> Comparison:
    lat0 = (a_coords[0][1] + b_coords[0][1]) / 2
    a = resample(to_xy(a_coords, lat0))
    b = resample(to_xy(b_coords, lat0))
    la, lb = length(a), length(b)
    h_ab, h_ba = directed_hausdorff(a, b), directed_hausdorff(b, a)
    hausdorff = max(h_ab, h_ba)
    ratio = max(la, lb) / max(min(la, lb), 1.0)
    short_to_long = h_ab if la <= lb else h_ba
    fr = (
        min(frechet(a, b), frechet(a, list(reversed(b))))
        if hausdorff <= SAME_HAUSDORFF_M * 2
        else math.inf
    )
    if hausdorff <= SAME_HAUSDORFF_M and ratio <= SAME_LENGTH_RATIO:
        relation: str | None = "stesso"
    elif short_to_long <= VARIANT_DIRECTED_M:
        relation = "variante"
    else:
        relation = None
    return Comparison(
        round(hausdorff),
        round(short_to_long),
        round(fr) if fr != math.inf else -1,
        round(ratio, 2),
        relation,
    )


@dataclass
class Group:
    canonical: str
    members: list[str] = field(default_factory=list)


def bbox_close(a: Sequence[float], b: Sequence[float], margin: float = 0.01) -> bool:
    return not (
        a[2] + margin < b[0] or b[2] + margin < a[0] or a[3] + margin < b[1] or b[3] + margin < a[1]
    )


def group(tracks: dict[str, dict[str, Any]]) -> tuple[list[Group], list[dict[str, Any]]]:
    """Raggruppa gli stessi itinerari; elenca le varianti. `tracks[id]` ha `coords`, `bbox`,
    `verified` e `date`: il canonico è una traccia verificata, la più recente."""
    ids = sorted(tracks)
    parent = {i: i for i in ids}

    def root(i: str) -> str:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    relations = []
    for x, i in enumerate(ids):
        for j in ids[x + 1 :]:
            if not bbox_close(tracks[i]["bbox"], tracks[j]["bbox"]):
                continue
            c = compare(tracks[i]["coords"], tracks[j]["coords"])
            if c.relation:
                relations.append({"a": i, "b": j, **c.__dict__})
            if c.relation == "stesso":
                parent[root(j)] = root(i)
    clusters: dict[str, list[str]] = {}
    for i in ids:
        clusters.setdefault(root(i), []).append(i)
    groups = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        best = max(
            members,
            key=lambda m: (bool(tracks[m].get("verified")), str(tracks[m].get("date") or "")),
        )
        groups.append(Group(best, sorted(members)))
    return groups, relations
