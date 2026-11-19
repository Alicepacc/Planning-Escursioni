# ADR 0013 – Elenco delle sezioni venete, fascia di confine, attività senza traccia

- **Stato**: accettata (risposte dell'utente del 19/11/2026)
- **Data**: 19/11/2026

## Contesto

Dopo i primi tre blocchi di ingestion (54 escursioni in app) sono emerse tre questioni:

1. L'elenco delle sezioni CAI del Veneto, con i loro siti, è caricato dalla pagina
   `organizzazione.cai.it/gr-veneto/sezioni/` tramite un endpoint del CAI
   (`wp-json/cai-section/v2/sections-list-simple?region=Veneto`), come l'API
   `cai-activities/v1` che non era stata autorizzata.
2. Alcune gite delle sezioni passano fuori dall'estratto OpenStreetMap (Trentino-Alto Adige e
   Veneto): Passo Nota e Adamello lombardo, Zillertal in Austria. Non si ricostruiscono.
3. Le attività con ricostruzione fallita (7) non compaiono in app.

## Decisione

1. **Elenco delle sezioni venete: autorizzato.** Una sola richiesta in lettura, in cache, alla
   directory che ogni visitatore della pagina vede; poi per ogni sito robots.txt, la home e un
   conteggio dei PDF pubblici, come per i siti SAT. L'API `cai-activities/v1` resta esclusa.
2. **Fascia di confine.** L'estratto si allarga a una fascia di circa 20–30 km oltre i confini
   (Lombardia, Friuli, Austria, Svizzera), dove le fonti sono raggiungibili e i termini lo
   consentono (ADR 0004); grafo e tasselli diventano più pesanti.
3. **Attività senza traccia visibili.** Scheda con i dati della locandina, il link
   all'originale e, se nota, la partenza sulla mappa; nessuna linea e una nota che lo dice.
4. **Ritmo**: i blocchi proseguono in automatico (Veneto, poi adapter SAT) e il lavoro si ferma
   solo prima della Fase 5 o per decisioni come queste.

## Conseguenze

- `config/sources/cai_sections.yaml` registra la provenienza dell'elenco veneto.
- Le attività «fallite» non sono più escluse dalla build: entrano senza linea e senza valori
  calcolati.
