# ADR 0002 – Motore di routing: GraphHopper

- **Stato**: accettata il 16/11/2026 (checkpoint della Fase 0). Hosting: Mac di casa (ADR 0005)
- **Data**: 13/11/2026
- **Evidenze**: `reports/phase0/routing-spike/` (script: `services/routing/spike/run_spike.py`)

## Contesto

Servono due cose diverse: un motore **interattivo** per il planner (difficoltà massima,
statistiche live) e un modo per **ricostruire le tracce** delle gite CAI privilegiando i
sentieri citati (§7.4). Lo spike ha confrontato GraphHopper 11.1 e BRouter 1.6.3 sulla fixture
golden (dichiarati: 15,5 km, ±950 m, quota massima 2.253 m), misurando entrambi allo stesso
modo: distanza sulla geometria, dislivello su un DEM comune (SRTM 1", passo 15 m, media mobile
75 m, isteresi 10 m).

## Risultati

| Scenario | Motore | km | D+ nativo | D+ ricalcolato | Sui sentieri citati |
|---|---|---|---|---|---|
| 5 waypoint («rado») | GraphHopper | 15,62 (+0,8%) | 1.284 | 980 (+3,1%) | 53% |
| 5 waypoint («rado») | BRouter | 15,72 (+1,4%) | 1.020 | 989 (+4,1%) | 50% |
| 12 waypoint («completo») | GraphHopper | 16,41 (+5,9%) | 1.338 | 1.011 (+6,4%) | 50% |
| 12 waypoint («completo») | BRouter | 16,47 (+6,2%) | 1.066 | 989 (+4,1%) | 48% |
| solo partenza e cima («minimo») | entrambi | 10,69 (−31%) | – | ~950 | 16% |

Entrambi ricostruiscono l'anello entro le tolleranze (±10% km, ±15% D+, quota massima ±50 m)
quando hanno almeno i 5 waypoint principali; le due tracce coincidono quasi ovunque (vedi
`map-rado.png`). Nessuno dei due trova l'anello con la sola cima: i punti chiave servono.

## Decisione

**GraphHopper** come motore unico per planner e ricostruzione.

- **Custom model per richiesta**: la difficoltà massima (`hike_rating`) e la preferenza per i
  sentieri citati (aree poligonali costruite dalle geometrie delle relazioni) si passano nel
  corpo della richiesta, senza ricostruire il grafo. Nello scenario «minimo» la preferenza
  porta la quota di traccia sui sentieri citati dal 16% all'87%.
- **`osm_way_id` per ogni tratto**: permette di risalire alle relazioni attraversate (numero
  del sentiero, `cai_scale`) e quindi di compilare l'elenco dei sentieri usati e la difficoltà
  massima. BRouter restituisce solo i tag della way, non l'identificativo.
- **Operatività**: import del Trentino-Alto Adige in ~25 s con ~1,3 GB di RAM; risposte in
  30-160 ms; rilasci regolari su Maven Central; licenza Apache 2.0.

BRouter resta un riferimento: il suo dislivello «filtrato» nativo è più vicino al dichiarato
(+7-12% contro +35-41% di GraphHopper), ma il binario pubblico è fermo alla 1.6.3 (2021), i
profili attuali richiedono un `lookups.dat` più recente e la personalizzazione per richiesta
passa dal caricamento di profili.

## Conseguenze

- **Il dislivello non si prende dal motore**: si ricalcola sempre dal DEM con isteresi (§8).
  Con soglia 10 m l'errore sulla fixture è +3%; con 5 m è +7%; senza filtro +33%. La
  calibrazione definitiva è della Fase 1, con Mapterhorn al posto di SRTM (sulla cima: 2.240 m
  contro 2.232 m di SRTM e 2.253 m reali).
- **I punti chiave vanno trattati come «passa vicino», non come tappe obbligate**: con tutti
  i 12 punti la traccia si allunga del 5% per le deviazioni verso oggetti non sul sentiero
  (centro di un lago, edificio del rifugio). Nella Fase 2 i waypoint si agganciano al punto
  più vicino dei sentieri candidati.
- **Né `cai_scale` né i numeri dei sentieri sono nel grafo**: l'attribuzione ai sentieri CAI
  si fa a valle, con la tabella way → relazioni costruita dall'estratto OSM e collegata a
  OSM2CAI tramite `relation_id`.
- **La difficoltà da sola non basta**: sulla fixture, dichiarata EE, tutte le way percorse
  hanno al massimo `sac_scale=mountain_hiking` e relazioni `cai_scale=E`: il limite «massimo
  E» non cambia la traccia. La difficoltà dichiarata dalla sezione deve prevalere su quella
  calcolata (§8) e il tratto verso la cima va segnalato a parte.
- L'altimetria interna di GraphHopper (SRTM) serve solo ai pesi del routing.
