# Servizio delle uscite di gruppo

Cloudflare Worker + D1 ([ADR 0014](../../docs/decisions/0014-backend-uscite-di-gruppo.md)):
uscite create dagli utenti, pagina invito, iscrizione con lista d'attesa, azioni
dell'organizzatore (SPEC §5.4). Accesso con **passkey**; niente email, niente password. Le
notifiche Web Push arriveranno in un passo successivo: le API restituiscono già chi va avvisato.

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
| `GET /api/uscite/:id?t=<invito>` | col link (o già iscritti) | pagina invito: dati, posti, stato, avvertenza; i nomi solo all'organizzatore |
| `POST /api/uscite/:id/partecipa` `{t}` | con sessione e link | confermato o in lista d'attesa |
| `POST /api/uscite/:id/rinuncia` | iscritti | rinuncia; la lista d'attesa scorre |
| `POST /api/uscite/:id/stato` | organizzatore | `annullata`, `rinviata` (con `rinviata_a`) o `aperta` |
| `POST /api/uscite/:id/partecipanti/:utente` | organizzatore | sposta tra confermati e lista d'attesa |
| `POST /api/uscite/:id/annunci` | organizzatore | bacheca, letta dai partecipanti |
| `GET /api/uscite` | con sessione | le mie uscite |

La sessione si passa con `Authorization: Bearer <token>`; nel database ci sono solo gli hash di
sessioni e link d'invito.

## Pubblicazione (account Cloudflare dell'utente)

1. `wrangler d1 create cordata-uscite` e l'id ottenuto in `wrangler.jsonc` (`database_id`).
2. `wrangler d1 migrations apply cordata-uscite --remote`.
3. `wrangler deploy`. Le chiavi (token di pubblicazione, più avanti la chiave VAPID) stanno nei
   segreti di Cloudflare e dell'ambiente, **mai nel repository**.

La data di compatibilità è 2026-08-15: è la più recente supportata dal runtime dei test.
