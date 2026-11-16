# Pilota Fase 2: problemi trovati e proposte (16/11/2026)

Numeri in [`metrics.md`](metrics.md), schede in [`pilot.html`](pilot.html).

## 1. Fonti delle sezioni

- **SAT.** Sul sito centrale (`sat.tn.it`, 1122 PDF) le locandine delle sezioni arrivano al 2023;
  il calendario «programma gite» è un widget caricato dal browser, senza feed; le pagine delle
  85 sezioni SAT non collegano i loro siti. Per il pilota ho usato le locandine 2020-2023 (sezioni
  di Borgo Valsugana, Mezzolombardo, Trento, Aldeno, Spormaggiore, Rovereto e il trekking del
  150°). **Proposta:** per la Fase 3 trovare i siti delle sezioni più attive uno per uno
  (archiviando ogni sorgente in `config/sources/cai_sections.yaml`), oppure chiedere alla SAT un
  canale (feed o elenco) come già fatto con il CAI.
- **Vipiteno:** nessuna locandina di gite online (4 PDF, tutti amministrativi).
- **Bressanone** ospita anche documenti di altre sezioni (ciaspolata CAI Merano in Val Venegia,
  settimana dell'escursionismo SAT Riva del Garda): la sezione organizzatrice va letta dal testo,
  non dall'URL.
- **PDF dichiarati ma non visibili.** Bressanone dichiara 194 PDF nell'intestazione `X-WP-Total`
  ma l'API ne restituisce 90 (77 + 13 nelle due pagine); la SAT 1134 contro 1122. La paginazione
  è corretta: WordPress conta anche gli allegati di contenuti non pubblici e poi li nasconde agli
  utenti anonimi. Non li cerchiamo per altre vie: non sono pubblicati. La scoperta ora registra
  i due numeri per sezione, così la differenza resta visibile.

## 2. Dati personali

Le locandine contengono nomi e telefoni in molte forme: dopo un'etichetta («Accompagnatori:»,
«Responsabile escursione»), nelle righe di contatto («telefonando a … al n.»), in colonne di tabelle
(«Cognome I.»), in elenchi di istruttori con il titolo (AE, ASC…), in maiuscolo nelle scansioni. La
pulizia a regole è stata corretta cinque volte durante il pilota; oggi i nomi noti dei 51 documenti
non compaiono più nel testo salvato.

- Il testo estratto resta **privato** (`data/`, escluso da git); i campi strutturati non contengono
  mai nomi; nel rapporto le citazioni con segnaposto di dati rimossi non sono mostrate.
- Rischio residuo: un nome in testo libero senza etichetta né telefono vicino può sfuggire.
  **Proposta:** nella coda di revisione (§7.7) un controllo visivo «dati personali» per i documenti
  nuovi di ogni sezione, e un test di regressione per ogni forma nuova trovata.
- Effetto collaterale accettato: qualche frase innocua viene oscurata («gli accompagnatori
  valuteranno…»).

## 3. Estrazione: cosa fa bene il parser e cosa no

- **Bene:** data, difficoltà, durata, distanza, salita, ora, mezzi, quota. 100% di precisione anche
  sulle 8 locandine mai viste.
- **Male:** tipo di percorso (83% sulle non viste), partenza (67%) e soprattutto la **sequenza dei
  punti chiave** (F1 0,43): con i soli campi del parser le ricostruzioni fallite passano da 0 a 6
  su 20. È il lavoro che la revisione deve fare, e nel pilota l'ha fatto Claude Code leggendo i PDF.
- **Attenzione al sovradattamento:** il parser è stato rifinito sulle 20 del pilota. Ogni
  correzione futura in revisione va salvata come caso di test (le annotazioni sono già in YAML),
  così la precisione si misura su un insieme che cresce.
- **Proposta:** nella revisione mostrare per primi i campi a confidenza < 0,8 (un terzo del
  totale) e i punti chiave; i campi ad alta confidenza sono corretti nel 99,5% dei casi.

## 4. Geocodifica

Il gazetteer locale (116 mila luoghi OSM con nome, PostGIS + trigrammi, nomi italiani e tedeschi)
trova il 95% dei punti chiave senza servizi esterni. Regole introdotte durante il pilota, tutte
generali: nome identico prima di nome simile, tipo atteso dalla prima parola («Lago…», «Malga…»,
«Cima…»), parole distintive obbligatorie (niente «Malga Dossioli» per «Malga Zocchi»), quota
verificata sul DEM, raggio massimo dalla lunghezza o dalla durata dichiarata, nomi di sentieri e
strade come punti di passaggio («Edelweisssteig»).

Limiti rimasti e proposte:

| Problema | Esempio | Proposta |
|---|---|---|
| Nomi molto comuni | Moarhof, Wetterkreuz, San Giacomo attorno a Tiso | preferire i candidati vicini ai sentieri citati; in revisione, scelta tra i candidati in mappa |
| Nome solo tedesco in OSM | Laghi del Latte = Milchseen | piccolo dizionario dei termini generici (lago/See, malga/Alm, latte/Milch…) |
| Torrenti e rii | Torrente Aviana | aggiungere al gazetteer i corsi d'acqua con nome (punto più vicino al tratto) |
| Locali minori assenti da OSM | Baita Pauli, Casoni di Valfredda | segnalarli: sono anche contributi possibili a OSM |

## 5. Dati dichiarati nelle locandine

Le locandine contengono errori: dislivello impossibile (Monte Cavone: 670 m dichiarati, almeno
837 m tra partenza e quota massima), data di iscrizione sbagliata (Corno Nero: «16/09» per una gita
del 18/10), quote sbagliate (Lavis «387» e «378», in realtà circa 230 m), refusi («settemre»,
«Referernte», «Cadenave»), distanze arrotondate o ottimistiche (Val di Cembra 14 km, la relazione
OSM della tappa ne misura 12,2).

- **Decisione presa nel pilota:** un dislivello dichiarato incoerente con le quote della stessa
  locandina non si usa per il confronto e l'attività va in revisione con il motivo esplicito.
- **Proposta:** i valori dichiarati non si correggono mai; accanto si mostrano quelli calcolati,
  marcati come tali (come già nelle schede della Fase 1).

## 6. Stato auto_ok: le tolleranze bastano?

Le tolleranze della SPEC (±10% km, ±15% D+, ±50 m) sono un buon filtro ma non una garanzia:

- possono **promuovere una traccia in parte sbagliata**: Castel Coira è auto_ok con −14,7% di
  dislivello (al limite) e solo il 22% della traccia sui sentieri citati;
- possono **bocciare una traccia giusta** quando il dato dichiarato è sbagliato (Monte Cavone,
  Val di Cembra).

Decisioni prese nel pilota, da confermare: (a) dato dichiarato incoerente → escluso dal confronto;
(b) per auto_ok serve almeno un confronto su distanza o dislivello, la sola quota massima non basta;
(c) è tollerato **un** punto intermedio non trovato se i numeri tornano.

**Proposta:** mostrare in revisione la quota della traccia sui sentieri citati come segnale, senza
farne una soglia: le locandine citano spesso solo una parte dei sentieri (Forcella Segura scende per
forcelle non citate ed è giusta al 41%).

## 7. Routing

- La preferenza per i sentieri citati (fuori dall'area costano 4 volte di più) e per gli itinerari
  citati per nome funziona: con il «Cammino delle Terre Sospese» il 93% della traccia è sulla tappa.
- **Andata e ritorno:** la traccia è l'andata ripercorsa all'indietro. Se la discesa ha una
  variante (Lago della Selva, sulla forestale) la distanza esce corta: la variante va aggiunta come
  punto in revisione.
- **Deviazioni «vai e torna»:** un cartello o una località poco fuori dal percorso faceva tornare
  indietro la traccia. Ora il punto si sposta all'innesto, ma solo per cartelli, località e vie con
  nome, mai per la meta più lontana né per rifugi, malghe, cime e laghi. Nella prima versione la
  regola era troppo larga e aveva rovinato quattro anelli: è il tipo di regola da tenere coperta da
  test.
- Percorsi senza numeri («Via Italiana», «Via Austriaca» al Cauriol) richiedono un punto di
  passaggio a mano: è la funzione di modifica della traccia prevista dalla revisione (§7.7).

## 8. Duplicati (anticipo della Fase 3)

Il pilota contiene già casi reali per la deduplica del §7.5: il Waldner See / Lago della Selva
(anello CAI Bolzano da Casere, andata e ritorno CAI Bressanone da Predoi) e la Croda della Calva
(CAI Bolzano 30/08 e libretto CAI Appiano 22/08).

## 9. Calendari e libretti

Le voci del libretto di Appiano si ritagliano bene (data, giorno, titolo, difficoltà,
dislivello/tempi); le righe del calendario SAT di Rovereto hanno solo destinazione, difficoltà,
dislivello e tipologia, e restano «attività leggere» (SPEC §7.1) da collegare alla locandina quando
appare. Si ricostruiscono solo se i nomi del titolo bastano (Lago di Tovel – Malga Flavona: sì).

## 10. Aspetti legali

I PDF non sono mai ripubblicati: archivio privato, link all'originale, sintesi dei campi, citazioni
di poche parole, data. È quanto consente la risposta del CAI (`docs/legal/`). Le tracce sono derivate
da OSM e OSM2CAI (ODbL) e lo dichiarano.

## 11. Non fatto nel pilota (per scelta)

- coda di revisione con PDF e mappa modificabile (§7.7);
- caricamento delle attività nel database e nella PWA;
- deduplica;
- crawler periodici: **nessuno schedulato**, come chiede il §7.6.

## Decisioni che spettano all'utente

1. Estendere l'ingestion alle 5 sezioni del pilota (344 candidati, 5-13 ore di revisione in più
   sessioni) o prima a tutte le sezioni con la sola scoperta dei metadati per misurare il volume?
2. Confermare le tre regole di auto_ok del punto 6, o renderle più severe?
3. SAT: cercare i siti delle sezioni uno per uno, o scrivere alla SAT per un canale dati?
4. Passare alla Fase 3 (Esplora + archivio attività + integrazione SAT + deduplica) usando le 20
   attività del pilota come primo contenuto della sezione attività?
