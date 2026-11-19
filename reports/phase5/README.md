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
| Visibilità «contatti» e feed delle uscite pubbliche vicine | da fare |

**Servizio** (`services/outings`):

- un Worker TypeScript con D1;
- schema in `migrations/0001_uscite.sql`;
- nel database solo gli hash di sessioni e link d'invito;
- nessuna email o telefono: il nome lo sceglie la persona.

## Prove

- **17 test del servizio** nel runtime dei Workers (Miniflare) con D1 e migrazioni: regole dei
  posti, permessi, link d'invito, lista d'attesa, annullamento e rinvio, bacheca, sessioni;
  cifratura push sul vettore dell'Appendice A della RFC 8291 e decifrata come farebbe il
  browser, firma VAPID verificata, iscrizioni scadute (410) cancellate, promemoria del giorno
  prima in ora italiana; anteprima dell'invito (escape dell'HTML, niente dettagli senza link
  valido, script consentito solo dall'hash nella CSP, uscite annullate).
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

## Per pubblicare il servizio (serve l'account Cloudflare dell'utente)

Passi in [`services/outings/README.md`](../../services/outings/README.md): creare il database D1,
applicare le migrazioni, pubblicare il Worker, poi compilare l'app con `VITE_USCITE_API`. Finché
non è pubblicato, la demo mostra le pagine delle uscite con l'avviso «servizio non ancora
attivo».

## Prossimi passi della fase

1. Visibilità «contatti» e feed delle uscite pubbliche vicine.
2. Pubblicazione del servizio, con le chiavi nei segreti di Cloudflare.
