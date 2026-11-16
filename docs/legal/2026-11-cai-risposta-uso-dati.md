# Risposta del CAI sull'uso dei dati (testo integrale)

- **Ricevuta da**: Club Alpino Italiano (la struttura mittente non compare nel testo incollato)
- **Data dell'email originale**: non indicata nel testo incollato; registrata nel repository il
  16/11/2026
- **Destinataria**: la promotrice del progetto (nome omesso)
- **Da completare**: data, mittente e oggetto dell'email originale

## Testo

> Gentile [nome omesso],
>
> grazie per averci contattato e per l'attenzione dedicata alla corretta diffusione delle
> informazioni della rete escursionistica dolomitica.
>
> Con riferimento ai quesiti da Lei posti, Le forniamo di seguito le indicazioni aggiornate
> relative al catasto della Rete Escursionistica Italiana (REI), agli strumenti tecnici, alle
> modalità di accesso e di riutilizzo dei dati:
>
> **1. Informazioni sulla percorribilità, manutenzione e accesso ai dati (OSM2CAI, API e
> documentazione)**
>
> Il catasto della Rete Escursionistica Italiana (REI) cataloga i tracciati, le relative
> caratteristiche tecniche e le Sezioni CAI (o gli enti territoriali) competenti per la
> manutenzione.
>
> Piattaforma OSM2CAI, API e documentazione ufficiale: I dati sono consultabili tramite la
> piattaforma OSM2CAI. Per l'integrazione in applicazioni esterne, il progetto mette a
> disposizione delle API REST pubbliche (in formato GeoJSON/JSON). Tutta la documentazione
> tecnica di riferimento, comprensiva di guide operative e specifiche d'uso, è ufficialmente
> consultabile sul portale dedicato: https://catastorei.gitbook.io/documentazione-osm2cai.
>
> Modalità di accesso (Frontend e Backend): Per quanto riguarda l'utilizzo diretto della
> piattaforma OSM2CAI, il frontend pubblico rimane liberamente accessibile a tutti per la
> consultazione della cartografia e dei dati esposti, mentre tutti i Soci CAI con profilo MyCAI
> attivo possono accedere anche all'area backend mediante le proprie credenziali istituzionali,
> in sola modalità di visualizzazione, per consultare i dettagli gestionali del catasto.
>
> Stato di percorribilità e frequenza di aggiornamento: Tra i dati gestiti nel sistema è
> presente anche il campo relativo allo stato di percorribilità del percorso; tuttavia, non
> possiamo garantire una presenza capillare né l'aggiornamento in tempo reale su tutto il
> territorio. La registrazione delle chiusure temporanee o contingenti (dovute a frane,
> maltempo o ordinanze sindacali) dipende infatti dalle segnalazioni e dalle validazioni
> effettuate dalle singole Sezioni locali o dagli enti territoriali competenti (Comuni, Parchi,
> Province Autonome). Gli aggiornamenti su OSM2CAI avvengono comunque su base continua, man mano
> che i referenti regionali e sezionali inseriscono e validano le modifiche.
>
> **2. Condizioni di utilizzo e licenze**
>
> Per quanto riguarda la possibilità di riutilizzare le informazioni nella Sua web-app:
>
> Dati su OSM2CAI / OpenStreetMap: I tracciati e i metadati presenti nell'ecosistema
> OpenStreetMap ed esposti tramite le API di OSM2CAI sono rilasciati con licenza ODbL (Open
> Database License). Tale licenza consente il riutilizzo anche per progetti, a condizione che
> venga sempre citata esplicitamente la fonte (OpenStreetMap / CAI) e che eventuali database
> derivati vengano condivisi con la medesima licenza.
>
> Informazioni e comunicati dai siti istituzionali CAI: Per le notizie, gli avvisi di chiusura o
> i contenuti pubblicati sui portali delle singole Sezioni o della Sede Centrale, il riutilizzo
> mediante sintesi e rimando alla fonte (con indicazione della data e link all'avviso originale)
> è generalmente consentito nell'ambito del diritto di cronaca e informazione, purché non si
> configuri una riproduzione sistematica e integrale dei contenuti protetti da diritto d'autore
> senza espressa autorizzazione.
>
> Nel rinnovarLe i nostri migliori auguri per lo sviluppo del Suo progetto, restiamo a
> disposizione e Le porgiamo cordiali saluti.

## Cosa autorizza e cosa no

| Tema | Cosa dice l'email | Conseguenza per il progetto |
|---|---|---|
| Dati OSM2CAI (tracciati e metadati via API) | Licenza **ODbL**; citare OpenStreetMap e CAI; database derivati con la stessa licenza | Uso pieno. Il database derivato di Cordata (sentieri, itinerari) va pubblicato in ODbL. Attribuzione secondo la pagina «Copyright e licenza» della documentazione (vedi `docs/data-sources.md`) |
| Stato di percorribilità | Presente ma non capillare né in tempo reale | Mostrarlo come «segnalazione della sezione», sempre con la data, mai come garanzia |
| Contenuti dei siti delle sezioni (locandine, avvisi) | Riuso **per sintesi con rimando alla fonte** (data e link) consentito; vietata la riproduzione sistematica e integrale senza autorizzazione espressa | Fase 2: si estraggono i fatti (data, difficoltà, km, dislivello, punti chiave), si scrive una sintesi propria e si rimanda al PDF originale. I PDF non vengono ripubblicati né ospitati; l'archivio grezzo resta privato e serve solo all'estrazione |
| Backend OSM2CAI per i soci (MyCAI) | Accesso in sola visualizzazione con credenziali personali | Non usato dall'app. Eventuali controlli manuali da parte della socia, senza ripubblicare contenuti riservati (SPEC §13-bis) |
| API delle attività di `organizzazione.cai.it` (`cai-activities/v1`) | **Non menzionata** | Non autorizzata: non viene usata. Bozza di richiesta specifica in `bozza-richiesta-api-attivita.md` |
