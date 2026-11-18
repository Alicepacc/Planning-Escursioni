# ADR 0012 – Le escursioni proposte vengono solo dalle locandine delle sezioni

- **Stato**: accettata (proposta dell'utente, 18/11/2026); da realizzare dopo le verifiche
  dell'utente sulla demo della Fase 4
- **Data**: 18/11/2026

## Contesto

Fino alla Fase 4 Esplora mescolava due cose diverse: i 2.150 sentieri del catasto CAI (OSM2CAI),
elencati come proposte, e le attività estratte dalle locandine pubblicate dalle sezioni sui loro
siti WordPress. L'utente propone di separarle: la rete sentieristica è un dato del territorio, le
escursioni sono le gite scelte e promosse dalle sezioni.

## Decisione

- **Escursioni = solo locandine.** Esplora, ricerca, preset, filtri e ricerca in linguaggio
  naturale lavorano solo sul catalogo delle attività estratte dalle locandine (future e
  archivio), unite in itinerari quando la stessa gita è proposta da più sezioni o in più anni
  (deduplica, §7.5).
- **Catasto CAI = livello della mappa.** I sentieri di OSM2CAI restano sulla mappa (linee colorate
  per difficoltà, numeri). Toccandone uno si vedono le informazioni del sentiero (numero,
  difficoltà, tempi ufficiali, segnalazioni, link al catasto), ma non è più un'«escursione».
- **Generatore = strumento del planner.** «Proponi un giro» resta solo dentro Pianifica come
  aiuto per comporre un giro proprio, con l'etichetta «non verificato»; non compare mai in Esplora
  né tra le escursioni proposte.
- **Legenda della mappa** insieme a questa modifica: difficoltà (verde T, rosso E, viola EE, nero
  EEA, marrone sconosciuta; tratteggio = difficoltà stimata da OSM), punti delle attività,
  percorsi del planner (blu sui sentieri, arancione tratteggiato a mano libera, viola proposte),
  sempre con testo e non solo colore. Da rivedere i colori dei punti di Esplora: oggi il rosso
  delle attività coincide con quello dei sentieri E.
- **Ordine dei lavori**: prima questa modifica e la legenda, poi i blocchi di ingestion (siti SAT
  WordPress, altre sezioni CAI Alto Adige, metadati CAI Veneto, adapter SAT), poi la Fase 5.

## Conseguenze

- Modello dei dati più chiaro: chi usa l'app distingue la rete dei sentieri dalle gite consigliate.
- **Copertura**: oggi il catalogo ha 28 gite (12 tracce verificate); nelle fonti già scoperte ci
  sono circa 275 PDF classificati come gite (certi o probabili), più libretti annuali e i siti di 17
  sezioni SAT. L'app resta scarna finché i blocchi di ingestion (con revisione) non avanzano: per
  questo l'ingestion viene subito dopo la modifica.
- «Consigliato dal CAI» riguarda la scelta del giro: la linea sulla mappa resta una ricostruzione
  (verificata o no), e la scheda continua a dirlo; le sintesi rispettano le condizioni d'uso dei
  contenuti delle sezioni (sintesi, link e data, nessuna ripubblicazione dei PDF).
- La SPEC va aggiornata (§5.1, §5.7 a) quando la modifica sarà realizzata.
