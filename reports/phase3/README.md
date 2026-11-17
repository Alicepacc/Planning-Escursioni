# Fase 3 – Esplora, archivio attività e altre fonti: rapporto di fine fase

Data: 17/11/2026. Tutto ciò che è riportato è stato eseguito e osservato nel browser o nei
dati; i limiti sono indicati esplicitamente. Decisioni: [ADR 0009](../../docs/decisions/0009-esplora-e-archivio-attivita.md).

## 1. Cosa è stato fatto

| Voce della SPEC (§11, Fase 3) | Esito |
|---|---|
| Esplora: lista e mappa sincronizzate (§5.1) | **fatto**: 2.179 proposte (2.150 sentieri del catasto, 28 attività CAI e SAT, 1 itinerario); punti sulla mappa cliccabili, card evidenziata, «Cerca in quest'area» dopo lo spostamento |
| Ricerca testuale e geocoding locale | **fatto**: suggerimenti da 17.797 luoghi OSM (cime, rifugi, laghi, paesi, passi, valli) e dai nomi delle proposte; scegliendo un luogo si filtra entro 10 km |
| Filtri | **fatto**: tempo, km, dislivello, quota massima, difficoltà (T, E, EE, EEA, EAI), tipo, luoghi lungo il percorso, stagione, distanza da me, fonte, solo in programma. Mezzi pubblici: segnaposto dichiarato (fase successiva) |
| Preset, ordinamento, card | **fatto**: Mezza giornata, Giornata intera, Facile con bambini, Panoramico, Laghi, Cima; ordinamento per rilevanza, distanza, durata, dislivello, data; card con i dati in ordine fisso |
| Scheda completa (§5.2) | **fatto** per attività e itinerari: metriche, sintesi dai soli dati, attività e locandina, profilo interattivo, tappe con tempi cumulati, sentieri percorsi, attrezzatura e periodo indicativi, come arrivare, confronto con la locandina, Salva / GPX / KML / Condividi. Condizioni (meteo, valanghe) e «Organizza uscita»: segnaposto per le fasi 5 e 6 |
| Archivio attività | **fatto**: 28 schede (20 del pilota + 8 di SAT Pergine) da 11 sezioni; tracce non verificate tratteggiate, con avviso e solo dati dichiarati |
| Ricerca in linguaggio naturale (§5.7 b) | **fatto**, a regole: la frase diventa chip modificabili; esempio della SPEC nei test |
| Deduplica (§7.5) | **fatto**: Hausdorff + Fréchet + lunghezze; nessun doppione tra le 28 attività (verificato), algoritmo coperto da test sintetici |
| Integrazione SAT | **fatto in parte**: 17 siti di sezione trovati e registrati; primo blocco di 8 gite 2026 di SAT Pergine portato in app. I 12 siti non WordPress richiedono adapter |
| Integrazione Open Data Hub | **valutata e scartata**: su 600 record nessuna traccia con licenza aperta |

## 2. Numeri

- **Attività**: 28 da 11 sezioni (CAI Bolzano, Bressanone, Appiano; SAT Pergine, Borgo
  Valsugana, Mezzolombardo, Trento, Aldeno, Spormaggiore, Rovereto, trekking del 150°);
  **12 tracce verificate** (auto_ok): 7/20 del pilota (invariato), 5/8 del blocco SAT Pergine.
- **Parser** (valori corretti, punti chiave esclusi): pilota 98,1%, locandine mai viste 92,4%,
  blocco SAT Pergine 83% prima della revisione e 97,1% dopo (le correzioni sono diventate regole
  generali e test).
- **Test**: 81 test Python e 34 test web, lint e type-check puliti.

## 3. Demo

Schermate in `screenshots/` (telefono Pixel 7 e desktop 1280 px):

| File | Cosa mostra |
|---|---|
| `1-esplora-telefono.jpg` | Mappa con le proposte (rosso: attività; blu: sentieri del catasto), ricerca, preset, card |
| `2-ricerca-linguaggio-naturale.jpg` | «traversata EE con un rifugio, giornata intera» → chip 4–8 h, EE, EEA, Traversata, Rifugio: 25 proposte |
| `3-filtri.jpg` | Pannello dei filtri con lo stato della ricerca precedente |
| `4-scheda-attivita-telefono.jpg` | Monte Mulaz (SAT Pergine): traccia verificata, punti numerati, sintesi, metriche della locandina |
| `5-scheda-attivita-intera.jpg` | La stessa scheda intera: profilo, tappe, sentieri, attrezzatura, come arrivare, confronto, azioni |
| `6-esplora-desktop.jpg` | Desktop con il preset «Cima»: lista a sinistra, mappa a destra |

Verifiche con Playwright: nessun errore in pagina; nessuno scorrimento orizzontale sul telefono;
la mappa si ridimensiona con il layout; la ricerca in linguaggio naturale produce i chip attesi.

## 4. Problemi aperti

- **Adapter per i siti SAT non WordPress** (12 sezioni) e ingestion a blocchi delle altre
  sezioni CAI: il collo di bottiglia resta la revisione.
- **Coda di revisione per l'utente** (§7.7): rimandata a quando l'utente farà le sue verifiche.
- **Tracce da rivedere** (16 su 28): cause tipiche già note (nomi comuni, luoghi assenti da OSM,
  dati dichiarati imprecisi); servono il punto di passaggio manuale e la scelta del candidato in
  mappa, cioè la coda di revisione.
- **Indice di Esplora**: 1,1 MB (circa 250 kB compresso), adeguato oggi; con migliaia di attività
  andrà diviso per area.
- La pagina della fixture e le schede delle attività condividono un componente nuovo: la scheda
  dei sentieri del catasto (Fase 1) non ha ancora le azioni Salva / GPX / Condividi.
