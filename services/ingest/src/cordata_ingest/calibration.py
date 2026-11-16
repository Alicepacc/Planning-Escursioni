"""Calibrazione di dislivello e tempi contro i valori ufficiali OSM2CAI (SPEC §8, ADR 0007).

Per ogni sentiero validato (`sda` 4) con valori ufficiali, campiona il DEM lungo la geometria
OSM2CAI una sola volta e prova una griglia di parametri: media mobile, soglia di isteresi e
lunghezza dei tratti del modello dei tempi. Confronta con `ascent`, `descent`,
`duration_forward` e `duration_backward` del catasto e scrive un report ripetibile.

Uso:  python -m cordata_ingest.calibration [--limit N] [--out reports/phase1/calibrazione]
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import shape

from .config import areas, data_dir, repo_root
from .geo.elevation import TerrariumDem, ascent_descent, moving_average
from .geo.profile import as_single_line
from .geo.track import resample_along
from .http import PoliteClient
from .osm2cai.sync import Osm2caiStore
from .timing import swiss_track_minutes

STEP_M = 15.0
WINDOWS = (1, 3, 5, 7, 9)
HYSTERESES = (0.0, 3.0, 5.0, 10.0, 15.0)
SEGMENTS = (15.0, 50.0, 100.0, 200.0, 500.0)


@dataclass
class Sample:
    rid: str
    ref: str
    length_km: float
    official: dict[str, float]
    distances: list[float]
    raw: list[float]
    reversed_geometry: bool


def load_samples(
    store: Osm2caiStore, dem: TerrariumDem, limit: int | None
) -> tuple[list[Sample], dict]:
    w, s, e, n = areas()["pilot"].bbox
    skipped = {"fuori area": 0, "senza valori ufficiali": 0, "geometria spezzata": 0, "sda < 4": 0}
    samples: list[Sample] = []
    for feature in store.features():
        props = feature["properties"]
        if props.get("sda") != 4:
            skipped["sda < 4"] += 1
            continue
        official = {
            k: float(props[k])
            for k in ("ascent", "descent", "duration_forward", "duration_backward")
            if props.get(k) not in (None, "", 0)
        }
        if len(official) < 4 or not props.get("distance"):
            skipped["senza valori ufficiali"] += 1
            continue
        geom = shape(feature["geometry"])
        minx, miny, maxx, maxy = geom.bounds
        if minx < w or maxx > e or miny < s or maxy > n:
            skipped["fuori area"] += 1
            continue
        coords, gaps = as_single_line(geom)
        if gaps:
            skipped["geometria spezzata"] += 1
            continue
        points, dist = resample_along(coords, STEP_M)
        raw = dem.sample(points)
        # orientamento: la geometria va da `from` a `to`? Si confrontano le quote ufficiali
        reversed_geometry = False
        ele_from, ele_to = props.get("ele_from"), props.get("ele_to")
        if ele_from is not None and ele_to is not None:
            direct = abs(raw[0] - ele_from) + abs(raw[-1] - ele_to)
            swapped = abs(raw[0] - ele_to) + abs(raw[-1] - ele_from)
            if swapped + 20 < direct:
                reversed_geometry = True
                raw = list(reversed(raw))
                dist = [dist[-1] - d for d in reversed(dist)]
        samples.append(
            Sample(
                rid=str(props["id"]),
                ref=str(props.get("ref") or ""),
                length_km=dist[-1] / 1000,
                official=official,
                distances=dist,
                raw=raw,
                reversed_geometry=reversed_geometry,
            )
        )
        if limit and len(samples) >= limit:
            break
    return samples, skipped


def _errors(pairs: list[tuple[float, float]]) -> dict[str, float]:
    """Errore assoluto medio, mediana dell'errore %, distorsione (calcolato − ufficiale)."""
    diffs = [c - o for c, o in pairs]
    pct = [abs(c - o) / o * 100 for c, o in pairs if o > 0]
    return {
        "mae": statistics.fmean(abs(d) for d in diffs),
        "bias": statistics.fmean(diffs),
        "median_abs_pct": statistics.median(pct),
        "within_15pct": sum(p <= 15 for p in pct) / len(pct) * 100,
    }


def evaluate(samples: list[Sample]) -> dict:
    elevation_results = []
    for window, hyst in itertools.product(WINDOWS, HYSTERESES):
        ups, downs = [], []
        for smp in samples:
            smooth = moving_average(smp.raw, window)
            up, down = ascent_descent(smooth, hyst)
            ups.append((up, smp.official["ascent"]))
            downs.append((down, smp.official["descent"]))
        elevation_results.append(
            {
                "window": window,
                "hysteresis_m": hyst,
                "ascent": _errors(ups),
                "descent": _errors(downs),
            }
        )
    time_results = []
    for window, segment in itertools.product(WINDOWS, SEGMENTS):
        fwd, bwd = [], []
        for smp in samples:
            smooth = moving_average(smp.raw, window)
            f = swiss_track_minutes(smp.distances, smooth, segment).minutes
            total = smp.distances[-1]
            rev_d = [total - d for d in reversed(smp.distances)]
            b = swiss_track_minutes(rev_d, list(reversed(smooth)), segment).minutes
            fwd.append((f, smp.official["duration_forward"]))
            bwd.append((b, smp.official["duration_backward"]))
        time_results.append(
            {
                "window": window,
                "segment_m": segment,
                "forward": _errors(fwd),
                "backward": _errors(bwd),
                "both": _errors(fwd + bwd),
            }
        )
    best_elev = min(elevation_results, key=lambda r: r["ascent"]["mae"] + r["descent"]["mae"])
    best_time = min(time_results, key=lambda r: r["both"]["mae"])
    return {
        "elevation": elevation_results,
        "time": time_results,
        "best_elevation": best_elev,
        "best_time": best_time,
    }


def write_report(out: Path, samples: list[Sample], skipped: dict, result: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(
        json.dumps({"n": len(samples), "skipped": skipped, **result}, indent=1) + "\n",
        encoding="utf-8",
    )
    be, bt = result["best_elevation"], result["best_time"]
    lines = [
        "# Calibrazione di dislivello e tempi contro OSM2CAI",
        "",
        f"Sentieri validati (`sda` 4) dell'area pilota usati: **{len(samples)}**. "
        f"Esclusi: {', '.join(f'{k} {v}' for k, v in skipped.items())}.",
        "",
        f"DEM: Mapterhorn z12 (Terrarium), campionamento ogni {STEP_M:.0f} m lungo la geometria "
        "OSM2CAI. Verità di riferimento: `ascent`, `descent`, `duration_forward`, "
        "`duration_backward` del catasto.",
        "",
        "## Dislivello",
        "",
        "| Media mobile | Isteresi | D+ errore medio | D+ distorsione | D+ mediana errore % "
        "| D+ entro ±15% | D− errore medio |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in result["elevation"]:
        a, d = r["ascent"], r["descent"]
        mark = " **←**" if r is be else ""
        lines.append(
            f"| {r['window'] * STEP_M:.0f} m | {r['hysteresis_m']:.0f} m "
            f"| {a['mae']:.0f} m{mark} | {a['bias']:+.0f} m | {a['median_abs_pct']:.1f}% "
            f"| {a['within_15pct']:.0f}% | {d['mae']:.0f} m |"
        )
    lines += [
        "",
        "## Tempi (modello CAI / Sentieri Svizzeri)",
        "",
        "| Media mobile | Tratti | Errore medio | Distorsione | Mediana errore % | Entro ±15% |",
        "|---|---|---|---|---|---|",
    ]
    for r in result["time"]:
        b = r["both"]
        mark = " **←**" if r is bt else ""
        lines.append(
            f"| {r['window'] * STEP_M:.0f} m | {r['segment_m']:.0f} m | {b['mae']:.1f} min{mark} | "
            f"{b['bias']:+.1f} min | {b['median_abs_pct']:.1f}% | {b['within_15pct']:.0f}% |"
        )
    lines += [
        "",
        "## Migliori parametri rispetto al catasto",
        "",
        "Le frecce nelle tabelle indicano i parametri più vicini ai valori del catasto. Per il "
        "dislivello Cordata **non** li adotta: il catasto conta tutte le micro-risalite, mentre le "
        "sezioni dichiarano un dislivello «da escursionista». Parametri adottati e motivazioni in "
        "`docs/decisions/0007-modelli-dei-tempi-e-delle-quote.md`.",
        "",
        f"- Dislivello: media mobile {be['window'] * STEP_M:.0f} m, isteresi "
        f"{be['hysteresis_m']:.0f} m → D+ errore medio {be['ascent']['mae']:.0f} m, "
        f"mediana {be['ascent']['median_abs_pct']:.1f}%.",
        f"- Tempi: media mobile {bt['window'] * STEP_M:.0f} m, tratti di "
        f"{bt['segment_m']:.0f} m → errore medio {bt['both']['mae']:.1f} min, mediana "
        f"{bt['both']['median_abs_pct']:.1f}%. I tempi ufficiali sono arrotondati a 15 minuti: "
        "un errore medio sotto i 7-8 minuti è al livello dell'arrotondamento.",
    ]
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--zoom", type=int, default=12)
    parser.add_argument(
        "--out", type=Path, default=repo_root() / "reports" / "phase1" / "calibrazione"
    )
    args = parser.parse_args(argv)
    store = Osm2caiStore(data_dir() / "osm2cai")
    with PoliteClient(host_intervals={"tiles.mapterhorn.com": 0.25}) as client:
        dem = TerrariumDem(data_dir() / "dem" / "mapterhorn", client, zoom=args.zoom)
        samples, skipped = load_samples(store, dem, args.limit)
    result = evaluate(samples)
    write_report(args.out, samples, skipped, result)
    be, bt = result["best_elevation"], result["best_time"]
    print(f"{len(samples)} sentieri; tile scaricati {dem.tiles_downloaded}; esclusi {skipped}")
    print(f"dislivello: finestra {be['window']}, isteresi {be['hysteresis_m']} → {be['ascent']}")
    print(f"tempi: finestra {bt['window']}, tratti {bt['segment_m']} → {bt['both']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
