# ADR 0003 – Regole per le chiamate verso server altrui

- **Stato**: accettata
- **Data**: 13/11/2026

## Decisione

Ogni chiamata dell'ingestion passa da `cordata_ingest.http.PoliteClient`, che applica:

1. **User-Agent identificativo** `Cordata/<versione> (PWA escursioni open data; +<contatto>)`.
   Il contatto arriva dalla variabile d'ambiente `CORDATA_CONTACT` e non è mai nel codice;
   finché non è impostato lo User-Agent dichiara «contatto non ancora configurato».
2. **Cache su disco** con TTL e richieste condizionali (ETag / If-Modified-Since).
3. **Intervallo minimo tra richieste allo stesso host** (default 1 s, configurabile).
4. **Retry con backoff esponenziale** su 429/5xx ed errori di rete, onorando `Retry-After`.
5. **`robots.txt`** secondo RFC 9309: assente (4xx) = consentito; irraggiungibile (5xx o
   errore di rete) = vietato.

## Eccezione: API pubbliche documentate

Alcuni host pubblicano un `robots.txt` che esclude i crawler dai percorsi dell'API ma, nei
termini d'uso, consentono l'accesso programmatico entro limiti dichiarati. In quei casi vale
la policy dell'API e l'adapter disattiva il controllo in modo esplicito
(`respect_robots=False`, con il motivo scritto accanto). Oggi vale solo per:

| Host | `robots.txt` | Policy che seguiamo |
|---|---|---|
| `api.open-meteo.com` | `Disallow: /` | Termini Open-Meteo: 10.000 chiamate/giorno, uso non commerciale |
| `nominatim.openstreetmap.org` | esclude `/search`, `/reverse` | Usage policy OSMF: 1 richiesta/s, User-Agent identificativo |

Dove un catalogo vieta la propria API ai client automatici (CKAN di `dati.trentino.it` e
`data.civis.bz.it`), **non** si usa l'eccezione: la licenza si legge dalla pagina HTML del
dataset e i file si scaricano dall'URL diretto.

## Cosa non si fa

- Non si aggirano controlli d'accesso. L'API `cai-activities/v1` di `organizzazione.cai.it`
  risponde 403 senza header `Origin`: non viene chiamata finché il CAI non la autorizza.
- Non si chiamano Overpass o altri servizi pubblici gratuiti dai client.
- Non si schedula alcun crawler periodico prima dell'approvazione del pilota (§7.6).
