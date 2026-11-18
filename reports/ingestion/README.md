# Blocchi di ingestion delle attività

Ogni blocco porta in app un gruppo di locandine **con revisione**: candidati scelti a mano,
archivio privato dei PDF (`data/`, mai pubblicato), estrazione del testo senza dati personali,
verità di riferimento rivista (`config/activities/reviewed/`), ricostruzione della traccia e
build. Nessun crawler periodico ([ADR 0012](../../docs/decisions/0012-escursioni-solo-dalle-locandine.md)
per il ruolo delle locandine nell'app).

| Blocco | Data | Fonti | Attività riviste | In app | Tracce verificate |
|---|---|---|---|---|---|
| 1 – SAT Pergine | 17/11/2026 | 8 locandine 2026 | 8 | 8 | 5 |
| 2 – siti WordPress SAT | 18/11/2026 | 13 PDF di Cavalese, Primiero, Ledro | 18 | 15 | 5 |

Il primo blocco è descritto nel [rapporto della Fase 3](../phase3/README.md).

## Blocco 2 – siti WordPress SAT (18/11/2026)

Candidati: [`config/activities/candidates/2026-11-18-sat-wordpress.yaml`](../../config/activities/candidates/2026-11-18-sat-wordpress.yaml)
(Care Alto non pubblica locandine di gite).

### Cosa è entrato

- **18 attività riviste** da 6 documenti: 2 locandine di SAT Cavalese (Cima Nara 2022, Gola di
  Stanghe 2018), 2 di SAT Primiero («Donne e montagna» 2024 e 2025) e i programmi annuali di SAT
  Ledrense (7 gite del 2026 e 7 del 2025).
- **Non usati**, con il motivo: la mappa della Val Martello (solo immagine, nessun testo); la serata
  «Peter Moser in tour» (proiezione, non una gita); la locandina della settimana della montagna di
  Ledro (festa sul territorio; l'uscita del 3 maggio è già nel programma 2026); «2023-24» di
  Primiero (prezzi degli skipass); il quaderno per le scuole di Primiero; i **libretti 2017 e 2018
  di SAT Cavalese** (programmi senza dislivelli né distanze), rimandati a un blocco successivo.
- **Dati personali**: l'estrazione ora toglie anche organigrammi, firme, crediti fotografici e
  cellulari scritti a gruppi di tre cifre (commit a27699a); nei testi restano solo i link
  all'originale.

### Parser a regole

Regole nuove e generali: anno delle date senza anno dalla cartella di caricamento del PDF, date
delle lettere ignorate, notazioni `md+`/`D+`/`disl.`, «N km» e «N ore» da soli su una riga, voci
dei programmi con date brevi (`dd/mm`) e titoli in maiuscolo, «mezzi propri/pubblici», ritorno al
punto di partenza come indizio di anello.

| Insieme | Prima | Dopo |
|---|---|---|
| Blocco 2, precisione dei campi estratti | 68,8% | 88,5% |
| Blocco 2, copertura dei campi presenti | 12,5% | 65,3% |
| Pilota | 98,1% | 98,1% |
| Controllo (holdout) | 92,4% | 92,4% |
| Tutti i blocchi | – | 92,3% (216/234) |

Le regole sono state messe a punto su questo stesso blocco: i suoi numeri sono ottimistici. Pilota
e controllo invariati dicono che non ci sono regressioni; il prossimo blocco darà una misura
indipendente.

### Ricostruzione delle tracce

| Esito | Blocco 2 | Tutte le attività (47) |
|---|---|---|
| verificata (auto_ok) | 5 | 18 |
| da rivedere (tratteggiata, solo valori della locandina) | 10 | 25 |
| fallita (non mostrata) | 3 | 4 |

Verificate: Giro dei 5 laghi, Giro dei laghi del Cevedale, Carega, Giro delle cime (Ledro),
Camminata d'oro a Pietralba.

Correzioni generali della ricostruzione, ciascuna con un test:

1. **Sentieri omonimi.** I numeri si ripetono (SAT, CAI Alto Adige, zone diverse): un «105» a
   20 km attirava il percorso fuori strada. Ora, per ogni numero citato, se alcuni sentieri passano
   entro 2 km dai punti della gita si tengono solo quelli.
2. **Andata e ritorno con il ritorno tra i punti chiave.** Il ritorno veniva contato due volte
   (Monte Vioz: 54 km → 27,6 km). Ora si ricostruisce l'andata e la si ripercorre.
3. **Tracce incompatibili con la locandina.** Se tutto ciò che si può confrontare (distanza,
   dislivello) è oltre il doppio, la linea passa altrove e sulla mappa ingannerebbe: l'esito è
   «fallita» e l'attività non entra in app. Casi: Sentiero dei Fiori (68 km per 15, in parte in
   Lombardia) e **l'anello di Tiso di CAI Appiano del pilota** (47 km e +2270 m per 5 ore e
   +550 m; era già sbagliato e mostrato tratteggiato). CAI Appiano esce quindi dal filtro
   «Sezione».
4. La build toglie le schede non più prodotte.
5. Nomi dei punti chiave allineati alla cartografia nella revisione (Gilfenklamm - Cascata di
   Stanghe, Maria Weissenstein - Madonna di Pietralba, Rifugio Mandrone, Bocca dell'Ussol, Dosso
   della Torta, Malga Vies, Le Vale, Prè di Ledro, Bocca dei Fortini), annotati in `note_revisione`.

Da rivedere, con il motivo: Monte Vioz (gli 11 km della locandina sono probabilmente la sola
andata; dislivello giusto), Monte Altissimo giovanile (+18% di distanza), Da Riva al Rifugio Pernici
(+19%), Cima Nara (+55% di dislivello), Ferrata Bolver Lugli (+44%), Pasta/Spiedo dal Franco
(+47%; Cadrione, Baita Segala e Passo Vil non sono nella cartografia), Gola di Stanghe (gola breve,
dislivello sottostimato dal modello del terreno), le due «Donne e montagna» (nessun numero nella
locandina con cui confrontare).

**Deduplica**: «Spiedo dal Franco» (2025) e «Pasta dal Franco» (2026) sono lo stesso giro e
diventano un solo itinerario con due proposte della sezione (screenshot 2).

### In app

- **42 escursioni** in Esplora (erano 29), da 14 voci del filtro «Sezione»; nuove SAT Ledrense,
  SAT Cavalese e SAT Primiero.
- Corretta l'etichetta del link «Locandina originale (pagina N)», a cui mancava lo spazio.
- Verificato nel browser (Pixel 7): elenco, filtro, schede del blocco, nessun errore in console.

| File | Cosa mostra |
|---|---|
| `screenshots/1-giro-dei-5-laghi-telefono.jpg` | Giro dei 5 laghi (SAT Ledrense): traccia verificata, punti numerati, sintesi |
| `screenshots/2-stesso-giro-due-anni-telefono.jpg` | Pasta dal Franco: traccia da rivedere, solo valori della locandina, stesso itinerario proposto nel 2025 e nel 2026 |

### Problemi aperti

- **Confine con la Lombardia**: l'estratto OpenStreetMap copre Trentino-Alto Adige e Veneto. Le
  gite di Ledro verso il Passo Nota (Spiedo in Nota 2025 e 2026) e l'Adamello lombardo (Sentiero
  dei Fiori) non si ricostruiscono. Si può allargare l'estratto con una fascia di confine.
- **Attività con ricostruzione fallita**: oggi non compaiono. Si potrebbero mostrare con la sola
  partenza e i dati della locandina, senza linea (4 attività oggi).
- **Le tracce da rivedere** (25) non hanno ancora uno strumento di revisione: restano tratteggiate,
  con l'avviso e i soli valori della locandina.
