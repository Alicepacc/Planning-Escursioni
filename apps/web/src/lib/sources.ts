// Fonti dati e attribuzioni mostrate nella pagina «Fonti e licenze» (SPEC §3).
// Licenze verificate nella Fase 0: il dettaglio è in docs/data-sources.md.
export interface DataSource {
	name: string;
	use: string;
	license: string;
	attribution: string;
	url: string;
}

export const dataSources: DataSource[] = [
	{
		name: 'OpenStreetMap',
		use: 'Sentieri, punti di interesse, mappa di base',
		license: 'ODbL 1.0',
		attribution: '© OpenStreetMap contributors',
		url: 'https://www.openstreetmap.org/copyright'
	},
	{
		name: 'Club Alpino Italiano – Catasto REI (INFOMONT / OSM2CAI)',
		use: 'Catasto dei sentieri CAI: difficoltà, tempi ufficiali, stato di percorribilità',
		license: 'ODbL 1.0',
		attribution:
			'Dati sentieri: © Club Alpino Italiano – INFOMONT, derivati da © OpenStreetMap contributors',
		url: 'https://infomont.cai.it'
	},
	{
		name: 'SAT – Società degli Alpinisti Tridentini',
		use: 'Tracciati dei sentieri del Trentino (confronto e arricchimento)',
		license: 'ODbL 1.0',
		attribution: '© Società degli Alpinisti Tridentini (SAT)',
		url: 'https://www.sat.tn.it/sentieri/'
	},
	{
		name: 'Open-Meteo',
		use: 'Previsioni meteo in quota e zero termico',
		license: 'CC BY 4.0',
		attribution: 'Weather data by Open-Meteo.com (dati Copernicus e servizi meteo nazionali)',
		url: 'https://open-meteo.com/'
	},
	{
		name: 'avalanche.report (Euregio)',
		use: 'Bollettino valanghe di Alto Adige, Trentino e Tirolo',
		license: 'CC BY 4.0',
		attribution: '© avalanche.report – Servizi valanghe Euregio',
		url: 'https://avalanche.report/'
	},
	{
		name: 'Mapterhorn',
		use: 'Rilievo: ombreggiatura e profili altimetrici',
		license: 'Copernicus GLO-30, TINITALY (CC BY 4.0), LiDAR Provincia di Trento (CC BY 2.5)',
		attribution: '© Mapterhorn e fonti elencate su mapterhorn.com/attribution',
		url: 'https://mapterhorn.com/attribution'
	}
];
