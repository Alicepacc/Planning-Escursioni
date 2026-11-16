# ADR 0006 – Estrazione delle locandine senza API LLM a pagamento

- **Stato**: accettata
- **Data**: 16/11/2026

## Contesto

La SPEC (§7.3, §10) prevede l'estrazione strutturata con la Claude API, che si paga a consumo
e non è inclusa nell'abbonamento Claude Pro. Il budget è zero (ADR 0005).

## Decisione

Estrazione in due livelli:

1. **Parser a regole, automatico e gratuito.** PyMuPDF estrae testo e layout; regole
   specifiche per sezione e per tipo di documento (locandina singola, libretto annuale)
   riconoscono data, difficoltà, dislivello, durata, distanza, partenza, sentieri citati e
   punti chiave. Ogni campo ha una confidenza e la citazione del testo da cui proviene. I dati
   personali vengono scartati prima del salvataggio.
2. **Revisione con Claude Code nelle sessioni di sviluppo**, coperta dall'abbonamento: i campi
   a bassa confidenza, i layout nuovi e la lettura dei PDF come immagini (mappe, profili,
   tabelle) vengono rivisti in sessione. Le correzioni diventano casi dell'harness di
   valutazione e, dove possibile, nuove regole del parser.

## Conseguenze

- L'harness di valutazione (locandine → campi attesi) diventa ancora più centrale: misura il
  parser da solo e il parser più la revisione.
- Le attività nuove compaiono subito con i campi estratti dal parser; quelle con confidenza
  bassa restano «da rivedere» fino alla sessione successiva.
- Le funzioni basate su un modello linguistico in produzione (ricerca in linguaggio naturale
  §5.7b, briefing §5.7c, descrizioni generate §5.7a) vanno ripensate per il vincolo di costo:
  versioni a regole e template, oppure testi pre-generati in sessione. Da decidere nelle fasi
  in cui servono.
- Contenuti delle sezioni: si pubblicano solo fatti estratti e una sintesi propria, con data e
  link alla fonte, come indicato dal CAI (`docs/legal/2026-11-cai-risposta-uso-dati.md`).
