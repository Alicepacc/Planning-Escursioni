# Fase 1 – Dati OSM e mappa: rapporto di checkpoint

Data: 16/11/2026. Tutto ciò che è riportato è stato eseguito e osservato nel browser o nei
dati; i limiti sono indicati esplicitamente.

## 1. Cosa è stato fatto

| Voce della SPEC (§11, Fase 1) | Esito |
|---|---|
| Sincronizzazione incrementale OSM2CAI (§6.1) | **fatto**: 2.252 sentieri di Trentino-Alto Adige e Veneto (`sda` 3 e 4) in 57 minuti, nessun errore; il secondo giro scarica solo i 4 indici e finisce in 8 secondi |
| Import dell'estratto OSM in PostGIS | **fatto**: area pilota in 19 secondi (osm2pgsql, output «flex»): 7.132 relazioni escursionistiche, 491.665 tratti percorribili, 88.682 punti di interesse |
| Sentieri e POI in PMTiles | **fatto**: 79.725 tratti di sentiero con i numeri di tutti i sentieri che li percorrono e 46.150 POI, 19,7 MB (sotto il limite di 25 MiB di Cloudflare Pages) |
| Mappa con ombreggiatura | **fatto**: base OpenFreeMap, rilievo e isoipse da Mapterhorn calcolate nel browser, sentieri colorati per difficoltà con lettere in legenda, POI con quote |
| Scheda base di sentiero e itinerario con profilo | **fatto**: 2.150 schede di sentieri del catasto più l'itinerario della fixture, con profilo interattivo sincronizzato con la mappa |
| Dislivello e tempi con test unitari | **fatto**: modello CAI verificato sul diagramma ufficiale, DIN 33466 (fixture 7:00), calibrazione su 1.375 sentieri; 59 test Python e 20 test web |
| Wireframe UX | **fatto**: sei schermate in `docs/ux/wireframes.html` (anteprima: `docs/ux/wireframes.png`) |

## 2. Demo

Schermate da telefono (Pixel 7) in `screenshots/`:

| File | Cosa mostra |
|---|---|
| `1-esplora.jpg` | Apertura sul Lagorai: sentieri colorati per difficoltà, rilievo, isoipse |
| `2-esplora-sentiero-toccato.jpg` | Tocco sul sentiero 360: anteprima con i dati del catasto e traccia evidenziata |
| `3-sentiero-332.jpg` | Scheda del 332: metriche ufficiali, profilo per pendenza, percorribilità, confronto ufficiale/calcolato |
| `4-itinerario-val-d-inferno.jpg` | Fixture: punti chiave numerati su mappa e profilo, tappe con tempi cumulati, sentieri percorsi, confronto con la locandina |
| `5-dettaglio-z14.jpg` | Dettaglio topografico a zoom 14: isoipse quotate, numeri dei sentieri, cime, laghi, bivacchi |

Interazioni verificate con Playwright: tocco su un sentiero → anteprima con i dati del catasto;
scorrimento del profilo con dito o mouse e con le frecce della tastiera → il marker si muove
sulla mappa; nessun errore nella console del browser.

## 3. Modelli di calcolo (ADR 0007)

**Tempi.** Il Quaderno CAI n. 1 rimanda al diagramma dei Sentieri Svizzeri. Il polinomio usato
riproduce il diagramma ufficiale: su 620 isocrone digitalizzate lo scarto medio è di 0,085
minuti. Sui casi della SPEC dà 20,0 / 48,8 / 14,2 / 27,5 minuti. I tempi ufficiali OSM2CAI
risultano calcolati con la stessa formula.

**Confronto con il catasto** (1.375 sentieri validati dell'area pilota, calcolo indipendente):

| | Errore medio | Distorsione | Errore mediano | Entro ±15% |
|---|---|---|---|---|
| Tempo (modello CAI, parametri scelti) | 18,6 min | −2,1 min | 14,3% | 53% |
| Dislivello in salita senza filtro | 57 m | −24 m | 11,3% | 57% |
| Dislivello in salita con il filtro scelto (75 m, soglia 10 m) | 92 m | −82 m | 19,6% | 43% |

Il catasto conta tutte le micro-risalite; le sezioni dichiarano un dislivello «da escursionista»
(fixture: 950 m dichiarati, 1.037 m calcolati con il filtro, 1.175 m senza). Per questo le schede
mostrano i valori ufficiali quando esistono e i calcolati come confronto; i parametri del
filtro si ricalibrano nella Fase 2 sui dislivelli dichiarati dalle 20 attività del pilota.

**Fixture Val d'Inferno** (traccia ricostruita nello spike della Fase 0):

| | Locandina | Calcolato | Esito |
|---|---|---|---|
| Lunghezza | 15,5 km | 15,62 km | +0,8% |
| Salita / discesa | 950 / 950 m | 1.037 / 1.037 m | +9,2% (entro ±15%) |
| Quota massima | 2.253 m | 2.245 m | −8 m |
| Tempo | 7:00 h | 5:50 h netto (modello CAI) → 7:00 con soste +20%; DIN 7:29 | coerente |
| Sentieri citati | 332, 360, 326 + reti | 332, 360, 326, AVG, SdP, TL, SI (+ L31, L35) | trovati tutti |

## 4. Problemi trovati e risolti

| Problema | Effetto | Soluzione |
|---|---|---|
| `minzoom` per singolo elemento in tippecanoe 2.49 | sparivano quasi tutti i sentieri dai tile (1 su 7 nel tile della fixture) | filtro per zoom (`-j`) al posto del `minzoom` |
| Regola `build/` nel `.gitignore` | il pacchetto `cordata_ingest/build` non era nel repository e la CI falliva | regola limitata a `apps/web/build/` |
| MapLibre 6 (solo ESM) | il worker della mappa non veniva trovato | worker importato come asset con `setWorkerUrl` |
| Isteresi e media mobile ai bordi | una salita rettilinea di 200 m risultava 189 m | residuo finale sommato, finestra simmetrica ai bordi; test dedicati |
| Lunghezza misurata sulle corde | −2,6% sulla fixture (i tornanti venivano tagliati) | distanza lungo la traccia originale |
| Campi OSM2CAI | `name` a volte è un dizionario per lingua; geometrie con quota | normalizzazione dei campi; geometrie 2D |

## 5. Cosa non è stato verificato

- **Pubblicazione online**: il sito è statico e pronto (119 MB, 2.150 schede prerenderizzate) ma
  non è ancora pubblicato (vedi le domande).
- **Routing sul Mac** con Tailscale Funnel: istruzioni scritte, non provate (serve il Mac).
- **Aggiornamento periodico** di OSM2CAI ed estratto OSM: il comando incrementale c'è, la
  pianificazione no (nessun server sempre acceso; da decidere con la pubblicazione).
- **Tedesco e inglese**: la struttura i18n c'è, i testi delle nuove pagine sono solo in italiano.
- **PWA (offline, installazione)**, accessibilità con axe, prestazioni: fasi 7 e 8.
- Le schede prerenderizzate contengono i dati due volte (HTML e JSON): da ottimizzare se le
  dimensioni diventano un problema.

## 6. Decisioni

- ADR 0005 – architettura a costo zero (sito statico, Mac con Tailscale Funnel per il routing).
- ADR 0006 – estrazione delle locandine con parser a regole e revisione in sessione.
- ADR 0007 – modelli dei tempi e del dislivello, con verifiche e calibrazione.

## 7. Domande per l'utente

Vedi il messaggio di checkpoint: approvazione per la Fase 2, sezioni del pilota (la SPEC ne
chiede almeno 4), pubblicazione della demo, riservatezza della risposta del CAI nel repository
pubblico.
