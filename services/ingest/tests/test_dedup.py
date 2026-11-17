"""Deduplica degli itinerari (SPEC §7.5) su tracce sintetiche."""

import math

from cordata_ingest.activities.dedup import compare, frechet, group, resample, to_xy

# anello di circa 6 km attorno a un punto delle Dolomiti
LOOP = [
    [11.80 + 0.012 * math.cos(t / 40 * 2 * math.pi), 46.40 + 0.008 * math.sin(t / 40 * 2 * math.pi)]
    for t in range(41)
]


def shifted(coords, meters):
    return [[c[0] + meters / 77_000, c[1]] for c in coords]


def test_stessa_traccia_spostata_o_invertita():
    assert compare(LOOP, shifted(LOOP, 20)).relation == "stesso"
    assert compare(LOOP, list(reversed(LOOP))).relation == "stesso"


def test_meta_traccia_e_variante_traccia_lontana_no():
    half = LOOP[:21]
    assert compare(LOOP, half).relation == "variante"
    assert compare(LOOP, shifted(LOOP, 2000)).relation is None


def test_ricampionamento_e_frechet():
    xy = to_xy([[11.0, 46.0], [11.01, 46.0]], 46.0)
    pts = resample(xy, 50)
    assert len(pts) == 17  # circa 773 m ogni 50 m, più gli estremi
    assert frechet(pts, pts) == 0


def test_gruppo_con_canonico_verificato():
    bbox = [11.78, 46.39, 11.82, 46.41]
    tracks = {
        "a": {"coords": LOOP, "bbox": bbox, "verified": False, "date": "2026-07-26"},
        "b": {"coords": shifted(LOOP, 30), "bbox": bbox, "verified": True, "date": "2021-07-01"},
        "c": {
            "coords": shifted(LOOP, 5000),
            "bbox": [11.84, 46.39, 11.88, 46.41],
            "verified": True,
        },
    }
    groups, relations = group(tracks)
    assert len(groups) == 1 and groups[0].canonical == "b" and groups[0].members == ["a", "b"]
    assert relations[0]["relation"] == "stesso"
