# Calibrazione di dislivello e tempi contro OSM2CAI

Sentieri validati (`sda` 4) dell'area pilota usati: **1375**. Esclusi: fuori area 71, senza valori ufficiali 89, geometria spezzata 7, sda < 4 710.

DEM: Mapterhorn z12 (Terrarium), campionamento ogni 15 m lungo la geometria OSM2CAI. Verità di riferimento: `ascent`, `descent`, `duration_forward`, `duration_backward` del catasto.

## Dislivello

| Media mobile | Isteresi | D+ errore medio | D+ distorsione | D+ mediana errore % | D+ entro ±15% | D− errore medio |
|---|---|---|---|---|---|---|
| 15 m | 0 m | 57 m **←** | -24 m | 11.3% | 57% | 57 m |
| 15 m | 3 m | 70 m | -47 m | 14.0% | 52% | 71 m |
| 15 m | 5 m | 76 m | -57 m | 15.5% | 49% | 77 m |
| 15 m | 10 m | 86 m | -72 m | 17.6% | 46% | 87 m |
| 15 m | 15 m | 92 m | -81 m | 19.5% | 44% | 94 m |
| 45 m | 0 m | 67 m | -48 m | 13.8% | 52% | 68 m |
| 45 m | 3 m | 77 m | -62 m | 15.3% | 49% | 78 m |
| 45 m | 5 m | 82 m | -68 m | 16.7% | 47% | 83 m |
| 45 m | 10 m | 89 m | -78 m | 18.7% | 44% | 91 m |
| 45 m | 15 m | 95 m | -85 m | 20.7% | 43% | 97 m |
| 75 m | 0 m | 74 m | -59 m | 15.0% | 50% | 75 m |
| 75 m | 3 m | 82 m | -69 m | 16.8% | 47% | 83 m |
| 75 m | 5 m | 86 m | -74 m | 17.7% | 45% | 87 m |
| 75 m | 10 m | 92 m | -82 m | 19.6% | 43% | 94 m |
| 75 m | 15 m | 98 m | -88 m | 21.4% | 42% | 99 m |
| 105 m | 0 m | 79 m | -66 m | 16.4% | 48% | 80 m |
| 105 m | 3 m | 85 m | -74 m | 18.0% | 46% | 87 m |
| 105 m | 5 m | 88 m | -78 m | 18.6% | 45% | 90 m |
| 105 m | 10 m | 95 m | -85 m | 20.1% | 43% | 96 m |
| 105 m | 15 m | 100 m | -91 m | 21.6% | 42% | 101 m |
| 135 m | 0 m | 82 m | -71 m | 17.2% | 47% | 84 m |
| 135 m | 3 m | 88 m | -78 m | 18.8% | 45% | 89 m |
| 135 m | 5 m | 91 m | -81 m | 19.3% | 44% | 92 m |
| 135 m | 10 m | 97 m | -88 m | 20.7% | 42% | 98 m |
| 135 m | 15 m | 101 m | -93 m | 21.9% | 42% | 103 m |

## Tempi (modello CAI / Sentieri Svizzeri)

| Media mobile | Tratti | Errore medio | Distorsione | Mediana errore % | Entro ±15% |
|---|---|---|---|---|---|
| 15 m | 15 m | 18.3 min **←** | +3.3 min | 13.0% | 56% |
| 15 m | 50 m | 18.5 min | -1.3 min | 14.1% | 54% |
| 15 m | 100 m | 18.9 min | -3.3 min | 14.7% | 51% |
| 15 m | 200 m | 19.8 min | -5.9 min | 15.6% | 48% |
| 15 m | 500 m | 21.5 min | -9.5 min | 17.0% | 43% |
| 45 m | 15 m | 18.3 min | -0.3 min | 13.7% | 55% |
| 45 m | 50 m | 18.6 min | -2.0 min | 14.3% | 53% |
| 45 m | 100 m | 19.0 min | -3.6 min | 14.7% | 51% |
| 45 m | 200 m | 19.9 min | -6.0 min | 15.6% | 48% |
| 45 m | 500 m | 21.5 min | -9.6 min | 17.0% | 43% |
| 75 m | 15 m | 18.6 min | -2.1 min | 14.3% | 53% |
| 75 m | 50 m | 18.8 min | -2.9 min | 14.5% | 52% |
| 75 m | 100 m | 19.2 min | -4.0 min | 14.9% | 50% |
| 75 m | 200 m | 19.9 min | -6.1 min | 15.6% | 48% |
| 75 m | 500 m | 21.5 min | -9.6 min | 17.0% | 43% |
| 105 m | 15 m | 18.9 min | -3.3 min | 14.7% | 52% |
| 105 m | 50 m | 19.1 min | -3.8 min | 14.9% | 51% |
| 105 m | 100 m | 19.3 min | -4.5 min | 15.1% | 50% |
| 105 m | 200 m | 20.0 min | -6.3 min | 15.7% | 48% |
| 105 m | 500 m | 21.5 min | -9.7 min | 17.0% | 43% |
| 135 m | 15 m | 19.2 min | -4.2 min | 14.9% | 50% |
| 135 m | 50 m | 19.3 min | -4.5 min | 15.1% | 50% |
| 135 m | 100 m | 19.5 min | -5.0 min | 15.2% | 49% |
| 135 m | 200 m | 20.1 min | -6.5 min | 15.7% | 47% |
| 135 m | 500 m | 21.6 min | -9.7 min | 17.1% | 43% |

## Migliori parametri rispetto al catasto

Le frecce nelle tabelle indicano i parametri più vicini ai valori del catasto. Per il dislivello Cordata **non** li adotta: il catasto conta tutte le micro-risalite, mentre le sezioni dichiarano un dislivello «da escursionista». Parametri adottati e motivazioni in `docs/decisions/0007-modelli-dei-tempi-e-delle-quote.md`.

- Dislivello: media mobile 15 m, isteresi 0 m → D+ errore medio 57 m, mediana 11.3%.
- Tempi: media mobile 15 m, tratti di 15 m → errore medio 18.3 min, mediana 13.0%. I tempi ufficiali sono arrotondati a 15 minuti: un errore medio sotto i 7-8 minuti è al livello dell'arrotondamento.
