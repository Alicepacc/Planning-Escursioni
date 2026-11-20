# 0015 – Catalogo Trentino-Alto Adige e Dolomiti, soglia di affidabilità, rifacimento della UI

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
2. **Area del catalogo: tutto il Trentino-Alto Adige più Dolomiti e Prealpi venete**, decisa
   dalla **meta** dell'escursione (traccia, o partenza e punti chiave), non dalla sede della
   sezione. Prima proposta: solo Dolomiti e Prealpi; corretta dall'utente lo stesso giorno
   («Val di Non non va esclusa»):
   - Trentino-Alto Adige intero, con il confine OSM della regione (Val di Non e di Sole,
     Ortles, Adamello trentino, Venosta, Aurina, Ledro e Alto Garda compresi);
   - in Veneto: provincia di Belluno fino al confine friulano, Prealpi vicentine e trevigiane
     (Piccole Dolomiti, Pasubio, Carega, Lessinia, Asiago, Grappa), Alpago e Cansiglio;
   - esclusi: Friuli (Dolomiti Friulane, Alpi e Prealpi Carniche, anche le cime carniche del
     Comelico), Lombardia, Austria, Monte Baldo veronese e pianura.
   Il confine è in `config/areas/catalogo.geojson` (regione OSM unita al poligono veneto,
   semplificato a circa 150 m); mappa di controllo in `reports/catalogo/area-del-catalogo.jpg`.
   Del catalogo attuale restano dentro 84 escursioni su 90.
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
- Le 6 escursioni del catalogo attuale fuori area (Campione del Garda, Zillertal, Monte
  Palombino e tre senza coordinate) escono dall'app; restano nell'archivio.
- La Fase 6 riparte dopo questo lavoro, sulla nuova area.
