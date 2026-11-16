"""Pipeline attività: pulizia dei dati personali, classificazione e normalizzazione dei nomi."""

from cordata_ingest.activities.classify import classify_name, classify_text
from cordata_ingest.activities.extract import sanitize
from cordata_ingest.activities.gazetteer import kind_of, normalize


def test_sanitize_rimuove_email_e_telefoni():
    text, n = sanitize("Info: segreteria@example.org, tel. 0471 123456 o cell. 347 1234567")
    assert "@" not in text and "0471" not in text and "347" not in text
    assert n >= 3


def test_sanitize_non_tocca_sentieri_date_e_orari():
    line = "Sentieri 332 360 326, partenza ore 07:30 di domenica 01.03.2026, quota m 1350"
    assert sanitize(line) == (line, 0)


def test_sanitize_nomi_dopo_le_etichette_di_ruolo():
    assert sanitize("Capogita: Mario Rossi")[0] == "Capogita: [nome rimosso]"
    text, _ = sanitize("Accompagnatori:\nMario Rossi\nAnna Bianchi\nSentieri 15, 7")
    assert "Rossi" not in text and "Bianchi" not in text and "Sentieri 15, 7" in text


def test_sanitize_nomi_nelle_righe_di_contatto():
    text, _ = sanitize("ISCRIZIONI: Rossi Mario 333 1234567, Bianchi Anna 340 7654321")
    assert "Rossi" not in text and "Bianchi" not in text and text.startswith("ISCRIZIONI")
    text, _ = sanitize("adesioni telefonando a Cinzia al n. 349 1234567 entro mercoledì")
    assert "Cinzia" not in text and "entro mercoledì" in text


def test_sanitize_tabella_dei_referenti():
    table = (
        "Tipologia\nReferernte\n14/10/2021\nLAGO DI TOVEL\nE\n+720/-720\nGIRO AD ANELLO\nRossi M."
    )
    text, _ = sanitize(table)
    assert "Rossi" not in text and "LAGO DI TOVEL" in text and "+720/-720" in text


def test_classify_name():
    assert classify_name("07_20260412-Castel-Coira.pdf") == "escursionismo?"
    assert classify_name("04_20260222-Ciaspolata-Forca-Rossa.pdf") == "ciaspolata"
    assert classify_name("Informativa privacy GDPR.pdf") == "amministrativo"
    assert classify_name("PROGRAMMA-ATTIVITA-CAI-APPIANO-2026.pdf") == "programma"


def test_classify_text_ciaspolata():
    text = "Difficoltà EAI. Ciaspolata con ARTVA, pala e sonda. Dislivello 600 m, partenza ore 8."
    assert classify_text(text)[0] == "ciaspolata"


def test_normalize_nomi_di_luogo():
    assert normalize("Rif. Monte Cavone") == "rifugio monte cavone"
    assert normalize("S. Costantino") == "san costantino"
    assert normalize("Passo S. Pellegrino") == "passo san pellegrino"
    assert normalize("Weißkugelhütte") == "weisskugelhutte"
    assert normalize("Palù del Fersina") == "palu del fersina"


def test_kind_of():
    assert kind_of({"natural": "peak", "name": "Corno Nero"}) == "cima"
    assert kind_of({"tourism": "alpine_hut"}) == "rifugio"
    assert kind_of({"historic": "castle"}) == "castello"
    assert kind_of({"place": "hamlet"}) == "frazione"
