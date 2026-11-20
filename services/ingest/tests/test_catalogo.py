"""Catalogo Trentino-Alto Adige e Dolomiti (ADR 0015): area, prefiltro, punti, affidabilità."""

from cordata_ingest.activities.catalog import activity_kind
from cordata_ingest.activities.itinerary import extract_points, title_points
from cordata_ingest.activities.prefilter import classify
from cordata_ingest.activities.reliability import score
from cordata_ingest.geo.area import contains, in_area


def test_area_regione_e_dolomiti_venete():
    assert contains(11.12, 46.07)  # Trento
    assert contains(11.03, 46.36)  # Cles, Val di Non: dentro (correzione dell'utente)
    assert contains(12.14, 46.54)  # Cortina d'Ampezzo
    assert contains(11.24, 45.78)  # Pasubio
    assert not contains(10.99, 45.44)  # Verona, pianura
    assert not contains(12.66, 46.30)  # Dolomiti Friulane
    assert in_area([[11.8, 46.3], [11.82, 46.31]])


def test_prefiltro_per_titolo():
    inside = {"pasubio", "rifugio fonda savio"}
    outside = {"monte venda"}
    assert classify("Gita al Pasubio", inside, outside)[0] == "dentro"
    assert classify("Trekking in Sardegna 2025", inside, outside)[0] == "fuori"
    # un rifugio col nome di una città non è una meta lontana
    assert classify("Capanna Trieste in Val di Pelsa", inside, outside)[0] != "fuori"
    # un programma non si scarta dal titolo
    assert classify("Programma 2026 Euganei e Dolomiti", inside, outside, True)[0] == "dentro"


TESTO = """CLUB ALPINO ITALIANO
Sezione di Belluno
Domenica 20 giugno 2026
DESCRIZIONE
Giro ad anello che partendo da località Giralba ci farà percorrere la val d'Ansiei. Su
facili sterrati arriveremo al lago di Misurina con splendida vista sulle Marmarole e le Tre
Cime. Saliremo al rifugio Carpi (2110 m) presso la forcella Maraia e torneremo al punto di
partenza.
Equipaggiamento: scarponi.
"""


def test_punti_dal_testo_senza_panorama():
    out = extract_points(TESTO, home="Belluno")
    names = [p["nome"] for p in out["punti"]]
    assert names[0] == "Giralba"
    assert "Lago di Misurina" in names and "Rifugio Carpi" in names
    assert not any("Marmarole" in n or "Tre Cime" in n for n in names)
    assert out["anello"]
    carpi = next(p for p in out["punti"] if p["nome"] == "Rifugio Carpi")
    assert carpi["quota_m"] == 2110


def test_tappe_nel_titolo():
    assert title_points("Chiusa – Albions – Gudon")[:2] == ["Chiusa", "Albions"]
    assert title_points("Traversata da Favogna di Sopra al Rifugio Sores")[0].startswith("Favogna")


def _track(**checks):
    return {
        "status": "auto_ok",
        "coords": [[11.0, 46.0], [11.01, 46.01]],
        "checks": checks,
        "points": [
            {"nome": "A", "lon": 11.0, "lat": 46.0, "quota_dichiarata": 1500, "quota_osm": 1510},
            {"nome": "B", "lon": 11.01, "lat": 46.01, "quota_dichiarata": None},
        ],
        "on_cited_share": None,
        "cited_refs": [],
    }


def test_punteggio():
    good = _track(distanza={"scarto": 0.03}, salita={"scarto": -0.05}, quota_max={"scarto_m": 10})
    assert score(good)["punteggio"] >= 95
    # un solo confronto: la parte traccia non supera 0,6, sotto soglia
    one = _track(salita={"scarto": 0.0})
    assert score(one)["parti"]["traccia"] == 0.6
    assert not score(one)["pubblicabile"]
    assert score({"status": "fallita", "coords": []})["punteggio"] == 0


def test_tipo_di_attivita():
    assert activity_kind({"difficolta": "MC/BC"}, "Cicloescursionismo")[0] == "bici"
    assert activity_kind({"difficolta": "PD"}, "")[0] == "alpinismo"
    assert activity_kind({"difficolta": "EE", "salita_m": 900}, "Escursione")[0] == "escursione"


def test_date_di_un_programma():
    from cordata_ingest.activities.parse import programme_dates

    pages = [
        (
            1,
            "Gita al Lago di Calaita\nDomenica 12 aprile 2026\nDifficoltà: E\n\n"
            "Anello del Monte Grappa\nSabato 9 maggio 2026\nDifficoltà: EE\n",
        ),
    ]
    assert programme_dates(pages, 2026) == ["2026-04-12", "2026-05-09"]
    # un elenco di sole date uno sotto l'altro non sono voci
    lista = [(1, "12/01/2026\n18/01/2026\n25/01/2026\n")]
    assert programme_dates(lista, 2026) == []


def test_elenco_delle_tappe_dopo_itinerario():
    from cordata_ingest.activities.itinerary import extract_points, list_points

    names = lambda t: [p["nome"] for p in list_points(t)]  # noqa: E731
    assert names("Itinerario: Casotto, Belfiore, Luserna, Longhi, Casotto.\nRitrovo: ore 7") == [
        "Casotto",
        "Belfiore",
        "Luserna",
        "Longhi",
        "Casotto",
    ]
    # sentieri tolti, «M.» è monte, il punto dell'abbreviazione non chiude l'elenco
    assert names(
        "Itinerario: Bosco Chiesanuova vicino loc Scandole, sentiero E5, M. Tomba, "
        "sentiero 255, Bosco Chiesanuova.\nRitrovo"
    ) == ["Bosco Chiesanuova", "Monte Tomba", "Bosco Chiesanuova"]
    # quota tra parentesi, nomi «di sopra» interi, numeri dei sentieri non sono quote
    got = list_points(
        "Itinerario: Malga Cagnon di sopra – sent.439 forcella Nuvolau (2400 m) – Monte Conca."
    )
    assert [(p["nome"], p["quota_m"]) for p in got] == [
        ("Malga Cagnon di sopra", None),
        ("Forcella Nuvolau", 2400),
        ("Monte Conca", None),
    ]
    # indicazioni stradali e prosa non sono elenchi di tappe
    assert names("Percorso: Autostrada A27 fino a Pian di Vedoia, direzione Longarone") == []
    assert names("Itinerario: si sale per il bosco fitto fino alla forcella e poi si scende.") == []
    # l'elenco vale più della prosa ed è un anello se torna alla partenza
    out = extract_points("Itinerario: Casotto, Belfiore, Luserna, Casotto.\nNote: pranzo al sacco")
    assert [p["nome"] for p in out["punti"]] == ["Casotto", "Belfiore", "Luserna"]
    assert out["anello"]
