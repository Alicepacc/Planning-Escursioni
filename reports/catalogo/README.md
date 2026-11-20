# Catalogo Trentino-Alto Adige e Dolomiti: avanzamento

Data: 20/11/2026. Decisioni: [ADR 0015](../../docs/decisions/0015-catalogo-dolomiti-affidabilita-e-ui.md).
Rapporto intermedio: lo scarico e l'estrazione del testo sono ancora in corso.

## Cosa si pubblica

- **Area**: tutto il Trentino-Alto Adige più Dolomiti e Prealpi venete, decisa dalla traccia
  (almeno metà dentro), non dalla sede della sezione. Mappa: `area-del-catalogo.jpg`.
- **Affidabilità da 80 su 100**: vale per tutte le escursioni, anche per quelle rivedute a mano
  nelle fasi precedenti. Le escursioni senza traccia non si pubblicano.
- Per questo l'app è passata da 89 a **58 escursioni**: sono uscite quelle fuori area e quelle
  con la traccia meno sicura; entrano le prime 15 del catalogo a lotti (alcune coincidono con
  itinerari già presenti e si fondono con la deduplica).

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

## Aperti

- Scarico ed estrazione in corso; il catalogo si aggiorna a ogni passo.
- Programmi e libretti annuali (molte gite per documento): da trattare con le voci di
  calendario del parser.
- Partenza riconosciuta bene solo in metà dei casi: è la leva principale per pubblicare di più.
- Verifica dell'app sul simulatore iPhone del Mac dell'utente, quando una cartella del Mac sarà
  disponibile alla sessione.
