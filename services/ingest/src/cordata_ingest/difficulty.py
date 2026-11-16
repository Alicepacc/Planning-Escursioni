"""Difficoltà escursionistica: scala CAI e mappatura indicativa da `sac_scale` (SPEC §8)."""

from __future__ import annotations

# Ordine crescente della scala CAI. EEA comprende le varianti EEA:F, EEA:PD, EEA:D.
CAI_RANK = {"T": 1, "E": 2, "EE": 3, "EEA": 4}
RANK_CAI = {v: k for k, v in CAI_RANK.items()}

# sac_scale → CAI, indicativa: vale solo dove manca cai_scale sulle relazioni (SPEC §8)
SAC_TO_CAI = {
    "hiking": "E",
    "mountain_hiking": "E",
    "demanding_mountain_hiking": "EE",
    "alpine_hiking": "EEA",
    "demanding_alpine_hiking": "EEA",
    "difficult_alpine_hiking": "EEA",
}
# oltre questa soglia il tratto è escluso dal routing di default (alpinistico)
ALPINE_SAC = {"alpine_hiking", "demanding_alpine_hiking", "difficult_alpine_hiking"}


def normalize_cai(value: str | None) -> str | None:
    """`EEA:PD` → `EEA`; valori sconosciuti → None (EAI resta a parte: è invernale)."""
    if not value:
        return None
    base = value.strip().upper().split(":")[0].split(";")[0]
    return base if base in CAI_RANK else None


def cai_rank(value: str | None) -> int:
    norm = normalize_cai(value)
    return CAI_RANK[norm] if norm else 0


def cai_from_sac(sac_scale: str | None, highway: str | None = None) -> str | None:
    """Difficoltà CAI indicativa da `sac_scale`; le strade senza sac_scale sono «T»."""
    if sac_scale:
        return SAC_TO_CAI.get(sac_scale.strip())
    if highway in {"track", "service", "unclassified", "residential", "footway", "pedestrian"}:
        return "T"
    return None


def max_cai(values: list[str | None]) -> str | None:
    best = max((cai_rank(v) for v in values), default=0)
    return RANK_CAI.get(best)


def osmc_color(symbol: str | None) -> str | None:
    """Colore del segnavia da `osmc:symbol` (`red:white:red_bar:332:black` → `red`)."""
    if not symbol:
        return None
    color = symbol.split(":", 1)[0].strip().lower()
    return color or None
