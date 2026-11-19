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


def test_parser_programma_con_date_senza_anno_e_titoli_accoppiati():
    from cordata_ingest.activities.parse import calendar_entry, parse

    pagina = (
        "12:00\n"
        "Partenza da Prè, seguendo le indicazioni per Leano\n"
        "segnavia 421 si raggiunge la Cappella. Rientro per la forestale e arrivo a Prè.\n"
        "PASTA DAL FRANCO\nMANUTENZIONE SENTIERI\n12/04\n19/04\n"
        "Leano\n700 md+ E\n"
    )
    altra = (
        "GITA SOCIALE - GIRO DEI LAGHI\nDEL CEVEDALE\n13/09\nTrekking ad anello.\n15 km\n6 ore\nEE"
    )
    riassunto = (
        "12/01/2026\n18/01/2026\n12/04/2026\nQuest'anno in collaborazione con la Sat di Arco"
    )
    pages = [(16, pagina), (27, altra), (31, riassunto)]
    voce = calendar_entry(pages, "2026-04-12")
    assert voce and voce[0][0] == 16  # non l'elenco di date complete della pagina 31
    p = parse(voce, entry_date="2026-04-12")
    assert p["titolo"]["value"] == "Pasta dal Franco"
    assert p["difficolta"]["value"] == "E"
    assert p["salita_m"]["value"] == 700
    assert p["sentieri"]["value"] == ["421"]  # non «SENTIERI 12/04» né «12:00»
    assert p["tipo_percorso"]["value"] == "anello"  # «arrivo a Prè»
    q = parse(calendar_entry(pages, "2026-09-13"), entry_date="2026-09-13")
    assert q["titolo"]["value"] == "Gita Sociale - Giro dei Laghi del Cevedale"
    assert (q["distanza_km"]["value"], q["durata"]["value"]) == (15, "6:00")
    assert q["partenza_nome"]["value"] is None  # «Gita sociale» non è un luogo


def test_parser_misure_dei_programmi_e_delle_locandine():
    p = _parse(
        "DOMENICA 15 maggio 2022\n"
        "ESCURSIONE Livello EE           DISL. m. 900 ca\n"
        "DURATA ESCURSIONE ore 6.00 ca\n"
        "PARTENZA: ore 6.45 con automobili private (1h.30min di viaggio)\n"
        "ITINERARIO: partenza da Pregasina; scendendo torniamo a Pregasina.\n"
    )
    assert p["difficolta"] == "EE"
    assert p["salita_m"] == 900
    assert p["durata"] == "6:00"  # non «1h.30min di viaggio»
    assert p["mezzi"] == "mezzi propri"
    assert p["tipo_percorso"] == "anello"
    q = _parse("Si scende a Riva con l'autobus di linea\nD+ 2400m\n25-30km\nGIRO\n12 ore")
    assert q["mezzi"] == "mezzi pubblici"
    assert q["salita_m"] == 2400 and q["quota_max_m"] is None  # D+ non è una quota
    assert q["distanza_km"] is None  # un intervallo non è una distanza
    assert q["durata"] == "12:00"
    r = _parse("Dislivello: +- 900 m – 11 km - 5 h circa\n892 md+\n921 md-")
    assert r["distanza_km"] == 11


def test_parser_date_lettera_e_anno_dalla_cartella():
    from cordata_ingest.activities.parse import parse

    lettera = parse([(1, "Cavalese, 3 maggio 2018\nVISITA ALLA GOLA\n27 maggio 2018\n")])
    assert lettera["data"]["value"] == "2018-05-27"
    volantino = "Venerdì 16 maggio\nIncontro con le rifugiste\nSabato 17 maggio\nEscursione a tappe"
    p = parse([(1, volantino)], hint="2025/05/Donne-e-Montagna.pdf")
    assert p["data"]["value"] == "2025-05-17"


def test_sentieri_citati_omonimi_lontani_esclusi():
    from cordata_ingest.activities.reconstruct import _drop_far_homonyms

    rows = [
        {"relation_id": 1, "ref": "105", "reg_ref": None, "near_m": 300.0},
        {"relation_id": 2, "ref": "105", "reg_ref": None, "near_m": 14000.0},  # omonimo lontano
        {"relation_id": 3, "ref": "325", "reg_ref": "E325", "near_m": 9000.0},  # unico: resta
        {"relation_id": 4, "ref": "325", "reg_ref": "O325", "near_m": 800.0},
    ]
    kept = _drop_far_homonyms(rows, {"E325"})
    assert sorted(r["relation_id"] for r in kept) == [1, 3, 4]
    assert all("near_m" not in r for r in kept)


def test_andata_e_ritorno_con_il_ritorno_tra_i_punti_chiave():
    from cordata_ingest.activities.reconstruct import outbound_only

    pts = [(10.679, 46.357), (10.672, 46.378), (10.633, 46.402), (10.6791, 46.3571)]
    kinds = ["fermata", "malga", "cima", "fermata"]
    assert outbound_only(pts, kinds, "andata_ritorno") == (pts[:-1], kinds[:-1])
    assert outbound_only(pts, kinds, "anello") == (pts, kinds)
    assert outbound_only(pts[:2], kinds[:2], "andata_ritorno") == (pts[:2], kinds[:2])


def test_ricostruzione_incompatibile_con_la_locandina_non_mostrata():
    from cordata_ingest.activities.reconstruct import verdict

    ok = {"scarto": 0.05, "ok": True}
    # Sentiero dei Fiori: 68 km e +5700 m per 15 km e +500 m (zona fuori dai dati)
    assert (
        verdict(
            {"distanza": {"scarto": 3.6, "ok": False}, "salita": {"scarto": 10.4, "ok": False}},
            0,
            7,
        )[0]
        == "fallita"
    )
    # Vioz: distanza dichiarata solo per l'andata, dislivello giusto → da rivedere, non fallita
    assert (
        verdict(
            {"distanza": {"scarto": 1.5, "ok": False}, "salita": {"scarto": 0.12, "ok": True}}, 0, 4
        )[0]
        == "da_rivedere"
    )
    assert verdict({"distanza": ok, "salita": ok}, 1, 4) == ("auto_ok", None)
    assert verdict({"distanza": ok, "salita": ok}, 2, 4)[0] == "da_rivedere"
    assert verdict({"anello_chiuso": {"distanza_m": 0, "ok": True}}, 0, 3)[0] == "da_rivedere"


def test_sanitize_telefono_fisso_sulla_riga_del_sito():
    text = (
        "0471/123456   -   www.sezione-esempio.it  -   segreteria@example.org\n"
        "quota 1250 m, ore 8.30"
    )
    out = sanitize(text)[0]
    assert "123456" not in out and "example.org" not in out
    assert "654321" not in sanitize("Tel. 0471 / 654321")[0]
    assert "1250 m" in out and "8.30" in out


def test_sanitize_istruttore_e_nome_a_fine_riga():
    text = (
        "oppure presso l'istruttore Mario Bianchi o presso il Presidente della sezione Luca \n"
        "Verdi (333-1234567)\n"
        "Il presidente del Rifugio Roma apre a giugno"
    )
    out = sanitize(text)[0]
    for name in ("Mario", "Bianchi", "Luca", "Verdi", "1234567"):
        assert name not in out
    assert "Rifugio Roma" in out


def test_sanitize_scheda_tecnica_sulla_riga_di_una_email():
    text = (
        "SCHEDA TECNICA Iscrizioni: entro le 19 via e-mail\n"
        "Difficoltà: EEA (Escursionisti Esperti con Attrezzatura). La ferrata è gite@example.org\n"
        "Capogita: Mario Rossi (cell. 333 1234567)"
    )
    out = sanitize(text)[0]
    assert "Difficoltà: EEA (Escursionisti Esperti con Attrezzatura)" in out
    assert "Rossi" not in out and "example.org" not in out


def test_parser_tempi_a_segmenti_costi_di_viaggio_e_quote():
    p = _parse(
        "Domenica 11 ottobre 2026\n"
        "Distanza: 16,5 km.\n"
        "Dislivello: 640 m in salita e 760 m in discesa.\n"
        "Tempi di cammino: 1h 30' in salita,\n"
        '1h 30" in piano, 2h in discesa.\n'
        "Quota di viaggio: € 15,00.\n"
    )
    assert (p["durata"], p["salita_m"], p["discesa_m"]) == ("5:00", 640, 760)
    assert p["quota_eur"] == 15
    q = _parse(
        "Tempi di cammino: Circa 4 ore e 15 minuti complessivi\n"
        "Distanza totale: km 12,00\n"
        "Rifugio Giogo Lungo 2603m.\n"
        "Sullo sfondo vediamo il Pizzo Rosso che, con i suoi 3495 m, è la seconda vetta\n"
        "E previsto un rimborso di € 5,00 a passeggero.\n"
    )
    assert (q["durata"], q["distanza_km"], q["quota_max_m"], q["quota_eur"]) == (
        "4:15",
        12,
        2603,
        5,
    )
    r = _parse(
        "Tempo di percorrenza: ca. 1 ora (salita), 45 minuti (ritorno)\nPunto più alto\n2.643 m"
    )
    assert (r["durata"], r["quota_max_m"]) == ("1:45", 2643)


def test_sanitize_righe_lunghe_in_maiuscolo_senza_rallentare():
    import time

    from cordata_ingest.activities.extract import NAME_LIST

    line = (
        "COPERTURA ASSICURATIVA ED IL CONSENSO DEI DATI PERSONALI, OLTRE AL VERSAMENTO "
        "DELLA QUOTA DI €. 15"
    )
    start = time.perf_counter()
    assert NAME_LIST.match(line) is None
    assert time.perf_counter() - start < 0.5
    for names in (
        "Mario Rossi, Anna BIANCHI",
        "ROSSI Mario",
        "Maria de Rossi, Luca Verdi,",
        "Anna D'Angelo",
        "ROSSIMario",
    ):
        assert NAME_LIST.match(names), names
    assert NAME_LIST.match("Rifugio aperto") is None


def test_sanitize_cognome_a_capo_dopo_il_ruolo():
    text = "costruito grazie al Presidente Giovanni\nBianchi con l'aiuto dei soci\nRifugio Roma"
    out = sanitize(text)[0]
    assert "Giovanni" not in out and "Bianchi" not in out
    assert out.count("\n") == 2 and "Rifugio Roma" in out


def test_sanitize_soci_nominati_e_capi_gita():
    text = (
        "ci attenderà un rinfresco curato dai soci Mario Bianchi e Luca De Rossi.\n"
        "riservata ai soci CAI in regola\n"
        "CAPI GITA: VERDI S. – NERI M."
    )
    out = sanitize(text)[0]
    for name in ("Mario", "Bianchi", "Luca", "Rossi", "VERDI", "NERI"):
        assert name not in out, name
    assert "riservata ai soci CAI in regola" in out


def test_parser_programmi_con_orari_partenze_in_pullman_e_gradi_doppi():
    p = _parse(
        "CLUB ALPINO ITALIANO\n"
        "Sezione di Feltre\n"
        "Domenica 20 settembre\n"
        "2026\n"
        "Ore 6,00: Partenza con pullman da Feltre (parcheggio Pra del Moro).\n"
        "Ore 7:30 Ritrovo al parcheggio.\n"
        "Ore 17:00 Arrivo a Feltre.\n"
        "Difficoltà: EE-EEA\n"
        "Dislivello: positivo m 1250 ca, negativo m 1200 ca. Km 18 ca.\n"
        "Iscrizioni: entro martedì 15 settembre 2026\n"
    )
    assert p["data"] == "2026-09-20"  # non la scadenza delle iscrizioni
    assert p["ora_ritrovo"] == "07:30"  # non l'orario del rientro
    assert p["difficolta"] == "EEA"
    assert (p["salita_m"], p["discesa_m"], p["distanza_km"]) == (1250, 1200, 18)
    assert p["partenza_nome"] != "Feltre"  # è il viaggio in pullman, non la partenza a piedi
    q = _parse(
        "Difficoltà: T/E\nSi sale alla cima del Monte Totoga, a 1705 metri, punto panoramico"
    )
    assert (q["difficolta"], q["quota_max_m"]) == ("E", 1705)


def test_adapter_generico_pagine_gite_e_pdf():
    from cordata_ingest.activities.site_adapter import guess_date, links, list_pages

    home = """<a href="/gite-2026/">Gite 2026</a> <a href="/privacy">Privacy</a>
    <a href="https://altro.it/gite">Gite di altri</a> <a href="/chi-siamo">Chi siamo</a>
    <a href='/doc/Programma%202026.pdf'>Programma</a>"""
    assert list_pages(home, "https://www.sat-esempio.it/") == [
        "https://www.sat-esempio.it/gite-2026/"
    ]
    pdfs = [u for u, _ in links(home, "https://www.sat-esempio.it/") if u.endswith(".pdf")]
    assert pdfs == ["https://www.sat-esempio.it/doc/Programma%202026.pdf"]
    assert guess_date("https://x.it/a/Gita_17.05.2026.pdf", "") == "2026-05-17"
    assert guess_date("https://x.it/uploads/2026/03/locandina.pdf", "") == "2026-03-01"
    assert guess_date("https://x.it/locandina.pdf", "Gita al lago") == ""


def test_estrazione_di_una_pagina_web_di_gita(tmp_path):
    from cordata_ingest.activities.extract import extract_html

    page = tmp_path / "gita.html"
    page.write_text(
        "<html><head><script>var x=1</script></head><body><nav>Home | Gite</nav>"
        "<article><h1>Gita al Lago Nero</h1><p>Domenica 7 giugno 2026<br>Dislivello 600 m</p>"
        "<p>Info: Mario Rossi cell. 333 1234567</p></article>"
        "<footer>© sezione</footer></body></html>",
        encoding="utf-8",
    )
    text = extract_html(page)["pages"][0]["text"]
    assert text.splitlines()[:3] == [
        "Gita al Lago Nero",
        "Domenica 7 giugno 2026",
        "Dislivello 600 m",
    ]
    assert "Home" not in text and "sezione" not in text and "var x" not in text
    assert "1234567" not in text and "Rossi" not in text


def test_programma_pubblicato_come_pagina_web():
    from cordata_ingest.activities.parse import calendar_entry, parse

    text = (
        "ESCURSIONI SAT DELLA DOMENICA 2026\n"
        "Giro del Garda: Campione, Forra di\n"
        "San Michele, Tremosine\n"
        "Domenica 25 gennaio 2026\n"
        "Bel percorso sul lago.\n"
        "Tipologia: traversata\nSalita: 920 m\nDiscesa: 640 m\nSviluppo: 15 km\n"
        "Tempo: 5 ore e 30\nDifficoltà: E\n"
        "Villamontagna, Cima Calisio\n"
        "Domenica 1 marzo 2026\n"
        "Tipologia: traversata\nSalita: 820 m\nTempo: 6 ore\nDifficoltà: EE\n"
    )
    entry = calendar_entry([(1, text)], "2026-01-25")
    assert entry[0][1].splitlines()[0] == "Giro del Garda: Campione, Forra di"
    p = parse(entry, entry_date="2026-01-25")
    assert p["titolo"]["value"] == "Giro del Garda: Campione, Forra di San Michele, Tremosine"
    assert (p["durata"]["value"], p["salita_m"]["value"], p["discesa_m"]["value"]) == (
        "5:30",
        920,
        640,
    )
    q = parse(calendar_entry([(1, text)], "2026-03-01"), entry_date="2026-03-01")
    assert (q["difficolta"]["value"], q["durata"]["value"]) == ("EE", "6:00")
