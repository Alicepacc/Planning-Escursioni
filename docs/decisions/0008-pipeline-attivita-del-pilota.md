# ADR 0008 – Pipeline delle attività CAI: scelte del pilota

- **Stato**: accettata (checkpoint della Fase 2, 16/11/2026)
- **Data**: 16/11/2026

## Contesto

Il pilota della Fase 2 (SPEC §7.6, rapporto in `reports/pilot-2026-11-16/`) ha portato 20
locandine reali dal PDF alla traccia verificata. Senza API a pagamento (ADR 0006) e senza
servizi pubblici chiamati in modo massivo (ADR 0003, 0005).

## Decisioni

1. **Estrazione in due passaggi.** Un parser a regole estrae i campi con confidenza e riga di
   origine; la revisione (Claude Code nella sessione di lavoro) completa i campi a bassa
   confidenza e scrive i punti chiave in ordine. Le revisioni sono file YAML versionati
   (`config/pilot/reviewed/`): fanno da verità di riferimento e da test di regressione. Una
   seconda cartella di locandine mai viste (`config/pilot/holdout/`) misura il parser in modo
   onesto.
2. **Archivio privato.** I PDF e il testo estratto restano in `data/` (escluso da git); il
   rapporto e la PWA mostrano solo sintesi, link all'originale e data, come consente la risposta
   del CAI. I dati personali si tolgono dal testo prima di salvarlo e non entrano mai nei campi.
3. **Gazetteer locale per la geocodifica.** Gli elementi OSM con nome delle categorie utili
   (luoghi, masi, chiese, castelli, malghe, stazioni, fermate…) in PostGIS con indici a trigrammi;
   niente Nominatim. Regole: nome identico prima di simile, tipo atteso dalla prima parola,
   parole distintive obbligatorie, quota verificata sul DEM, raggio dalla lunghezza dichiarata,
   nomi di sentieri e strade come punti di passaggio.
4. **Routing vincolato morbido.** GraphHopper con un'area «citati» (sentieri numerati e itinerari
   citati per nome, buffer 35 m) e priorità ridotta a 0,25 fuori; andata e ritorno come andata
   ripercorsa; deviazioni «vai e torna» su cartelli e località ricondotte all'innesto.
5. **Stato auto_ok** = tolleranze della SPEC (±10% km, ±15% D+, ±50 m di quota massima, anelli
   chiusi) più tre regole confermate dall'utente: dato dichiarato incoerente con la locandina
   escluso dal confronto; almeno un confronto su km o dislivello; al massimo un punto intermedio
   non trovato.
6. **Nessun crawler periodico.** L'ingestion delle altre locandine procede a blocchi nella Fase 3,
   con revisione in sessione; le verifiche dell'utente arriveranno a demo finita.

## Conseguenze

- Il collo di bottiglia è la revisione (circa un terzo dei campi e il 65% delle tracce), non il
  calcolo: il costo è la quota di utilizzo dell'abbonamento, non denaro.
- La coda di revisione del §7.7 servirà quando l'utente farà le sue verifiche.
- Per la SAT si cercano i siti delle singole sezioni (decisione dell'utente).
