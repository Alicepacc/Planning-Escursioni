# ADR 0011 – Planner con stato nell'URL e generatore di proposte nel browser

- **Stato**: accettata (Fase 4)
- **Data**: 17/11/2026

## Contesto

La Fase 4 chiede il planner (SPEC §5.3: routing vincolato alla difficoltà, editing completo,
statistiche e avvisi, import GPX, stato nell'URL) e il generatore di proposte «stile sezione CAI»
(§5.7 a) con la sua valutazione. Vincoli: costo zero, sito statico, nessun servizio pubblico
gratuito chiamato dai client, routing nel browser (ADR 0010).

## Decisioni

### Planner

- **Stato nell'URL**: punti in 1e-5° (circa 1 m), differenze, zigzag, 5 bit per carattere in
  base64url (`p`); tratti a mano libera (`f`), loro forma (`s`), difficoltà (`d`), andata e
  ritorno (`ar`), nome (`n`). Ogni modifica è una voce della cronologia (`goto` *shallow* di
  SvelteKit): **Indietro annulla**, Avanti ripete, il link si condivide. L'ultimo piano resta in
  `localStorage` e si riapre da solo; i piani salvati finiscono nella lista «Salvati» delle schede.
- **Tratti**: «sul sentiero» (router nel browser) o «a mano libera» (linea diretta, tratteggiata e
  dichiarata). Il tocco si aggancia al sentiero ammesso più vicino entro 30 px (60–400 m secondo lo
  zoom); se non c'è, il tratto diventa a mano libera e lo si dice. Un punto lontano dal sentiero è
  collegato con un raccordo tratteggiato. I tratti già calcolati restano in cache: spostare un punto
  ricalcola solo i due tratti vicini.
- **Quote e statistiche**: dal grafo per i tratti sui sentieri; dal **DEM Mapterhorn nel browser**
  (gli stessi tasselli Terrarium del rilievo, decodificati da maplibre-contour con la sua cache)
  per i tratti a mano libera e le tracce importate. Km, D+, D−, quota massima e tempo con lo
  **stesso metodo delle schede** (campioni ogni 15 m, media mobile su 5, isteresi 10 m, modello
  CAI); tempo personalizzabile con allenamento, soste e gruppo (SPEC §8).
- **Avvisi**: tratti oltre la difficoltà, vie ferrate, segnalazioni aperte del catasto OSM2CAI,
  traccia poco visibile, sentieri senza segnavia, strade con traffico, tratti diventati a mano
  libera (con la proposta di ammettere un grado in più), rifugi lungo il percorso con apertura da
  verificare. Zero termico e apertura dei rifugi arriveranno con i dati meteo (Fase 6).
- **Import GPX**: il file resta nel browser. «Mantieni la traccia»: forma semplificata a 6 m
  (Douglas–Peucker), punti di controllo ogni 2 km; «Aggancia ai sentieri»: un punto ogni 600 m e,
  dove il percorso sui sentieri si scosta più di 60 m dalla traccia, resta la traccia originale.
- **Dalle schede** («Modifica nel planner»): la traccia campionata ogni 800 m, con la difficoltà
  della scheda. **Dalle proposte**: punti scelti in modo adattivo (mete, poi un punto solo dove il
  planner si scosta più di 40 m), così bastano pochi punti e il percorso coincide.
- **Attribuzioni** della mappa: compatte sui telefoni, visibili all'apertura, chiuse al primo tocco
  o dopo 6 secondi (restano sul pulsante «i»): aperte coprivano un quarto della mappa e un tocco
  apriva un sito esterno.

### Generatore di proposte

- Gira **nel browser** sullo stesso grafo del planner (nessun server), in circa 0,4 s.
- **Ricerca**: albero dei percorsi migliori dalla partenza (Dijkstra sul costo del router, con il
  tempo netto accumulato); mete raggiungibili nella finestra di tempo (cime, laghi, rifugi, punti
  panoramici, bivacchi; quelle chieste dall'utente se indicate), una per gruppo (tra cime vicine la
  più alta). Candidati: anelli a una o due mete con **penalità ×6 sugli archi già percorsi** (il
  rientro cerca un'altra via), anelli «su misura» con un passaggio scelto sull'**ellisse** che ha
  per fuochi partenza e meta (tempo che manca, il più lontano possibile dall'andata), anelli senza
  meta dove mancano luoghi notevoli, andata e ritorno, traversate verso un arrivo dato.
- **Vincoli rigidi**: tempo netto nella finestra chiesta, dislivello, difficoltà massima, desideri
  soddisfatti (luogo entro 150 m), anelli che non ripercorrono più di metà dell'andata.
- **Funzione di qualità esplicita** (somma di contributi, mostrati come «perché te la propongo»):

  | Contributo | Peso |
  |---|---|
  | quota su sentieri numerati | +40 × quota |
  | strade / strade forestali | −25 / −10 × quota (forestali 0 con le ciaspole) |
  | segnalazioni aperte OSM2CAI | −30 × quota |
  | traccia poco visibile | −10 × quota |
  | varietà (anelli) | +20 × (1 − ripetuto) − 40 × (ripetuto oltre il 20%) |
  | luoghi lungo il percorso | meta migliore + 0,35 × gli altri, al massimo 20 |
  | altezza della cima rispetto alla partenza | fino a +8 |
  | parcheggio entro 400 m dalla partenza | +6 |
  | tempo | −10 × scarto dal centro della finestra |
  | stagione | d'inverno −30 × quota sopra 1800 m (non con le ciaspole) |
  | esposizione al sole (DEM, solo nel browser) | ottobre–aprile +12 × (sole − 0,5); estate +6 × (0,5 − sole) |
  | rifugio a metà giro (desiderio «rifugio») | +8 |

- **Locandina composta solo dai dati, con regole e non con un modello linguistico**: titolo dai
  luoghi del percorso (con gli articoli italiani), descrizione con numeri, nomi, quote e sentieri,
  tappe con tempi cumulati, attrezzatura per stagione, quota e difficoltà (stesse regole delle
  schede), etichetta fissa **«Proposta generata, non verificata sul terreno»**. Nessun server né
  costo, nessuna frase inventata; un modello potrà riscrivere il testo quando ci sarà un server,
  con gli stessi dati e gli stessi controlli.
- **Valutazione nell'harness** (`pnpm run eval:generatore`, rapporto in
  `reports/phase4/generatore/`): per ogni gita reale con traccia verificata il generatore riceve
  solo ciò che chiederebbe un utente (partenza, arrivo per le traversate, tipo, tempo ±20%,
  dislivello ±25%, difficoltà, mese, tipo di meta, ciaspole se la gita è EAI), mai la traccia. Una
  proposta «riscopre» la gita se almeno il 70% di ciascun percorso è entro 150 m dall'altro.

## Conseguenze

- Tutto funziona su GitHub Pages; il grafo dell'area pilota pesa 66 MB (circa 23 MB compressi),
  scaricato a tasselli solo dove serve.
- Le quote dei tratti a mano libera dipendono dal servizio di tasselli DEM già usato dalla mappa;
  senza DEM si usa la quota del sentiero più vicino, e se manca anche quella lo si dichiara.
- Il generatore è stato messo a punto sulle stesse 13 gite su cui è valutato (non c'è ancora un
  insieme separato): i numeri vanno letti come indicativi finché i prossimi blocchi di attività
  verificate non daranno un insieme di controllo.
- I pesi della funzione di qualità sono scelte esplicite e modificabili; l'harness dice se una
  modifica migliora o peggiora la riscoperta delle gite reali.
