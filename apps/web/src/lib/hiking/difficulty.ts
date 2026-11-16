// Scala di difficoltà CAI: sempre lettera + colore, mai solo colore (SPEC §9.6).
import type { CaiScale } from '../data/types';

export interface ScaleInfo {
	code: CaiScale;
	label: string;
	description: string;
	/** colore di sfondo del badge e della linea sulla mappa (contrasto AA con testo bianco) */
	color: string;
}

export const CAI_SCALES: Record<CaiScale, ScaleInfo> = {
	T: {
		code: 'T',
		label: 'Turistico',
		description:
			'Stradine, mulattiere o sentieri comodi e ben evidenti, senza problemi di orientamento.',
		color: '#2f7a4f'
	},
	E: {
		code: 'E',
		label: 'Escursionistico',
		description:
			'Sentieri o tracce su terreno vario; servono allenamento, senso di orientamento e calzature adatte.',
		color: '#c0392b'
	},
	EE: {
		code: 'EE',
		label: 'Escursionisti esperti',
		description:
			'Terreno impegnativo: pendii ripidi, tratti rocciosi o ghiaioni. Servono passo sicuro, assenza di vertigini ed esperienza.',
		color: '#6a3fb5'
	},
	EEA: {
		code: 'EEA',
		label: 'Esperti con attrezzatura',
		description: 'Percorsi attrezzati o vie ferrate: servono imbrago, set da ferrata e casco.',
		color: '#1f2933'
	},
	EAI: {
		code: 'EAI',
		label: 'Escursionismo in ambiente innevato',
		description:
			'Itinerari con racchette da neve su terreno innevato: servono ARTVA, pala e sonda e la lettura del bollettino valanghe.',
		color: '#1d5f8f'
	}
};

export function scaleInfo(code: string | null | undefined): ScaleInfo | null {
	if (!code) return null;
	const upper = code.toUpperCase().split(':')[0];
	if (upper.startsWith('EAI')) return CAI_SCALES.EAI; // EAI-F, EAI-PD…
	// «E-EE» (tratti EE): si mostra il grado più alto
	const base = upper.split('-').pop() as CaiScale;
	return CAI_SCALES[base] ?? null;
}
