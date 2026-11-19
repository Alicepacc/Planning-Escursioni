# ADR 0005 – Architettura a costo zero

- **Stato**: accettata
- **Data**: 16/11/2026
- **Vincolo** (dall'utente): nessun budget oltre all'abbonamento Claude Pro; tutto deve
  funzionare con servizi gratuiti. Uso oggi non commerciale, in futuro forse a pagamento.

> **Aggiornamento 17/11/2026**: il routing del planner gira nel browser su tasselli statici del
> grafo dei sentieri ([ADR 0010](0010-routing-nel-browser.md)); il Mac e Tailscale Funnel non
> servono più all'app (GraphHopper resta nella pipeline delle attività). La demo è pubblicata su
> GitHub Pages.

## Decisione: un'app «statica prima di tutto»

Tutto ciò che si può calcolare in anticipo viene calcolato dalla pipeline di ingestion e
pubblicato come file statici. I servizi sempre accesi si riducono al routing del planner.

| Componente | Soluzione gratuita | Limiti verificati (16/11/2026) |
|---|---|---|
| Frontend PWA | SvelteKit con prerender, su **Cloudflare Pages** (`cordata.pages.dev`) | Piano Free: 20.000 file per sito, 25 MiB per file, 500 build al mese ([limiti](https://developers.cloudflare.com/pages/platform/limits/)) |
| Dati di sentieri, POI, itinerari | File statici (PMTiles e JSON) prodotti dalla pipeline e pubblicati con il sito | Ogni file sotto i 25 MiB: i PMTiles vanno dimensionati o divisi |
| Mappa di base | **OpenFreeMap**, istanza pubblica | «Completely free: there are no limits on the number of map views or requests», senza chiavi |
| Rilievo e profili | **Mapterhorn**, endpoint pubblico `tiles.mapterhorn.com` | Nessun limite pubblicato; infrastruttura offerta da Cloudflare |
| Routing del planner | **GraphHopper sul Mac di casa**, esposto con **Tailscale Funnel** (`https://<mac>.<tailnet>.ts.net`) | Funnel è «available for all plans»; solo HTTPS su porte 443, 8443 o 10000; banda limitata e non configurabile. Su macOS serve la variante open source dell'app Tailscale, non quella dell'App Store ([doc](https://tailscale.com/kb/1223/funnel)) |
| Proxy e cache meteo (Fase 6) | **Cloudflare Worker** gratuito davanti a Open-Meteo | Workers Free: 100.000 richieste al giorno, 10 ms di CPU per richiesta ([prezzi](https://developers.cloudflare.com/workers/platform/pricing/)). Open-Meteo stesso suggerisce i Workers, perché i suoi limiti si applicano per utente Cloudflare |
| PostGIS | Solo **in fase di build**: nelle sessioni di sviluppo, sul Mac o in GitHub Actions. Non c'è un database pubblico | – |
| Estrazione delle locandine | Parser a regole + revisione in sessione con Claude Code (ADR 0006) | Nessuna API LLM a pagamento |
| Backend delle uscite di gruppo (Fase 5) | **Cloudflare Workers + D1**, accesso con passkey, notifiche Web Push ([ADR 0014](0014-backend-uscite-di-gruppo.md)) | D1 Free: 5 GB, 5 milioni di righe lette e 100.000 scritte al giorno; nessuna pausa per inattività (verificato il 19/11/2026) |

## Conseguenze

- **Il Mac spento non deve rompere l'app.** Esplora, schede, profili, meteo ed export
  funzionano senza il Mac; solo il planner «agganciato ai sentieri» lo richiede. Quando il
  routing non risponde, il planner lo dice chiaramente e permette comunque di tracciare a mano.
- **Il Mac va trattato come un server**: GraphHopper in ascolto solo su `localhost`, Funnel
  espone solo la porta del routing (mai quella di amministrazione), avvio automatico con
  `launchd`, aggiornamento settimanale del grafo. Istruzioni in `services/routing/README.md`.
- **Dimensioni dei dati**: il limite di 25 MiB per file guida la generazione dei PMTiles
  (zoom massimo, semplificazione, eventuale divisione per area).
- **Uso futuro a pagamento**: tutte le licenze dei dati lo consentono (ODbL, CC BY, CC0,
  licenza Copernicus) con attribuzione, e il database derivato resta in ODbL. Fa eccezione
  l'**API gratuita di Open-Meteo, riservata all'uso non commerciale**: in quel caso si passa al
  piano a pagamento o a un'istanza self-hosted. Anche i piani gratuiti dei servizi di hosting
  vanno rivalutati in quel momento.
- **Niente chiavi nel client**: non ce ne sono, perché nessun servizio usato ne richiede.
