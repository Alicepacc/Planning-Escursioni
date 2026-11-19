# Servizio delle uscite di gruppo

Cloudflare Worker + D1 ([ADR 0014](../../docs/decisions/0014-backend-uscite-di-gruppo.md)):
uscite create dagli utenti, pagina invito, iscrizione con lista d'attesa, azioni
dell'organizzatore (SPEC §5.4). Accesso con **passkey**; niente email, niente password.
Notifiche **Web Push** senza librerie (cifratura RFC 8291 e firma VAPID RFC 8292 con WebCrypto):
iscrizioni, lista d'attesa, promozioni, annullamenti, rinvii, annunci e il promemoria della sera
prima (cron alle 16:00 UTC). Senza chiave VAPID il servizio funziona lo stesso, senza notifiche.

## In locale (senza account)

```bash
pnpm install
pnpm test          # Vitest nel runtime dei Workers (Miniflare), con D1 e le migrazioni
pnpm run check     # TypeScript
pnpm run db:migrate:local && pnpm run dev   # API su http://localhost:8787
```

## API

| Metodo e percorso | Chi | Cosa fa |
|---|---|---|
| `POST /api/accesso/registrazione/opzioni` · `…/verifica` | chiunque | crea un utente (nome) con una passkey |
| `POST /api/accesso/opzioni` · `…/verifica` | chiunque | accesso con una passkey già registrata |
| `POST /api/accesso/esci` · `GET /api/io` | con sessione | chiude la sessione · chi sono |
| `POST /api/uscite` | con sessione | crea un'uscita; risponde con `id` e il segreto `invito` del link |
| `GET /api/uscite/:id?t=<invito>` | col link, già iscritti, contatti (se «contatti»), tutti (se pubblica) | pagina invito: dati, posti, stato, avvertenza; i nomi solo all'organizzatore |
| `POST /api/uscite/:id/partecipa` `{t}` | con sessione e link | confermato o in lista d'attesa |
| `POST /api/uscite/:id/rinuncia` | iscritti | rinuncia; la lista d'attesa scorre |
| `POST /api/uscite/:id/stato` | organizzatore | `annullata`, `rinviata` (con `rinviata_a`) o `aperta` |
| `POST /api/uscite/:id/partecipanti/:utente` | organizzatore | sposta tra confermati e lista d'attesa |
| `POST /api/uscite/:id/annunci` | organizzatore | bacheca, letta dai partecipanti |
| `GET /api/uscite` | con sessione | le mie uscite |
| `GET /api/uscite/pubbliche` | chiunque | uscite pubbliche dei prossimi 30 giorni con il punto di ritrovo (cache 5 minuti); la distanza la calcola l'app |
| `GET /api/uscite/contatti` | con sessione | uscite future «per i contatti» degli organizzatori con cui si è già usciti |
| `GET /api/notifiche/chiave` | chiunque | chiave pubblica VAPID per `pushManager.subscribe` (404 se le notifiche non sono attive) |
| `POST /api/notifiche` · `POST /api/notifiche/rimuovi` | con sessione | registra o toglie l'iscrizione push del browser |
| `GET /invito/:id?t=<invito>` | chiunque | il link da condividere: pagina HTML con l'anteprima Open Graph (titolo, data, luogo, avvertenza; generica senza link valido) che rimanda alla pagina dell'app. Niente referrer, cache o indicizzazione |

La sessione si passa con `Authorization: Bearer <token>`; nel database ci sono solo gli hash di
sessioni e link d'invito.

## Pubblicazione (account Cloudflare dell'utente)

1. `wrangler d1 create cordata-uscite` e l'id ottenuto in `wrangler.jsonc` (`database_id`).
2. `wrangler d1 migrations apply cordata-uscite --remote`.
3. `node scripts/vapid-key.mjs | pnpm exec wrangler secret put VAPID_PRIVATE_JWK`: la chiave
   privata delle notifiche va direttamente nei segreti di Cloudflare, senza passare da un file.
4. `wrangler deploy`. Il token di pubblicazione e la chiave VAPID stanno solo nei segreti di
   Cloudflare e dell'ambiente, **mai nel repository**.

In locale le notifiche si provano con una chiave usa e getta passata a `wrangler dev` con
`--var "VAPID_PRIVATE_JWK:…"` (i file `.dev.vars` sono esclusi da git); la prova end-to-end è
`apps/web/scripts/e2e-notifiche.cjs`.

La data di compatibilità è 2026-08-15: è la più recente supportata dal runtime dei test.
