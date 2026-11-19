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
| 3 – sezioni CAI Alto Adige | 19/11/2026 | 20 locandine di Brunico e Bressanone | 15 | 12 | 5 |

Il primo blocco è descritto nel [rapporto della Fase 3](../phase3/README.md).

## Blocco 3 – sezioni CAI Alto Adige (19/11/2026)

Candidati: [`config/activities/candidates/2026-11-18-cai-alto-adige.yaml`](../../config/activities/candidates/2026-11-18-cai-alto-adige.yaml).

### Cosa è entrato

- **CAI Brunico** è stata aggiunta all'indice delle fonti (metadati di 122 PDF; nuova opzione
  `discover --sezioni brunico`, che aggiorna solo quella sezione). Scelte le 10 locandine singole
  di agosto-ottobre 2026; per **CAI Bressanone** le 10 locandine 2026 non usate nel pilota.
  Vipiteno pubblica solo moduli e una falesia; il programma 2025 di Appiano resta per un blocco
  successivo.
- **15 attività riviste.** Escluse con il motivo: Törggelen e gita di chiusura di Brunico (pranzi
  sociali), la salita alpinistica alla Torre Diamantidi (via PD, fuori dall'escursionismo),
  Zinsnock e Cima di Pozzo di Bressanone (scialpinismo).
- Le date e i tempi che l'OCR delle locandine di Brunico aveva perso sono stati letti
  sull'immagine della pagina (annotato in `note_revisione`).

### Dati personali

Il controllo dei testi ha trovato tre casi, corretti con test e con la nuova estrazione di tutto
l'archivio:

- nomi dopo «istruttore» e nome proprio a fine riga col cognome a capo («presso il Presidente della
  sezione Nome⏎Cognome»);
- telefoni fissi scritti «0xxx/xxxxxx» o «0xxx / xxxxxx» su righe senza la parola «tel» ma con il
  sito o l'email della sezione;
- al contrario, parole della scheda tecnica («Difficoltà: EEA (Escursionisti Esperti…)») tolte come
  se fossero nomi quando l'OCR a due colonne le metteva sulla riga di un'email.

### Parser a regole: la misura indipendente

Il parser è stato misurato su queste locandine **prima** di ogni ritocco: è la misura onesta delle
regole scritte nei blocchi precedenti.

| Insieme | Prima (indipendente) | Dopo |
|---|---|---|
| Blocco 3, precisione | **75,5%** | 80,6% |
| Blocco 3, copertura | **54,3%** | 64,8% |
| Pilota | 98,1% | 98,1% |
| Controllo (holdout) | 92,4% | 92,4% |
| Blocchi 1 e 2 | 92,3% | 92,3% (un campo corretto in più) |

Il 75,5% contro l'88,5% «ottimistico» del blocco 2 conferma che i numeri misurati sulle stesse
locandine usate per scrivere le regole sono gonfiati. Regole nuove: tempi dopo l'etichetta su più
righe (totale «4 ore e 15 minuti complessivi» o somma di salita, piano e discesa, anche «1 ora
(salita), 45 minuti (ritorno)»), «N m in salita/in discesa», «distanza totale: km N», «13 km
distanza», «punto più alto» con la quota a capo, quota massima senza le mete facoltative e le cime
viste da lontano, rimborsi e quote di viaggio, «Dal Passo X (quota)». Restano difficili i titoli e
le date delle locandine solo grafiche (OCR).

### Ricostruzione delle tracce

| Esito | Blocco 3 | Tutte le attività (62) |
|---|---|---|
| verificata (auto_ok) | 5 | 23 |
| da rivedere | 7 | 32 |
| fallita (non mostrata) | 3 | 7 |

Verificate: Ferrata Piz da Peres, Valle Aurina – Rifugio Giogo Lungo, traversata Sarè – Pederü,
Chiusa – Albions – Gudon, Corno di Tres. Fallite: Ferrata di Preore (la locandina non nomina punti
oltre al paese), Piccolo Tibet (in Austria, fuori dall'estratto), Monte Tullo (partenza non
indicata). Da rivedere: Santa Croce di Lazfons (i 6,5 km sono la sola andata), Ferrata Susatti a
Cima Capi, Bec de Roces, Rifugio Torre di Pisa, Giro del Castello di Monguelfo, e le due uscite
dell'alpinismo giovanile senza dati tecnici.

Correzioni generali:

- **Raggio di ricerca dei punti chiave**: il maggiore tra la stima dalla distanza e quella dalla
  durata (3,5 km/h), perché la distanza dichiarata è spesso la sola andata. Nessun cambiamento
  sulle altre 47 attività.
- **Comuni omonimi**: «Funes» e «Magrè» portavano la ricerca della partenza in Veneto e in
  Trentino; corretti nella revisione (Cortaccia sulla Strada del Vino; nessun comune per Funes).
- **Indirizzi delle schede** con dieresi e accenti: «Pederü» → `pederu`, «Günther» → `gunther`
  (prima `g-nther`). Cambia l'indirizzo della scheda Odle di Eores di SAT Pergine.
- Nomi dei punti chiave allineati alla cartografia bilingue (Klausner Hütte, Latzfonser Kreuz,
  Castel Thurn, Castel Welsperg, Röt Alm, Malga Zannes, Malga Casnago, Fennberg - Favogna).

### In app

**54 escursioni** (erano 42); «CAI Brunico» compare nel filtro «Sezione». Verificato nel browser
(Pixel 7): elenco, filtro, schede del blocco, nessun errore.

| File | Cosa mostra |
|---|---|
| `screenshots/3-sare-pederu-telefono.jpg` | Traversata Sarè – Pederü (CAI Brunico, gita con l'AVS): traccia verificata, 7 punti chiave |

### Problemi aperti

- **Comuni omonimi**: l'àncora del comune cerca in tutta l'area; andrebbe limitata alla provincia
  della sezione.
- **Locandine solo grafiche**: titoli e date persi dall'OCR vanno letti a mano.
- **Escursioni fuori area** (Austria, Lombardia): restano fuori finché l'estratto OSM copre solo
  Trentino-Alto Adige e Veneto.

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

## Decisioni dell'utente (19/11/2026)

Registrate nell'[ADR 0013](../../docs/decisions/0013-fonti-veneto-confini-e-attivita-senza-traccia.md):

- elenco delle sezioni venete dalla directory del CAI (una richiesta in lettura): autorizzato;
- estratto OSM allargato con una **fascia di confine**;
- attività con ricostruzione fallita **mostrate senza linea**;
- i blocchi proseguono in automatico, con una sosta prima della Fase 5.

## Dopo le decisioni del 19/11/2026

### Fonti CAI Veneto (solo metadati)

- **La directory delle sezioni non si usa.** L'endpoint autorizzato risponde «Origin header
  mancante» (403): accetta solo le richieste della propria pagina. Falsificare l'intestazione
  vorrebbe dire aggirare una protezione, quindi non si fa.
- **Al suo posto, `cai-veneto-siti`.** I siti sono stati cercati su indirizzi plausibili per 62
  nomi di sezione compilati a mano (`organizzazione.cai.it/sez-<nome>` e `www.cai<nome>.it`):
  124 indirizzi, robots.txt e una sola richiesta alla home ciascuno.
- **39 sezioni venete registrate** in `config/sources/cai_sections.yaml`:
  - 28 WordPress con l'API dei media (23 con un sito proprio, 5 sul multisite del CAI);
  - 5 WordPress con l'API dei media spenta (Calalzo, Pieve di Cadore, San Vito di Cadore, Pieve
    di Soligo, Arzignano);
  - 6 con altri CMS (Agordo, Domegge, Oderzo, Schio, Valdagno, Padova): serviranno adapter come
    per i 12 siti SAT;
  - CAI Marostica esclusa: robots.txt risponde «accesso sospeso».
- **Metadati di 7.251 PDF** delle 28 sezioni con l'API (nessun download). Dal solo nome,
  941 sembrano locandine di gite dal giugno 2025, più 133 programmi. Le sezioni con più
  locandine sono Vicenza (389), Treviso (87), Verona (63), Rovigo (57), Feltre (53) e
  Montecchio Maggiore (52).

### Fascia di confine

L'estratto ora comprende, nella stessa bbox dell'area pilota, le province di **Sondrio, Brescia,
Udine e Pordenone** (Estratti OSM Italia, 135 MB). **Austria e Svizzera restano fuori**, perché
Geofabrik chiude la connessione da questo ambiente ([ADR 0004](../../docs/decisions/0004-estratto-osm.md)).

| | Prima | Dopo |
|---|---|---|
| Sentieri (OSM e catasto) | 7.109 | 8.028 |
| Luoghi con nome (geocodifica) | 116.126 | 127.593 |
| Tasselli PMTiles della mappa | 19,7 MB | 22,2 MB |
| Grafo del planner | 562 tasselli, 66 MB | 633 tasselli, 74 MB |

Effetto sulle 62 attività, ricostruite di nuovo:

| Esito | Prima | Dopo |
|---|---|---|
| verificata | 23 | 27 |
| da rivedere | 32 | 31 |
| fallita | 7 | 4 |

Nel dettaglio:

- **Spiedo in Nota** (2025 e 2026) passa da fallita a verificata, e le due uscite diventano un
  solo itinerario.
- Diventano verificate anche **Cima Nara** e **Val di Cembra, tappa 1**.
- **Sentiero dei Fiori** passa da 68 a 14,3 km (15 dichiarati). Resta da rivedere per il
  dislivello: i 500 m della locandina contano le funivie.
- Peggiora **Pasta/Spiedo dal Franco** (10,2 → 15,2 km). Era già da rivedere: tra Bocca dei
  Fortini, sul confine, e Leano il percorso ora passa per sentieri lombardi.

### Attività senza traccia

Restano 4 attività senza traccia. Sono visibili in app con i dati della locandina, l'avviso
«Percorso non disponibile sulla mappa» e l'etichetta «senza traccia» in Esplora; non hanno
profilo né esportazioni.

| Attività | Punto sulla mappa |
|---|---|
| Anello da Tiso di CAI Appiano | sì |
| Ferrata di Preore | sì |
| Piccolo Tibet | no: segnata `fuori_area`, i nomi trovati in Italia erano omonimi |
| Monte Tullo | no: partenza non indicata |

Un punto isolato va sulla mappa solo se la locandina indica la partenza e la gita non è fuori
area: senza un secondo punto che lo confermi potrebbe essere un omonimo lontano.

**In app: 60 escursioni visibili** (61 schede, 2 itinerari con più proposte). Verificato nel
browser: elenco, schede con e senza traccia, nessun errore.

| File | Cosa mostra |
|---|---|
| `screenshots/4-senza-traccia-telefono.jpg` | Una scheda senza traccia, prima della fascia di confine |
| `screenshots/5-spiedo-in-nota-telefono.jpg` | Spiedo in Nota con la traccia ricostruita in Lombardia e le due proposte della sezione |

### Prossimi passi

1. **Blocco 4**: locandine venete, a partire dalle sezioni dolomitiche e da quelle con più gite
   in montagna (Belluno, Feltre, Alpago, Vicenza, Treviso), con revisione.
2. Adapter per i siti SAT non WordPress e per i 6 siti veneti con altri CMS.
3. Poi la Fase 5, con una sosta per scegliere il backend.
