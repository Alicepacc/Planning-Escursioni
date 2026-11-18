# Fase 4 – Planner e generatore di proposte: rapporto di fine fase

Data: 17/11/2026. Tutto ciò che è riportato è stato eseguito e osservato nel browser (Playwright,
telefono Pixel 7 e desktop 1280 px, anche sulla demo pubblicata) o nei test; i limiti sono indicati
esplicitamente. Decisioni: [ADR 0010](../../docs/decisions/0010-routing-nel-browser.md) (routing
nel browser) e [ADR 0011](../../docs/decisions/0011-planner-e-generatore-di-proposte.md) (planner e
generatore).

## 1. Cosa è stato fatto

| Voce della SPEC (§11, Fase 4) | Esito |
|---|---|
| Routing vincolato alla difficoltà | **fatto**, nel browser: grafo pedonale dell'area pilota in 562 tasselli (scala CAI del catasto o `sac_scale`, segnavia, visibilità, segnalazioni OSM2CAI); A* sul tempo CAI con preferenza per i sentieri segnati; i tratti oltre la difficoltà scelta (default E) sono esclusi |
| Editing completo (§5.3) | **fatto**: tocca per aggiungere (aggancio entro 30 px), trascina, tocca la linea per inserire, elimina, annulla/ripeti, chiudi/riapri anello, inverti, andata e ritorno, tratti a mano libera tratteggiati, «punto al centro» per chi usa la tastiera |
| Statistiche live | **fatto**: km, D+, D−, quota massima, tempo netto e «col tuo passo» (allenamento, soste, gruppo), difficoltà massima incontrata; stesso metodo delle schede; profilo altimetrico interattivo |
| Avvisi (inclusi gli `issues` OSM2CAI) | **fatto**: segnalazioni del catasto, oltre la difficoltà, vie ferrate, traccia poco visibile, senza segnavia, strade con traffico, tratti diventati a mano libera (con «Ammetti un grado in più»), rifugi lungo il percorso. Zero termico e rifugi aperti: con i dati meteo (Fase 6) |
| Import GPX | **fatto**: «Mantieni la traccia» o «Aggancia ai sentieri» (dove i sentieri si allontanano resta la traccia); quote dal modello del terreno; export GPX |
| Stato nell'URL | **fatto**: link condivisibile, Indietro annulla, ultimo piano ripreso dal browser, percorsi salvati |
| Generatore «stile sezione CAI» (§5.7 a) | **fatto**: anelli, andata e ritorno, traversate con vincoli di tempo, dislivello, difficoltà, desideri (cima, lago, rifugio, panorama), mese e ciaspole; funzione di qualità esplicita; locandina composta dai dati con l'etichetta «proposta generata, non verificata sul terreno»; apertura nel planner |
| Valutazione del generatore nell'harness | **fatto**: `pnpm run eval:generatore` sulle 13 gite reali con traccia verificata ([risultati](generatore/risultati.md)) |
| Collegamenti | «Modifica nel planner» dalle schede di attività e itinerari |

## 2. Numeri

- **Grafo**: 562 tasselli, 66 MB (circa 23 MB compressi; un tassello tipico 86 kB, 29 kB
  compresso). Sulla fixture Val d'Inferno il router dà 15,3 km (locandina 15,5), +999 m (950),
  quota massima 2245 m (2253), in 55 ms con 4 tasselli: entro le tolleranze di auto_ok.
- **Planner**: dalla scheda della fixture al planner 15,1 km e +993 m in 0,7 s; una proposta del
  generatore si riapre nel planner con 6 punti e gli stessi numeri (12,7 km, +915 m, 5:00 h).
- **Import GPX** (traccia di 174 punti): agganciata ai sentieri 15,1 km e +988 m, con 1 tratto su 22
  rimasto sulla traccia originale; mantenuta a mano libera con un link di 664 caratteri.
- **Generatore** (13 gite reali, finestra di tempo ±20%, dislivello ±25%):

  | Misura | Prima versione | Finale |
  |---|---|---|
  | Gite con almeno una proposta | 11/13 | 13/13 |
  | Gita reale riscoperta nella 1ª proposta | 0/13 | 2/13 |
  | … tra le prime 3 (e 5) | 3/13 | 5/13 (38%) |
  | Meta principale raggiunta da una delle prime 5 | 6/13 | 8/13 (62%) |
  | Copertura reciproca migliore, media | 46% | 58% |
  | Tempo di generazione, media | 0,33 s | 0,42 s |

  Le modifiche sono regole generali (finestra di tempo misurata sul tempo e non sul costo del
  router, vetta e non anticima, anelli su misura e senza meta, finestra rispettata, ciaspole), ma
  sono state provate sulle stesse 13 gite: i numeri sono indicativi finché non ci sarà un insieme
  di controllo.
- **Test**: 85 test Python e 72 test web (più la valutazione su richiesta); lint e type-check
  puliti.

## 3. Demo

https://alicepacc.github.io/Planning-Escursioni/pianifica (verificata dopo la pubblicazione: due
tocchi danno un percorso di 2,6 km agganciato al sentiero 332, nessun errore).

| File | Cosa mostra |
|---|---|
| `screenshots/1-planner-telefono.jpg` | Anello disegnato con 4 tocchi e «Chiudi ad anello»: statistiche, strumenti, avvisi |
| `screenshots/2-planner-profilo-telefono.jpg` | Lo stesso piano: profilo altimetrico e luoghi lungo il percorso |
| `screenshots/3-import-gpx-telefono.jpg` | Import di una traccia GPX: aggancia o mantieni |
| `screenshots/4-traccia-importata-telefono.jpg` | Traccia mantenuta a mano libera, tratteggiata, quote dal modello del terreno |
| `screenshots/5-proposte-telefono.jpg` | «Proponi un giro»: anello di 4–5:30 h con un lago, anteprima viola sulla mappa e locandina |
| `screenshots/6-da-scheda-al-planner-desktop.jpg` | La fixture aperta dalla scheda con «Modifica nel planner» |
| `screenshots/7-proposta-cima-desktop.jpg` | Proposta con una cima: locandina con descrizione, tappe e motivi |
| `screenshots/8-proposta-nel-planner-desktop.jpg` | La proposta aperta nel planner, pronta da modificare |

## 4. Problemi aperti

- **Generatore, casi non riscoperti**: gite su strade forestali (Tovel), mete assenti dai luoghi di
  OpenStreetMap o lontane dal sentiero (Cima Bedolè), giri culturali brevi (castelli e abbazie non
  sono tra le mete), traversate. Serve un insieme di controllo: i prossimi blocchi di attività
  verificate.
- **Il generatore gira sul thread principale** (0,4–1,3 s): su telefoni lenti conviene un Web Worker.
- **Zero termico e apertura dei rifugi**: avvisi segnaposto fino ai dati meteo (Fase 6); per i
  rifugi manca ancora una fonte aperta degli orari di apertura.
- **Peso del grafo**: adeguato all'area pilota; per un'area più ampia servirà un formato binario.
- **Molti punti** quando si apre una scheda nel planner (uno ogni 800 m): si potrebbe usare lo
  stesso adattamento delle proposte, che ne mette solo dove servono.
- Le schede dei sentieri del catasto (Fase 1) non hanno ancora «Apri nel planner».
- **Accessibilità della mappa**: punti come pulsanti, Canc per eliminare, «punto al centro»; la
  verifica completa è nella Fase 8.

## 5. Risposte dell'utente (17/11/2026)

1. **Prossimo passo: Fase 5** (uscite di gruppo); all'inizio si verificano i limiti attuali dei
   backend gratuiti e si sceglie insieme quale usare.
2. **Verifiche**: l'utente prova planner e generatore sulla demo prima di proseguire; il lavoro
   riprende dalle sue osservazioni.
3. **Generatore, quando ci si torna**: prima la **valutazione indipendente** (gite verificate nuove,
   mai usate per la messa a punto), poi le proposte per **inverno e strade forestali**.

## 6. Osservazioni e decisioni dell'utente (18/11/2026)

- **Modello dei dati** ([ADR 0012](../../docs/decisions/0012-escursioni-solo-dalle-locandine.md)):
  le escursioni proposte vengono solo dalle locandine delle sezioni; il catasto CAI diventa un
  livello della mappa (toccando un sentiero se ne vedono le informazioni); il generatore resta solo
  come strumento del planner, etichettato «non verificato».
- **Legenda della mappa**: oggi manca; si fa insieme alla modifica del modello.
- **Profilo e mappa nelle schede**: scorrendo il profilo il punto corrispondente sulla mappa non si
  vede, perché la mappa resta in alto. Da risolvere nella rifinitura della UX (mappa fissa accanto
  al profilo su desktop, mini-mappa o mappa ferma sul telefono).
- **Ordine dei lavori** dopo le verifiche sulla demo: modifica del modello e legenda, poi blocchi di
  ingestion, poi Fase 5 (sostituisce la risposta del 17/11 «prossimo passo: Fase 5»).
