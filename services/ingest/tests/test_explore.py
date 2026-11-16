"""Indice di Esplora e documenti delle attività: funzioni pure."""

from datetime import date

from cordata_ingest.build.activities import activity_slug, equipment, summary
from cordata_ingest.build.explore import _n, mini_profile, season


def test_numeri_del_catasto_anche_come_stringhe():
    assert _n("939") == 939.0
    assert _n("9,7") == 9.7
    assert _n("") is None and _n(None) is None and _n("n.d.") is None


def test_stagione_indicativa_dalla_quota():
    assert season(900, "E") == [3, 4, 5, 6, 7, 8, 9, 10, 11]
    assert season(2000, "E") == [6, 7, 8, 9, 10]
    assert season(2600, "EE") == [7, 8, 9]
    assert season(2400, "EAI") == [12, 1, 2, 3]


def test_mini_profilo_equidistante():
    points = [[0, 1000], [500, 1100], [1000, 1200]]
    prof = mini_profile(points, n=5)
    assert len(prof) == 5 and prof[0] == 1000 and prof[-1] == 1200


def test_sintesi_solo_dai_dati():
    act = {
        "tipo_percorso": "anello",
        "distanza_km": 13,
        "salita_m": 840,
        "partenza": {"nome": "Casere"},
        "punti_chiave": [
            {"nome": "Casere", "quota_m": 1580},
            {"nome": "Archbichl", "quota_m": 2414},
            {"nome": "Casere", "quota_m": 1580},
        ],
    }
    text = summary(act, {"distance_km": 12.0, "ascent_m": 800})
    assert text == (
        "Anello di circa 13 km e 840 m di dislivello con partenza da Casere: Archbichl (2414 m)."
    )


def test_attrezzatura_indicativa():
    winter = equipment({"difficolta": "EAI", "data": date(2026, 2, 22)}, 2490)
    assert any("ciaspole" in e for e in winter) and any("antivento" in e for e in winter)
    ferrata = equipment({"difficolta": "EEA", "data": date(2020, 7, 19)}, 2436)
    assert any("ferrata" in e for e in ferrata)
    night = equipment({"difficolta": None, "titolo": "Escursione in notturna"}, 1250)
    assert "frontale" in night


def test_indirizzo_leggibile_e_stabile():
    act = {"data": date(2026, 7, 26), "titolo": "Anello Waldnersee", "sezione": "CAI Bolzano"}
    assert activity_slug("x", act) == "2026-07-26-anello-waldnersee-bolzano"
