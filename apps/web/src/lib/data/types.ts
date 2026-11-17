// Formato dei documenti JSON prodotti da services/ingest/src/cordata_ingest/build/documents.py.
// I due file vanno tenuti allineati (campo `schema`).

export type CaiScale = 'T' | 'E' | 'EE' | 'EEA' | 'EAI';

/** [distanza m, quota m, lon, lat, minuti cumulati in andata (modello CAI)] */
export type ProfilePoint = [number, number, number, number, number];

export interface Profile {
	columns: string[];
	points: ProfilePoint[];
}

export interface ComputedStats {
	distance_km: number;
	ascent_m: number;
	descent_m: number;
	min_ele_m: number;
	max_ele_m: number;
	cai_forward_min: number;
	cai_backward_min: number;
	din_forward_min: number;
	din_backward_min: number;
	steep_m: number;
	gaps: number;
	method: {
		dem: string;
		step_m: number;
		smoothing_m: number;
		hysteresis_m: number;
		time_model: string;
		time_segment_m: number;
	};
}

export interface Difficulty {
	cai: CaiScale | null;
	raw: string | null;
}

export interface TrailDoc {
	schema: number;
	kind: 'sentiero';
	id: string;
	ref: string;
	name: string;
	name_de?: string | null;
	from: string;
	to: string;
	roundtrip: boolean;
	difficulty: Difficulty;
	network: string | null;
	operator: string | null;
	color: string;
	osmc_symbol: string | null;
	sda: number | null;
	validation_date: string | null;
	issues: { status: string; description: string; updated: string };
	values_source?: string | null;
	official: {
		distance_km: number | null;
		ascent_m: number | null;
		descent_m: number | null;
		duration_forward_min: number | null;
		duration_backward_min: number | null;
	};
	computed: ComputedStats;
	bbox: [number, number, number, number];
	line: [number, number][];
	profile: Profile;
	links: { osm2cai: string | null; osm: string | null };
	attribution: string[];
	generated_at: string;
}

export interface Stage {
	name: string;
	declared_ele_m: number | null;
	ele_m: number;
	dist_km: number;
	cai_min: number;
	offset_m: number;
	osm?: string;
}

export interface TrailOnRoute {
	relation_id: number;
	osm2cai_id: string | null;
	ref: string;
	name: string;
	cai: CaiScale | null;
	network: string | null;
	km_on_route: number;
}

export interface ItineraryDoc {
	schema: number;
	/** itinerario (fixture) o attività CAI dell'archivio (build/activities.py) */
	kind: 'itinerario' | 'attivita';
	id: string;
	title: string;
	group: string;
	type: string;
	start: {
		nome: string;
		quota_m: number | null;
		comune: string;
		ora?: string;
		lon?: number;
		lat?: number;
	};
	difficulty: Difficulty;
	/** valori della locandina: possono mancare (null) */
	declared: {
		distance_km: number | null;
		ascent_m: number | null;
		descent_m: number | null;
		max_ele_m: number | null;
		duration: string | null;
		difficulty: string | null;
	};
	computed: ComputedStats;
	trails: TrailOnRoute[];
	networks: string[];
	off_trail: string[];
	stages: Stage[];
	equipment: string[];
	notes: string[];
	map_reference: string;
	/** sintesi composta dai soli dati (attività) */
	summary?: string;
	activity: {
		date: string | null;
		future?: boolean;
		organizers: string[];
		signup_note: string;
		source_url: string | null;
		source_page?: number | null;
		transport?: string | null;
	};
	/** deduplica (§7.5): itinerario canonico, proposte dello stesso itinerario, varianti */
	canonical?: string;
	proposals?: { id: string; section: string; date: string | null }[];
	related?: { id: string; title: string; relation: 'variante'; hausdorff_m: number }[];
	/** esito della ricostruzione automatica (attività) */
	verification?: {
		status: 'auto_ok' | 'da_rivedere' | 'fallita';
		reasons: string[];
		on_cited_share: number | null;
	};
	bbox: [number, number, number, number];
	line: [number, number][];
	profile: Profile;
	reconstruction: string;
	attribution: string[];
	generated_at: string;
}

export interface TrailIndexEntry {
	id: string;
	ref: string;
	name: string;
	from: string;
	to: string;
	cai: CaiScale | null;
	km: number | null;
	up: number | null;
	min: number | null;
	sda: number | null;
	bbox: [number, number, number, number];
	issues: string;
}

/** Proprietà dei tratti di sentiero nel layer `sentieri` dei PMTiles. */
export interface TrailWayProps {
	refs: string;
	scale: string;
	scale_rank: number;
	scale_derived: boolean;
	sac: string;
	vis: string;
	hw: string;
	net: number;
	cai: string;
	rel: string;
	sda: number;
	color: string;
}

/** Punto di partenza di una proposta in Esplora (k: s sentiero, a attività, i itinerario). */
export interface MapPoint {
	id: string;
	lon: number;
	lat: number;
	k: string;
}
