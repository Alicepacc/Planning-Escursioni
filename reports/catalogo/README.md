# Catalogo Trentino-Alto Adige e Dolomiti: avanzamento

Data: 20/11/2026. Decisioni: [ADR 0015](../../docs/decisions/0015-catalogo-dolomiti-affidabilita-e-ui.md).
Scarico, estrazione del testo ed elaborazione del catalogo conclusi per tutti i documenti.

## Cosa si pubblica

- **Area**: tutto il Trentino-Alto Adige più Dolomiti e Prealpi venete, decisa dalla traccia
  (almeno metà dentro), non dalla sede della sezione. Mappa: `area-del-catalogo.jpg`.
- **Affidabilità da 80 su 100**: vale per tutte le escursioni, anche per quelle rivedute a mano
  nelle fasi precedenti. Le escursioni senza traccia non si pubblicano.
- Per questo l'app era scesa da 89 a 58 escursioni (fuori quelle fuori area e quelle con la
  traccia meno sicura); con il catalogo a lotti è risalita a **82** (aggiornamento più sotto).

## Il punteggio

| Parte | Peso | Cosa misura |
|---|---|---|
| Traccia | 65% | Distanza, salita e quota massima della traccia ricostruita contro la locandina: pieno dentro le tolleranze della verifica (±10%, ±15%, ±50 m), zero oltre ±35%, ±45%, ±250 m; quota della traccia sui sentieri citati. Con un solo confronto la parte vale al massimo 0,6 (sotto soglia: un numero solo può coincidere per caso), con due 0,9 |
| Punti | 20% | Punti della locandina trovati sulla carta e, dove la locandina dà la quota, quota del luogo trovato entro 80 m |
| Lettura | 15% | Sicurezza del parser sui campi utili; 1 per i campi rivisti a mano |

**Taratura** sulle 90 attività già rivedute: per ciascuna la traccia ricostruita dal *solo
parser* è stata confrontata con quella dai campi rivisti a mano e verificata (giusta se almeno
l'80% coincide entro 300 m).

| Soglia | Pubblicate | Con una verità di confronto | Giuste |
|---|---|---|---|
| 70 | 22 | 12 | 10 (83%) |
| **80** | **15** | **10** | **9 (90%)** |
| 90 | 8 | 4 | 4 (100%) |

## La catena per ogni locandina

1. **Scoperta**: 8.815 documenti sui siti di 39 sezioni; 3.948 sembrano escursioni, programmi o
   ciaspolate (2012–2026).
2. **Prefiltro sul titolo** (nomi OSM di cime, rifugi, passi, laghi, valli e località
   dell'area; mete lontane come Sardegna, Appennini, Colli Euganei, Friuli): 1.503 dentro,
   2.283 incerti (si scaricano comunque), 162 fuori.
3. **Scarico cortese**: un documento ogni 3 secondi per sito, alternando i siti; finora 2.665
   (171 non più disponibili sui siti, per lo più 404).
4. **Testo**: estrazione con OCR per le locandine scansionate (solo le prime 12 pagine); i dati
   personali si tolgono come prima.
5. **Campi** con il parser a regole e **punti del percorso dal testo** quando il parser ne trova
   meno di tre (nomi con la parola di tipo, «partendo da», arrivo con un mezzo, tappe nel
   titolo; esclusi i panorami e i luoghi del viaggio). Misura sui punti rivisti a mano:
   richiamo 65%, precisione 69%, partenza giusta 20 su 46.
6. **Tipo di attività**: esclusi cicloescursionismo (scale MC/BC/OC), alpinismo (F/PD/AD…),
   corsi e serate, documenti senza dati di percorso; i **programmi** annuali restano per un
   passo successivo.
7. **Ricostruzione** della traccia, **area**, **punteggio**.

## Primo lotto elaborato (362 documenti)

| Esito | Documenti |
|---|---|
| Pubblicabili (da 80) | 15 |
| Sotto soglia | 213 |
| Esclusi (bici, corsi, programmi, nessun dato di percorso) | 121 |
| Fuori area | 13 |

Molte locandine dei primi anni sono **scansioni**: dal testo dell'OCR il parser trova pochi
numeri e pochi luoghi, e la ricostruzione fallisce. È il limite principale: il catalogo
pubblica solo quello che torna, quindi cresce meno di quanto si scarica.

## Controllo a campione

`campione-lotto-1.png`: le 6 pubblicabili del primo passo su piccole mappe. Cinque sono
chiaramente giuste (Ciaspolata in Val Venegia, Monte Brugnol, Seceda da Santa Cristina, Monte
Pic, Malga e Lago Bocche); una, «Malghe di Proves» (80 esatto), è plausibile ma irregolare,
con andate e ritorni per toccare le malghe. In linea con il 90% della taratura.

## Secondo passo (20/11/2026, pomeriggio)

Dove si perdevano le escursioni: in 94 delle 121 ricostruzioni fallite i punti della locandina
non si trovavano sulla carta. Il primo punto estratto era spesso una parola generica
(«Parcheggio», «Locanda», «Pian») che il gazetteer trova ovunque; tutti i punti successivi,
cercati vicino a quello, sparivano.

- **Zona del percorso**: ogni nome si cerca in tutta l'area e si sceglie la zona (12 km) dove
  cade il maggior numero di nomi diversi; si tengono solo quei nomi, nell'ordine della
  locandina, e la partenza si cerca lì. Sulle 90 di taratura le fallite scendono da 50 a 44 con
  la stessa precisione (90% alla soglia 80); sul catalogo le pubblicabili passano da 15 a 22 a
  parità di documenti.
- **Titoli**: quando la locandina dà come titolo una riga del regolamento («Per i non tesserati
  CAI, l'iscrizione…», «Quota di partecipazione:») o un campo («Dislivello positivo: 850 m»), il
  titolo viene dal nome del documento sul sito della sezione ripulito («Ferrata Strobel»), o
  dalla meta più alta e dalla partenza della traccia («Rifugio Nuvolau da Passo Giau»); i titoli
  tutti maiuscoli si normalizzano.
- **Ritrovo in paese**: il primo punto che porta il nome della sezione («Puos d'Alpago» per il
  CAI Alpago) è il ritrovo, non la partenza.

| Documenti elaborati | Pubblicabili | Sotto soglia | Esclusi | Fuori area |
|---|---|---|---|---|
| 740 | 46 (6,2%) | 461 | 212 | 21 |

Controllo a campione (`campione-lotto-2.png`, 12 a caso tra le 46): tracce tutte plausibili;
una sola resta dubbia («Escursione notturna: Rifugio Bristot al Nevegal», la traccia passa per
il versante dell'Alpago). Nell'app: **82 escursioni** da 80 in su (5 doppioni fusi).

## Terzo passo (20/11/2026, sera)

- **Scarico finito**: 3.814 documenti cercati, 3.513 scaricati (301 non più disponibili, per lo
  più 404, o esclusi dal robots.txt). **Testo** estratto per tutti: l'OCR ora gira con un
  processo per core e un filo per processo, prima le locandine con una meta dell'area nel titolo.
- **Dati personali**: sotto «ACCOMPAGNATORI» da solo su una riga, i nomi separati da virgole
  («Nome Cognome, Nome Cognome.», locandine CAI Asiago e altre) restavano nel testo estratto,
  e i blocchi di impaginazione, puliti uno per uno, non sapevano di essere sotto l'etichetta.
  Ora si tolgono; i testi già estratti sono stati ripassati (334 cambiati) e il catalogo è stato
  rifatto da capo sui testi puliti. Nessuno dei nomi tolti era nei file del repository o nei
  dati pubblicati dell'app (controllo su tutti i file tracciati).
- **Elenco delle tappe**: molte locandine danno il percorso come «Itinerario: Casotto,
  Belfiore, Luserna, Longhi, Casotto.». Quando è davvero un elenco di luoghi (non indicazioni
  stradali né prosa) dà i punti nell'ordine della locandina, senza i numeri dei sentieri, con la
  quota tra parentesi; se torna alla partenza è un anello. Sulle 72 locandine con un elenco: 11
  in più da 80 in su, una in meno (Monte Conca: con tutti gli otto punti la traccia viene il 40%
  più lunga del dichiarato, e il punteggio la tiene fuori).
- **Distanze** «km tot.: 11,1 Km», «Km totali: 13 km», «Km e dislivello: 11 km, +1300 m»
  (schede CAI Belluno): senza distanza restava un solo confronto e il punteggio non arrivava a 80.

- **Titoli**: una frase della descrizione («Riamo fino a Paneveggio; facendo così…») o il nome
  di un gruppo («Gruppo Escursionismo») non fanno più da titolo. Il nome del documento sul sito,
  usato in mancanza di un titolo, tiene solo le parole che il testo pulito della locandina
  ripete: alcuni nomi di file portano i cognomi degli accompagnatori («Escursionismo
  Cognome-Cognome Rifugio X»), che così non arrivano all'app.

Esiti sul lotto completo (tutti i documenti con il testo, rielaborati da capo):

| | Documenti | Voci dei programmi |
|---|---|---|
| Pubblicabili (da 80) | **164** | **36** |
| Sotto soglia | 1.751 | 591 |
| Esclusi (bici, alpinismo, corsi, nessun dato di percorso) | 1.134 | 788 |
| Programmi e libretti (divisi in voci) | 298 | – |
| Fuori area | 101 | 18 |
| **Totale** | **3.448** | **1.433** |

Nell'app: **228** escursioni da 80 in su (185 dal catalogo, le altre rivedute a mano), con
i doppioni dello stesso percorso fusi in gruppi.

Controllo a campione (`campione-lotto-3.jpg`, 12 a caso tra le nuove): dieci tracce plausibili;
due dubbie, «Anello di Sanzeno e Santuario di San Romedio» (la traccia non passa chiaramente dal
santuario) e la traversata verso il rifugio Marinelli (CAI Mestre: la traccia non arriva al
rifugio, in Carnia). Dieci su dodici è un po' sotto le 9 su 10 della taratura: le voci dei
programmi e le locandine con pochi numeri sono le più fragili, e sono le prime da guardare.

## Aperti

- Programmi e libretti annuali (molte gite per documento): da trattare con le voci di
  calendario del parser.
- Partenza riconosciuta bene solo in metà dei casi: è la leva principale per pubblicare di più.
- Verifica dell'app sul simulatore iPhone del Mac dell'utente, quando una cartella del Mac sarà
  disponibile alla sessione.
