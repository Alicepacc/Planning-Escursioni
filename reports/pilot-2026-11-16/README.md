# Pilota Fase 2: 20 attività CAI (16/11/2026)

**Checkpoint bloccante (SPEC §7.6):** nessuna ingestion su tutte le sezioni e nessun crawler
periodico prima dell'approvazione.

| File | Contenuto |
|---|---|
| [`pilot.html`](pilot.html) | Una scheda per attività: link alla locandina, campi estratti con confidenza, traccia, profilo, confronto dichiarato/calcolato, stato |
| [`metrics.md`](metrics.md) | Precisione per campo (anche su 8 locandine non viste), auto_ok, cause, tempi, costi, stima per l'ingestion completa |
| [`decisions.md`](decisions.md) | Problemi trovati, decisioni prese nel pilota, proposte, domande per l'utente |

In breve:

- 20 attività da CAI Bolzano, CAI Bressanone, CAI Appiano e 7 locandine SAT (6 sezioni), con il
  mix richiesto (12 anelli, 4 traversate, 4 andata e ritorno, 5 EE, 2 EAI, 2 da calendari, 2 PDF
  difficili) più la fixture Val d'Inferno (#0).
- Parser a regole: 96,8% dei valori estratti corretti sul pilota, 92,4% su locandine mai viste;
  un terzo dei campi va rivisto (quasi sempre partenza, tipo di percorso e punti chiave).
- Tracce: **7 auto_ok su 20**, 13 da rivedere con il motivo, nessuna fallita; la fixture è auto_ok
  (+5,5% km, +10,7% D+). Senza revisione dei campi: 3 auto_ok e 6 fallite.
- Costo LLM: zero chiamate API (parser + revisione in Claude Code).

Le locandine non sono ripubblicate: restano nell'archivio privato `data/activities/raw`.
