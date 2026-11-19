# ADR 0014 – Backend delle uscite di gruppo: Cloudflare Workers + D1, accesso con passkey

- **Stato**: accettata (risposte dell'utente del 19/11/2026)
- **Data**: 19/11/2026

## Contesto

La Fase 5 (SPEC §5.4) richiede un backend:

- creazione dell'uscita;
- pagina invito leggibile senza account;
- iscrizione con lista d'attesa;
- annullamento e rinvio;
- notifiche;
- bacheca dell'organizzatore.

L'[ADR 0005](0005-architettura-a-costo-zero.md) lasciava aperta la scelta tra Supabase Free e
Cloudflare Workers + D1. Limiti verificati il 19/11/2026:

| | Cloudflare Workers + D1 (Free) | Supabase (Free) |
|---|---|---|
| Richieste | 100.000 al giorno, 10 ms di CPU ciascuna | – |
| Dati | D1: 5 GB; 5 milioni di righe lette e 100.000 scritte al giorno; oltre, le query falliscono fino alle 00:00 UTC | Postgres 500 MB; 50.000 utenti attivi al mese |
| Inattività | nessuna pausa | progetto in pausa dopo 7 giorni di poca attività, da ripristinare a mano |
| Accesso e permessi | da scrivere nel nostro codice | Auth, RLS e Realtime pronti |
| Email | nessun invio incluso | invio integrato limitato a 2 email all'ora: serve un SMTP proprio |
| Altro | cron incluso; stessa piattaforma del proxy meteo della Fase 6 | – |

Per le email: Brevo Free invia 300 email al giorno e sembra non richiedere un dominio proprio;
Resend Free invia 100 email al giorno e 3.000 al mese, ma solo con un dominio verificato.

## Decisione

1. **Cloudflare Workers + D1.** Un invito aperto dopo settimane di silenzio deve funzionare: la
   pausa di Supabase lo impedirebbe. Accesso, sessioni e permessi si scrivono nel servizio, con
   test.
2. **Niente email per ora.** L'accesso avviene con le **passkey** (WebAuthn), le notifiche con
   **Web Push** (VAPID). Il magic link via email arriverà più avanti, se servirà. Su iOS le
   notifiche push richiedono la PWA installata: chi non la installa le vede alla visita
   successiva della pagina invito.
3. **Account e chiavi.** Gli account (Cloudflare) li crea l'utente. Le chiavi (token di
   pubblicazione, chiave privata VAPID) stanno nei segreti di Cloudflare e dell'ambiente,
   **mai nel repository**.
4. **Ordine dei lavori.** Si comincia dalle parti che non richiedono account: modello dei dati,
   API, test in locale con Miniflare, pagine dell'app. Le chiavi si chiedono solo al momento
   della pubblicazione.

## Conseguenze

- Il servizio vive in `services/outings` (TypeScript, Wrangler). Lo schema D1 sta in
  `migrations/`.
- La pagina invito si legge senza account con un link che contiene un segreto non indovinabile;
  le azioni (partecipo, rinuncio, azioni dell'organizzatore) richiedono una sessione.
- Senza email non si recupera un account se si perdono tutte le passkey: lo si dice nell'app.
