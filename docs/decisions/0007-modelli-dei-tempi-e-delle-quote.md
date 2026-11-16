# ADR 0007 – Modelli dei tempi e calcolo del dislivello

- **Stato**: accettata (parametri del dislivello da ricalibrare nella Fase 2 sul pilota)
- **Data**: 16/11/2026
- **Codice**: `services/ingest/src/cordata_ingest/timing.py`, `geo/elevation.py`,
  `geo/profile.py`; stesse formule in `apps/web/src/lib/hiking/time.ts`
- **Evidenze**: `reports/phase1/calibrazione/` (`python -m cordata_ingest.calibration`)

## 1. Modello dei tempi CAI / Sentieri Svizzeri

**Fonte.** Il Quaderno n. 1 «Sentieri» del CAI (p. 51) indica due metodi: una regola pratica
(350 m/h in salita, 500 m/h in discesa, 3,5-4 km/h in piano) e, per un calcolo preciso, il
diagramma dei tempi dell'Ente Svizzero Pro Sentieri (Schweizer Wanderwege, © 1986), riprodotto
anche nel manuale ufficiale «Signalisation Wanderwege» (ASTRA e Schweizer Wanderwege, 2013,
p. 66). Il manuale svizzero (§3.1.2) precisa: 4,2 km/h in piano, formula unica definita dai
Sentieri Svizzeri, calcolo su modello digitale del terreno, tempo «per esperienza» oltre il 40%
di pendenza.

**Formula.** Tempo [min] = distanza orizzontale [km] × f(s), con f polinomio di grado 15 nella
pendenza s in percento (coefficienti C0…C15 in `timing.py`, C0 = 14,271 min/km = 4,2 km/h).
I coefficienti non compaiono nei PDF pubblici consultati: sono quelli della formula svizzera di
uso comune e sono stati **verificati contro il diagramma ufficiale**:

| Verifica | Risultato |
|---|---|
| 620 attraversamenti delle isocrone, digitalizzati dal diagramma del manuale ASTRA lungo 13 colonne di dislivello (da +300 a −300 m) | scarto medio 0,085 min dal minuto intero (un polinomio sbagliato darebbe circa 0,25) |
| Apice dell'isocrona dei 60 minuti | diagramma 4,53 km a −218 m; formula 4,55 km a −227 m |
| Velocità in piano | 60 / f(0) = 4,20 km/h, come nel manuale |
| Casi della SPEC su 1 km: +100 / +300 / −100 / −300 m | 20,0 / 48,8 / 14,2 / 27,5 min (attesi ≈ 20 / 49 / 14 / 27-28) |
| Tempi ufficiali OSM2CAI, ricalcolati dai loro stessi distanza e dislivello (salita e discesa separate) | distorsione 0,0 min: il catasto usa la stessa formula |

**Parametri.** Pendenza limitata a ±40% (oltre, il tratto viene segnalato come «tempo poco
affidabile»); tempo calcolato su tratti di 15 m lungo il profilo smussato.

**Confronto con il catasto** (1.080 sentieri validati dell'area pilota, calcolo indipendente sul
DEM Mapterhorn): errore medio 18-19 minuti, distorsione entro ±3 minuti, errore mediano 13-14%.
Il residuo viene dal DEM diverso e dagli arrotondamenti: i tempi del catasto sono multipli di 15
minuti e una parte è inserita a mano dalle sezioni (`manual_data`).

## 2. DIN 33466 (confronto)

300 m/h in salita, 500 m/h in discesa, 4 km/h; il maggiore tra tempo orizzontale e verticale
più metà del minore. Sulla fixture dà esattamente 7:00 con i valori dichiarati. È mostrata come
confronto: sui sentieri del catasto sovrastima di circa 80 minuti in media.

## 3. Tempo con soste e fattori personali

- Tempo **netto** sempre mostrato; tempo **con soste** = netto × 1,20 (SPEC: +15-20%). Sulla
  fixture: 5:50 netto × 1,20 = 7:00, pari al tempo dichiarato dalla locandina.
- Fattore di allenamento 0,7-1,4 e fattore gruppo ≥ 1 (es. 1,5 con bambini), nel profilo utente.

## 4. Dislivello

**DEM.** Mapterhorn, campionato a z12 (13 m per pixel) ogni 15 m lungo la traccia, con
interpolazione bilineare. Scarto sulle quote OSM dei punti chiave della fixture: entro ±4 m,
tranne la cima (−12 m). È lo stesso dato del rilievo sulla mappa.

**Filtro.** Media mobile centrata (simmetrica anche ai bordi, così le quote di partenza e arrivo
restano quelle misurate) e soglia di isteresi; alla fine si somma il residuo sotto soglia, in
modo che salita − discesa = quota finale − quota iniziale.

**Due definizioni diverse di «dislivello».** La calibrazione ha mostrato che:

- il **catasto CAI** riporta valori più alti persino della somma grezza sul nostro DEM
  (distorsione −29 m senza alcun filtro, −86 m con media mobile di 75 m e soglia di 10 m):
  conta tutte le micro-risalite del suo modello del terreno;
- la **locandina** della fixture dichiara 950 m, contro 1.175 m grezzi e 1.030 m filtrati.

Non esiste quindi un solo valore «vero». Regole adottate:

1. dove esistono, si mostrano i valori **ufficiali** (catasto o sezione), con i calcolati come
   confronto (SPEC §8);
2. per gli itinerari calcolati da Cordata si usano media mobile 75 m e soglia 10 m, i parametri
   più vicini a come le sezioni dichiarano il dislivello (fixture: +8%);
3. nella **Fase 2** i parametri si ricalibrano sulle 20 attività del pilota, confrontando con i
   dislivelli dichiarati dalle sezioni.

## 5. Difficoltà

`cai_scale` delle relazioni prevale; dove manca, stima indicativa da `sac_scale` (`hiking` e
`mountain_hiking` → E, `demanding_mountain_hiking` → EE, dagli `alpine_hiking` in su → EEA,
esclusi dal routing di default); strade e piste senza `sac_scale` → T. Sulla mappa i tratti con
difficoltà stimata sono tratteggiati. La difficoltà dichiarata dalla sezione prevale: nella
fixture i tag indicano E, la locandina EE per il tratto fuori sentiero verso la cima.
