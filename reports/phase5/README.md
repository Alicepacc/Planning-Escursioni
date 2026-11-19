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
| Condivisione (Web Share o copia del link) | **fatto**; QR code e anteprima Open Graph da fare |
| Disclaimer «uscita privata, non organizzata dal CAI» | **fatto**, sulla pagina invito, sul modulo e in «Uscite» |
| Notifiche push e promemoria | da fare: le API restituiscono già chi va avvisato |
| Visibilità «contatti» e feed delle uscite pubbliche vicine | da fare |

**Servizio** (`services/outings`):

- un Worker TypeScript con D1;
- schema in `migrations/0001_uscite.sql`;
- nel database solo gli hash di sessioni e link d'invito;
- nessuna email o telefono: il nome lo sceglie la persona.

## Prove

- **9 test del servizio** nel runtime dei Workers (Miniflare) con D1 e migrazioni: regole dei
  posti, permessi, link d'invito, lista d'attesa, annullamento e rinvio, bacheca, sessioni.
- **Prova end-to-end** (`apps/web/scripts/e2e-uscite.cjs`), senza account: Worker con
  `wrangler dev` e D1 locale, app compilata con `VITE_USCITE_API`, passkey vere su autenticatori
  virtuali di Chromium.
  - Anna crea l'account e organizza l'uscita dalla scheda delle Stellune (2 posti).
  - Bruno apre il link senza account, crea la sua passkey e partecipa.
  - Carla va in lista d'attesa; quando Bruno rinuncia passa tra i confermati.
  - Anna vede i partecipanti e pubblica un annuncio, che Carla legge.
  - «Le mie uscite» elenca l'uscita.
  - Nessun errore in console.

| File | Cosa mostra |
|---|---|
| `screenshots/1-organizza-telefono.jpg` | Il modulo «Organizza un'uscita» precompilato dalla scheda |
| `screenshots/2-invito-telefono.jpg` | La pagina invito vista da chi non ha ancora un account |
| `screenshots/3-organizzatore-telefono.jpg` | La gestione dell'organizzatrice: partecipanti, bacheca, annulla o rinvia |

## Per pubblicare il servizio (serve l'account Cloudflare dell'utente)

Passi in [`services/outings/README.md`](../../services/outings/README.md): creare il database D1,
applicare le migrazioni, pubblicare il Worker, poi compilare l'app con `VITE_USCITE_API`. Finché
non è pubblicato, la demo mostra le pagine delle uscite con l'avviso «servizio non ancora
attivo».

## Prossimi passi della fase

1. Notifiche Web Push (VAPID): iscrizione del browser, avviso a chi va in lista d'attesa,
   promozioni, annullamenti, rinvii e annunci; promemoria del giorno prima con un cron.
2. Anteprima Open Graph e QR code della pagina invito.
3. Visibilità «contatti» e feed delle uscite pubbliche vicine.
4. Pubblicazione del servizio, con le chiavi nei segreti di Cloudflare.
