# Pilota Fase 2: metriche (16/11/2026)

Pagina navigabile: [`pilot.html`](pilot.html) (una scheda per attività). Problemi e proposte:
[`decisions.md`](decisions.md). Comandi per rifare tutto da zero: in fondo.

## Campione

20 attività reali da **4 sezioni** (CAI Bolzano 7, CAI Bressanone 5, CAI Appiano 1, SAT 7, con
sei sezioni SAT diverse: Borgo Valsugana, Mezzolombardo, Trento, Aldeno, Spormaggiore, Rovereto,
più una tappa del trekking del 150° della SAT centrale). Vipiteno non ha locandine di gite online.
La fixture Val d'Inferno è la #0, fuori conteggio.

| Requisito SPEC §7.6 | Richiesti | Nel pilota |
|---|---|---|
| Anelli | ≥ 6 | 12 |
| Traversate | ≥ 4 | 4 (Monte Cavone, Val di Cembra, Laion–Ortisei, Perimetro del Trentino) |
| Andata e ritorno | ≥ 4 | 4 (Laghi di Sopranes, Rifugio Vallaccia, Lago della Selva, Malga Prà) |
| EE (o più) | ≥ 3 | 5 (Corno Nero, Rifugio Pio XI, Lago della Selva, Monte Cauriol, Forcella Segura EEA) |
| EAI / ciaspolate | 2 | 2 (Forca Rossa, Rifugio Vallaccia) |
| Da calendari annuali | 2 | 2 (libretto CAI Appiano 2026, calendario SAT Rovereto 2021) |
| PDF difficili | 2 | 2 (scansione con OCR: Malga Prà; impaginazione a tabella: Perimetro del Trentino) |

Le locandine SAT pubblicate sul sito centrale sono del 2020-2023: le sezioni SAT non pubblicano
più i programmi lì e i loro siti non sono collegati (vedi `decisions.md`, punto 1). Per il
pilota vanno bene: le attività passate diventano proposte d'archivio (SPEC §7.5).

## Scoperta, download, testo

| Passo | Risultato | Tempo |
|---|---|---|
| Scoperta (REST WordPress, solo metadati) | 1365 PDF in 5 sezioni; 344 candidati dal nome (Bolzano 56, Bressanone 47, Appiano 8, SAT 233) | pochi minuti |
| Download dei candidati del pilota | 51 PDF, 38,5 MB, 0 errori, robots.txt rispettato, 3 s tra richieste allo stesso host | 174 s (3,4 s/PDF) |
| Testo e pulizia dei dati personali | 51 documenti, 5 con pagine OCR (Tesseract ita+deu) | 24 s in tutto |

## Estrazione dei campi (parser a regole)

Verità di riferimento: i 20 PDF letti a mano (`config/pilot/reviewed/*.yaml`). **Attenzione:** il
parser è stato messo a punto su queste 20 locandine, quindi la precisione sul pilota è ottimistica.
Per una stima onesta ci sono 8 locandine mai viste dal parser, annotate dopo aver congelato le
regole (`config/pilot/holdout/`, solo alcuni campi).

| Campo | Estratti | Corretti | Presenti | Precisione | Copertura | Da rivedere | Precisione (non viste) | Copertura (non viste) |
|---|---|---|---|---|---|---|---|---|
| titolo | 20 | 20 | 20 | 100% | 100% | 20 | – | – |
| data | 19 | 19 | 19 | 100% | 100% | 0 | 100% | 88% |
| difficoltà | 16 | 16 | 16 | 100% | 100% | 2 | 100% | 100% |
| tipo di percorso | 17 | 16 | 20 | 94% | 80% | 3 | 83% | 62% |
| durata | 18 | 18 | 19 | 100% | 95% | 4 | 100% | 100% |
| distanza | 8 | 8 | 9 | 100% | 89% | 2 | 100% | 100% |
| salita | 19 | 19 | 19 | 100% | 100% | 2 | 100% | 100% |
| discesa | 18 | 18 | 19 | 100% | 95% | 4 | 100% | 71% |
| quota massima | 16 | 14 | 16 | 88% | 88% | 8 | 83% | 71% |
| partenza | 20 | 20 | 20 | 100% | 100% | 13 | 67% | 50% |
| quota di partenza | 13 | 13 | 14 | 100% | 93% | 7 | 100% | 80% |
| arrivo | 16 | 16 | 20 | 100% | 80% | 13 | – | – |
| ora di ritrovo | 17 | 17 | 17 | 100% | 100% | 1 | – | – |
| mezzi | 16 | 16 | 16 | 100% | 100% | 0 | – | – |
| quota di partecipazione | 15 | 15 | 15 | 100% | 100% | 3 | – | – |
| sentieri citati (insieme esatto) | 16 | 14 | 16 | 88% | 88% | 10 | 86% | 86% |
| punti chiave (F1 ≥ 0,5) | 15 | 11 | 20 | 73% | 55% | 20 | – | – |

- Valori estratti corretti: **270 su 279 (96,8%)** sul pilota, **61 su 66 (92,4%)** sulle locandine
  non viste. F1 medio: sentieri 0,98, punti chiave 0,43.
- La confidenza funziona come segnale: con confidenza ≥ 0,8 è corretto il 99,5% dei valori
  (182/183), sotto 0,8 il 91,7% (88/96).
- **Carico di revisione**: 112 caselle su 340 (33%) hanno confidenza < 0,8 o mancano. Sono quasi
  sempre titolo, partenza/arrivo, tipo di percorso e punti chiave.
- I numeri (data, difficoltà, durata, distanza, salita) tengono anche sui documenti nuovi. Partenza
  e tipo di percorso calano (67% e 83%) e la sequenza dei punti chiave non è alla portata delle
  regole: sono i campi che la revisione (Claude Code nella sessione di lavoro) deve scrivere.

## Ricostruzione delle tracce

Geocodifica sul gazetteer locale (116.126 luoghi OSM con nome, nessun servizio esterno), routing
GraphHopper con preferenza per i sentieri citati, profilo sul DEM. Tolleranze della SPEC: ±10% km,
±15% D+, ±50 m di quota massima; anelli chiusi entro 200 m.

| | auto_ok | da rivedere | fallite |
|---|---|---|---|
| Con i campi rivisti (flusso scelto: parser + Claude Code) | **7 (35%)** | 13 (65%) | 0 |
| Con i soli campi del parser (senza revisione) | 3 (15%) | 11 (55%) | 6 (30%) |
| Fixture #0 Val d'Inferno | auto_ok: +5,5% km, +10,7% D+, −8 m di quota massima | | |

- Punti chiave geocodificati: **116 su 122 (95%)**.
- Quota media della traccia sui sentieri citati: 49% (le locandine citano spesso solo una parte
  dei sentieri percorsi).
- Tempo di ricostruzione: 1,9 s in media per attività (massimo 6 s), routing compreso.

Cause tra le 13 da rivedere (più cause per attività):

| Causa | Attività |
|---|---|
| Dislivello in salita fuori tolleranza | 7 |
| Distanza fuori tolleranza | 6 |
| Punto chiave non trovato nei luoghi OSM | 6 punti in 5 attività |
| Sentieri citati assenti da OSM e OSM2CAI (670, 694 a San Pellegrino; 80 sul Baldo) | 2 |
| Quota massima fuori tolleranza (Laghi del Latte presi per la forcella omonima, +170 m) | 1 |
| Dislivello dichiarato incoerente con le quote della locandina (Monte Cavone: 670 m dichiarati, almeno 837 m tra partenza e quota massima) | 1 |

Lette una per una, le 13 si dividono in tre gruppi:

1. **Dati dichiarati imprecisi o incoerenti** (4): Monte Cavone (dislivello impossibile), Val di
   Cembra (14 km dichiarati; la relazione OSM della tappa misura 12,2 km, la traccia calcolata
   12,6: −10,2%, appena fuori tolleranza), Lago della Selva (discesa sulla forestale, non
   descritta come punto: −18%), Corno Nero («circa 10 km», calcolati 12).
2. **Geocodifica** (5): nomi molto comuni (Moarhof, Wetterkreuz, San Giacomo attorno a Tiso),
   nomi solo tedeschi in OSM (Laghi del Latte = Milchseen), torrenti non presenti nel gazetteer
   (Torrente Aviana), locali minori (Baita Pauli, Casoni di Valfredda).
3. **Scelta del percorso tra punti giusti** (4): Monte Cauriol (le «vie» Italiana e Austriaca non
   hanno numero), Cascate di Barbiano, Malga Cislon, Lago di Erdemolo e Rifugio Sette Selle (+25%
   di dislivello con tutti i punti trovati e il 90% della traccia sui sentieri citati: il
   saliscendi tra lago e rifugio pesa più del previsto). Servono uno o due punti di passaggio in
   più, cioè la correzione manuale prevista dalla revisione (§7.7).

## Tempo e costo per attività

| Passo | Tempo per attività | Costo |
|---|---|---|
| Download educato | 3,4 s (limite di cortesia: 3 s per host) | 0 € |
| Testo + OCR | 0,5 s (3-5 s per pagina scansionata) | 0 € |
| Parser a regole | 0,01 s | 0 € |
| Ricostruzione e verifica | 1,9 s | 0 € (GraphHopper e PostGIS locali) |
| Revisione Claude Code (lettura del PDF, campi mancanti, punti chiave) | 2-4 minuti di sessione, stima | 0 € di API: rientra nell'abbonamento Claude Pro, consuma la quota di utilizzo |

**Costo LLM: zero chiamate API.** L'estrazione strutturata della SPEC (Claude API con JSON Schema)
è sostituita, come deciso alla Fase 0, da parser a regole più revisione nella sessione di Claude
Code. Il limite non è il denaro ma la quota di utilizzo dell'abbonamento: la revisione del pilota
(20 locandine più 8 di controllo) ha occupato una parte consistente di una sessione.

## Stima per l'ingestion completa

Sulle 5 sezioni del pilota: 344 PDF candidati dal nome. Dall'esperienza del pilota, dopo la
classificazione sul testo ne resteranno circa 150-200 attività escursionistiche (più le righe dei
calendari).

| Voce | Stima |
|---|---|
| Download | 344 × 3,4 s ≈ 20 minuti |
| Testo, parser, ricostruzione | ≈ 15 minuti |
| Revisione Claude Code | 150-200 attività × 2-4 min ≈ 5-13 ore di sessione, in più sessioni per i limiti di utilizzo |
| Esito atteso | circa 35% auto_ok, 65% da rivedere con motivo, quasi nessuna fallita |

Per tutte le sezioni CAI di Trentino-Alto Adige e Veneto la quantità va prima misurata con la sola
scoperta (metadati, nessun download). La revisione cresce in proporzione ed è il collo di bottiglia.

## Come rifare il pilota

```bash
cd services/ingest
.venv/bin/python -m cordata_ingest.activities discover     # metadati dei PDF delle sezioni pilota
.venv/bin/python -m cordata_ingest.activities archive      # 51 PDF candidati, archivio privato
.venv/bin/python -m cordata_ingest.activities extract      # testo, OCR, dati personali rimossi
.venv/bin/python -m cordata_ingest.activities gazetteer    # luoghi OSM con nome in PostGIS
.venv/bin/python -m cordata_ingest.activities reconstruct  # tracce (anche --solo-parser)
.venv/bin/python -m cordata_ingest.activities report       # questa cartella
```

Servono PostGIS con i dati della Fase 1 e GraphHopper avviato (vedi `services/routing/README.md`).
