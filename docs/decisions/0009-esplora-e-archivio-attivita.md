# ADR 0009 – Esplora, archivio delle attività e fonti della Fase 3

- **Stato**: accettata
- **Data**: 17/11/2026

## Contesto

La Fase 3 (SPEC §11) chiede Esplora con lista, mappa, filtri e preset, la scheda completa,
l'archivio delle attività, la deduplica, la ricerca in linguaggio naturale e l'integrazione di
Open Data Hub e SAT. Vincoli: costo zero e sito statico (ADR 0005), nessun modello a pagamento
(ADR 0006), nessuna chiamata dei client a servizi pubblici (SPEC §3).

## Decisioni

1. **Esplora tutta nel browser, su un indice statico.** La pipeline produce
   `data/esplora/index.json` (2179 proposte: sentieri del catasto, attività, itinerari; 1,1 MB,
   circa 250 kB compresso) con metriche, mini-profilo, etichette dai luoghi OSM vicini alla
   traccia (lago, cima, rifugio, acqua, panorama) e stagione indicativa dalla quota; e
   `data/esplora/luoghi.json` (17.797 cime, rifugi, laghi, paesi, passi, valli) per la ricerca e
   per «entro N km da». Filtri, ordinamenti e «Cerca in quest'area» girano nel browser: nessun
   server, nessun geocoder esterno.
2. **Ricerca in linguaggio naturale a regole.** La frase diventa filtri **visibili come chip**
   modificabili (§5.7 b); ciò che non è filtrabile (mezzi pubblici) viene detto, i minuti di
   viaggio diventano chilometri in linea d'aria con la stima dichiarata. Se nessuna regola
   riconosce la frase, è una ricerca per nome.
3. **Tracce non verificate: solo dati dichiarati.** Un'attività «da rivedere» compare con la
   traccia tratteggiata e un avviso; distanza, dislivello, tempi, mini-profilo ed etichette non
   vengono calcolati da quella traccia (potrebbero essere falsi) ma presi dalla locandina o dai
   nomi dei punti chiave.
4. **Deduplica (§7.5)** con distanza di Hausdorff (≤ 300 m) e rapporto delle lunghezze (≤ 1,25)
   su tracce ricampionate ogni 50 m, Fréchet discreta come conferma; «variante» se una traccia
   corre lungo l'altra. Il canonico è la traccia verificata più recente; in Esplora i doppioni
   non si ripetono. Sulle 28 attività di oggi nessun doppione.
5. **Open Data Hub non entra.** Su 600 record i CC0 non hanno traccia e quelli con traccia sono
   «Closed» (non ridistribuibili).
6. **SAT dai siti delle sezioni** (decisione dell'utente): ricerca di al massimo tre domini
   plausibili per sezione, una richiesta alla home; 17 siti trovati, 5 WordPress con l'API dei
   media aperta. Le protezioni anti-bot non si aggirano.
7. **Ingestion a blocchi con revisione.** Primo blocco: 8 gite 2026 di SAT Pergine. Le
   correzioni della revisione diventano regole generali del parser e test di regressione; la
   precisione si misura prima dei ritocchi (83% sul blocco) e dopo (97%), insieme a pilota (98%)
   e locandine mai viste (92%) per evitare regressioni.
8. **Geocodifica ancorata al comune** quando la locandina lo indica: i nomi comuni («San
   Martino in Monte») si cercano entro 15 km dal comune.

## Conseguenze

- La PWA resta pubblicabile come sito statico (GitHub Pages ora, Cloudflare Pages poi).
- I siti SAT non WordPress (12) richiedono adapter dedicati: lavoro della fase successiva di
  ingestion, insieme ai blocchi delle altre sezioni.
- Il blocco Condizioni (meteo, valanghe) e i mezzi pubblici restano segnaposto dichiarati fino
  alle fasi 6 e successive.
