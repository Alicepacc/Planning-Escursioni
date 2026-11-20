# Fase 5 – Uscite di gruppo: avanzamento

Data: 19/11/2026. Decisioni: [ADR 0014](../../docs/decisions/0014-backend-uscite-di-gruppo.md)
(Cloudflare Workers + D1, accesso con passkey, niente email per ora).

## Fatto

| Voce della SPEC (§5.4) | Stato |
|---|---|
| Creazione dell'uscita (data, ora e luogo del ritrovo, mezzi, posti, termine iscrizioni, difficoltà, requisiti, attrezzatura come checklist, note, visibilità) | **fatto**: da una scheda («Organizza uscita», titolo e difficoltà precompilati) o da «Uscite» |
| Pagina invito leggera, leggibile senza account | **fatto**: `/uscita?id=…&t=…`; il segreto del link è solo nel link (nel database l'hash) |
| Iscrizione con login leggero | **fatto con passkey** (impronta, volto o PIN), senza email né password |
| Confermato / lista d'attesa / rinuncia | **fatto**: la lista d'attesa scorre in ordine di arrivo quando qualcuno rinuncia |
| L'organizzatore conferma, sposta in attesa, annulla, rinvia | **fatto** |
| Bacheca annunci (solo organizzatore → partecipanti) | **fatto** |
| Condivisione (Web Share o copia del link) | **fatto** |
| Anteprima Open Graph e QR code | **fatto**: il link condiviso passa dal servizio (`/invito/:id?t=…`), che dà alle app di messaggistica titolo, data, luogo e avvertenza, poi rimanda alla pagina; senza link valido l'anteprima è generica. Il QR, disegnato nel browser, apre direttamente la pagina |
| Disclaimer «uscita privata, non organizzata dal CAI» | **fatto**, sulla pagina invito, sul modulo e in «Uscite» |
| Notifiche push e promemoria | **fatto**: «Attiva le notifiche» in «Uscite» e sulla pagina invito; avvisi per iscrizioni, lista d'attesa, promozioni, annullamenti, rinvii e annunci; promemoria della sera prima con un cron. App installabile (manifest e icone): su iPhone le notifiche arrivano solo dalla schermata Home |
| Punto di ritrovo sulla mappa | **fatto**: si tocca la mappa o si usa la propria posizione; da una scheda è proposto alla partenza dell'itinerario |
| Visibilità «contatti» | **fatto**: chi è già uscito con l'organizzatore (anche solo iscritto) vede l'uscita senza link, la trova tra le «Proposte dai tuoi contatti» e riceve una notifica |
| Feed «Uscite pubbliche vicino a te» | **fatto** in «Uscite», anche senza account: uscite pubbliche dei prossimi 30 giorni, «Vicino a me» (10–100 km), «Questo fine settimana». La posizione resta sul telefono: il servizio manda l'elenco, la distanza la calcola l'app. Un'uscita pubblica richiede il punto di ritrovo |

**Servizio** (`services/outings`):

- un Worker TypeScript con D1;
- schema in `migrations/0001_uscite.sql`;
- nel database solo gli hash di sessioni e link d'invito;
- nessuna email o telefono: il nome lo sceglie la persona.

## Prove

- **20 test del servizio** nel runtime dei Workers (Miniflare) con D1 e migrazioni: regole dei
  posti, permessi, link d'invito, lista d'attesa, annullamento e rinvio, bacheca, sessioni;
  cifratura push sul vettore dell'Appendice A della RFC 8291 e decifrata come farebbe il
  browser, firma VAPID verificata, iscrizioni scadute (410) cancellate, promemoria del giorno
  prima in ora italiana; anteprima dell'invito (escape dell'HTML, niente dettagli senza link
  valido, script consentito solo dall'hash nella CSP, uscite annullate); visibilità (feed dei
  prossimi 30 giorni senza annullate né «contatti», lettura e iscrizione senza link per le
  pubbliche, regole dei contatti).
- **Prova end-to-end** (`apps/web/scripts/e2e-uscite.cjs`), senza account: Worker con
  `wrangler dev` e D1 locale, app compilata con `VITE_USCITE_API`, passkey vere su autenticatori
  virtuali di Chromium.
  - Anna crea l'account e organizza l'uscita dalla scheda delle Stellune (2 posti).
  - Bruno apre il link senza account, crea la sua passkey e partecipa.
  - Carla va in lista d'attesa; quando Bruno rinuncia passa tra i confermati.
  - Anna vede i partecipanti e pubblica un annuncio, che Carla legge.
  - «Le mie uscite» elenca l'uscita.
  - Nessun errore in console.
- **Prova del link d'invito** (`apps/web/scripts/e2e-invito.cjs`):
  - il codice QR, decodificato con una libreria indipendente (jsQR), è esattamente il link della
    pagina;
  - il link condiviso, letto come farebbe un'app di messaggistica (senza JavaScript), ha titolo,
    «Lunedì 12 luglio alle ore 07:00 · Palù del Fersina» e l'avvertenza; l'immagine
    dell'anteprima si carica;
  - aperto nel browser, porta alla pagina dell'uscita.
- **Prova della visibilità** (`apps/web/scripts/e2e-visibilita.cjs`):
  - Anna organizza dalla scheda delle Stellune: il punto di ritrovo proposto è la partenza;
    toccando la mappa si sposta. La pubblica per sabato; ne pubblica un'altra tra due
    settimane con «Usa la mia posizione» e una terza solo per i contatti.
  - Bruno, a Feltre e senza account, apre «Uscite»: con «Vicino a me» vede le due pubbliche in
    ordine di distanza (24 e 32 km); con «Questo fine settimana» ne resta una; quella per i
    contatti non c'è.
  - Bruno partecipa a una pubblica creando l'account: da quel momento è un contatto di Anna e
    trova l'uscita per i contatti tra le sue proposte.
  - Nessun errore in console.
- **Prova delle notifiche** (`apps/web/scripts/e2e-notifiche.cjs`) con una chiave VAPID usa e
  getta: Carla organizza e attiva le notifiche, Bruno partecipa, il servizio locale manda una push
  vera attraverso il servizio push di Chrome e il service worker di Carla mostra «Giro del lago di
  Tovel — Bruno partecipa all'uscita.».
  - Chrome non offre il Push API nelle finestre private: la prova usa un profilo persistente e
    l'app lo spiega se l'attivazione non riesce.
  - La consegna passa dai server di Google e può richiedere qualche decina di secondi; la prova
    aspetta fino a un minuto.
  - Il service worker mostra anche i messaggi consegnati direttamente (CDP `deliverPushMessage`),
    con icona e link alla pagina dell'uscita; il manifest e le icone si caricano.

| File | Cosa mostra |
|---|---|
| `screenshots/1-organizza-telefono.jpg` | Il modulo «Organizza un'uscita» precompilato dalla scheda |
| `screenshots/2-invito-telefono.jpg` | La pagina invito vista da chi non ha ancora un account |
| `screenshots/3-organizzatore-telefono.jpg` | La gestione dell'organizzatrice: partecipanti, bacheca, annulla o rinvia |
| `screenshots/4-notifica-telefono.jpg` | La pagina dell'uscita con le notifiche attive («Disattiva le notifiche») |
| `screenshots/5-qr-invito-telefono.jpg` | Il codice QR dell'invito sulla pagina dell'uscita |
| `screenshots/6-punto-di-ritrovo-telefono.jpg` | Il punto di ritrovo sulla mappa nel modulo, proposto dalla partenza dell'itinerario |
| `screenshots/7-uscite-pubbliche-telefono.jpg` | Le uscite pubbliche vicine, filtrate per il fine settimana |

## Pubblicazione (20/11/2026)

- **Servizio**: `https://cordata-uscite.cordata.workers.dev` sull'account Cloudflare
  dell'utente (piano gratuito). Database D1 `cordata-uscite` in Europa occidentale, migrazioni
  applicate, promemoria ogni giorno alle 16:00 UTC.
- **Segreti**: il token di Cloudflare è un segreto di rete dell'ambiente di sviluppo (il proxy lo
  aggiunge solo alle richieste verso `api.cloudflare.com`); la chiave privata VAPID è stata
  generata e passata direttamente a `wrangler secret put`, senza file. Nel repository ci sono
  solo l'id del database e gli indirizzi pubblici.
- **Demo**: `scripts/deploy-gh-pages.sh` compila l'app con l'indirizzo del servizio.
- **Prove sulla demo pubblicata** (le quattro prove end-to-end con
  `CORDATA_URL=https://alicepacc.github.io/Planning-Escursioni`): uscita con lista d'attesa e
  bacheca, QR e anteprima del link, visibilità e feed, notifica push arrivata al browser. Nei log
  del servizio nessun errore. I dati di prova sono stati poi cancellati: il database è vuoto.
- **Corretto durante le prove**: un timer della mappa (chiusura delle attribuzioni dopo 6
  secondi) dava un errore se si lasciava la pagina prima; ora si annulla, e la mappa non si
  crea più se la pagina è già cambiata.
- Le notifiche arrivano attraverso i server push dei browser (Google, Apple, Mozilla): la
  consegna a un browser appena installato può richiedere qualche decina di secondi.

## Aperti

- Il token di Cloudflare ha accesso agli script Workers e a D1 dell'account: se non serve più
  pubblicare da qui, si può revocare dalla dashboard (My Profile → API Tokens) e togliere il
  segreto di rete dall'ambiente.
- Nessun recupero dell'account se si perdono tutte le passkey (scelta «niente email», ADR 0014).
