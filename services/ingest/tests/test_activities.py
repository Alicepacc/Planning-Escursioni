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


def test_sanitize_direttivo_e_crediti_fotografici():
    text = (
        "Foto:\nMario Rossi, Anna Bianchi\ne archivio Sat\n"
        "PRESIDENTE: Verdi Luigi\nCONSIGLIERI: Neri Paolo, Gialli Rosa, De Sanctis\n"
        "Maria, Blu Carlo\nRESPONSABILE MANUTENZIONE SEDE E BAITA: Viola Ugo\n"
        "Il direttivo\nSi sale al Rifugio Pernici per il sentiero 405.\n"
        "Il Presidente della Commissione Rifugi: Bruno Grigi\n"
        "Il Gestore La Presidente SAT - Lia Rosa\n"
        "comunicare al responsabile sezionale dei sentieri, Tino Marrone: segnalazioni"
    )
    clean, n = sanitize(text)
    names = ("Rossi", "Bianchi", "Verdi", "Neri", "Gialli", "Sanctis", "Blu", "Viola")
    for name in (*names, "Grigi", "Lia Rosa", "Marrone"):
        assert name not in clean
    assert "e archivio Sat" in clean
    assert "Il direttivo" in clean
    assert "Rifugio Pernici per il sentiero 405" in clean
    assert n >= 5


def test_sanitize_organigrammi_firme_e_cellulari_a_6_cifre():
    org = (
        "Consiglio direttivo\nPresidente\nROSSI Mario\nTesoriere\nBIANCHI VERDI Anna\n"
        "Consigliere Segretario\nLia DE MONTE\nSAT Ledrense e CAI Bolzano"
    )
    clean, _ = sanitize(org)
    for name in ("ROSSI", "BIANCHI", "Anna", "DE MONTE"):
        assert name not in clean
    assert "SAT Ledrense e CAI Bolzano" in clean
    firma, _ = sanitize("Il Presidente della Sezione di Bolzano\nGino Neri\nBuone escursioni")
    assert "Neri" not in firma and "Buone escursioni" in firma
    prosa, _ = sanitize("A cura del Presidente della\nSezione, Ugo Grigi e della commissione")
    assert "Grigi" not in prosa
    tel, _ = sanitize("Responsabile escursione: Tizio Caio\nCaio Tizio tel. 335 272822")
    assert "272822" not in tel and "Tizio" not in tel
    altri, _ = sanitize(
        "Foto: Ada Neri\nUgo Blu – “Sfumature”\nASAG (referente)\nBONARDO Pia\n"
        "REFERENTI: Gino Rosso\nPellegrini Oscar, De Guelmi Alessandro\n"
        "l’ex Presidente generale Vito Bruni. Il responsabile del Rifugio Pernici"
    )
    for name in ("Neri", "Blu", "BONARDO", "Rosso", "Pellegrini", "Guelmi", "Bruni"):
        assert name not in altri
    assert "“Sfumature”" in altri and "Rifugio Pernici" in altri
    # elenco di sentieri: non è un telefono
    assert "332 360 326" in sanitize("Sentieri 332 360 326 e 327")[0]


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


def _parse(text: str) -> dict:
    from cordata_ingest.activities.parse import parse

    return {k: v["value"] for k, v in parse([(1, text)]).items()}


def test_parser_formati_sat_pergine():
    text = (
        "C.A.I. – S.A.T. Sezione di Pergine Valsugana\n"
        "Domenica 12 Luglio 2026\n"
        "propone una escursione sulla\n"
        "CIMA VERMOI (Vermoi Spitze) - m. 2929\n"
        "L'escursione inizia dal parcheggio presso il Rif. Zannes (m. 1685) oltre S. Maddalena.\n"
        "Con il segnavia n. 32/A si rientra al parcheggio.\n"
        "Difficoltà: EE\n"
        "Dislivello: salita e  discesa m. 1250\n"
        "Tempi: totale ore 6:30\n"
        "Alternativa escursionistica: Tempi: salita h 2:00 - discesa h 2:00\n"
        "Partenza:        da piazza Gavazzi (Bar Alba)  ad ore 6:30\n"
    )
    p = _parse(text)
    assert p["titolo"].startswith("CIMA VERMOI")
    assert p["durata"] == "6:30"  # non quella dell'alternativa
    assert p["salita_m"] == 1250 and p["discesa_m"] == 1250
    assert p["ora_ritrovo"] == "06:30"
    assert p["partenza_nome"] == "Rif. Zannes" and p["partenza_quota_m"] == 1685
    assert "32A" in p["sentieri"]


def test_parser_salita_e_discesa_separate_e_traversata():
    p = _parse(
        "Domenica 6 Settembre 2026\n"
        "propone una escursione al MONTE MULAZ - m. 2906\n"
        "(Traversata da P.so Valles al P.so Rolle)\n"
        "Tempi: salita ore 4:00 - discesa ore 3:00\n"
    )
    assert p["durata"] == "7:00"
    assert p["tipo_percorso"] == "traversata"
    assert (p["partenza_nome"], p["arrivo_nome"]) == ("P.so Valles", "P.so Rolle")
