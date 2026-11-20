# 0015 – Catalogo Dolomiti e Prealpi, soglia di affidabilità, rifacimento della UI

Data: 20/11/2026 · Stato: accettata (scelte dell'utente con domande a risposta multipla)

## Contesto

Fasi 0–5 completate e pubblicate. Il catalogo ha 90 escursioni dalle locandine CAI, di cui 30
con traccia verificata automaticamente; nelle Dolomiti sono circa 28, e solo 6 verificate.
Le sezioni scoperte (39, Veneto, Alto Adige e SAT) hanno pubblicato circa 3.850 documenti che
sembrano escursioni, programmi o ciaspolate (2017–2026), ma ne abbiamo archiviati 116. Molte
sezioni di pianura (Treviso, Vicenza, Mestre…) organizzano gite in Dolomiti: conta la meta,
non la sede della sezione.

## Decisioni

1. **Pausa della Fase 6** (meteo e valanghe): prima si migliora quello che c'è.
2. **Area del catalogo: Dolomiti e Prealpi**, decisa dalla **meta** dell'escursione (partenza,
   punti chiave e sentieri citati), non dalla sede della sezione:
   - i gruppi dolomitici con le loro valli (Fassa, Gardena, Badia, Ampezzo, Cadore,
     Agordino, Zoldo, Primiero, Fiemme e Lagorai, Comelico, Sesto) e le Dolomiti di Brenta;
   - le Prealpi venete e trentine: Piccole Dolomiti, Pasubio, Carega, Lessinia, altopiani di
     Asiago, Folgaria e Lavarone, Grappa, Vette Feltrine, Prealpi Bellunesi e Alpago;
   - esclusi: Dolomiti Friulane e Prealpi Carniche (servirebbero fonti del Friuli),
     Ortles-Adamello, Val di Non e Val di Sole, Monte Baldo, Alpi Aurine e Venoste.
   Il confine è un poligono in `config/areas/dolomiti-prealpi.geojson`, disegnato a mano lungo
   valli e confini regionali e documentato con una mappa.
3. **Punteggio di affidabilità 0–100%** per ogni escursione; **si pubblica solo da 80%** in su.
   Il punteggio unisce la lettura della locandina (campi chiave presenti e coerenti, punti
   localizzati senza ambiguità) e la corrispondenza della traccia ricostruita con la locandina
   (distanza, dislivello, punto più alto, quota sui sentieri citati). Sotto l'80%
   l'escursione resta in un elenco di revisione non pubblico; di ogni lotto si controlla a
   campione una parte di quelle pubblicate. Le escursioni senza traccia non si pubblicano.
4. **Tutti gli anni (2017–2026)**: le locandine passate diventano **itinerari senza data** (la
   locandina resta collegata come fonte), quelle future restano **uscite con data** della
   sezione. Gli itinerari ripetuti si fondono (deduplica §7.5).
5. **Ingestione a lotti per sezione**, non più a blocchi con revisione completa: la soglia
   sostituisce la revisione una per una. Restano tutte le regole di prima: crawling cortese
   (User-Agent, cache, limite di frequenza, backoff, robots.txt), nessun crawler periodico,
   nessun dato personale, dalla locandina solo riassunto, link e data, PDF mai ripubblicati e
   archivio grezzo solo in `data/` (escluso da git).
6. **Rifacimento della UI**, su quattro aree insieme: Esplora (lista e mappa), scheda
   dell'escursione, identità visiva (colori, caratteri, icone, tema scuro), navigazione e primo
   uso. Prima i **mockup** (schermate di telefono) da approvare, poi l'implementazione. Le
   verifiche su iPhone si fanno anche nel simulatore di Xcode sul Mac dell'utente, collegato
   alla sessione quando serve.

## Conseguenze

- Il catalogo può crescere di molto, ma solo con escursioni affidabili: meglio meno schede
  giuste che tante sbagliate.
- Le escursioni del catalogo attuale fuori area (Ledro, Baldo, Val di Non, Ortles…) escono
  dall'app; restano nell'archivio.
- La Fase 6 riparte dopo questo lavoro, sulla nuova area.
