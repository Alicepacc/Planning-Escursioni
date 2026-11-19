// Posti e lista d'attesa: regole pure, senza database, per poterle provare a fondo.

export type StatoPartecipante = 'confermato' | 'attesa' | 'rinunciato';

export interface Iscrizione {
	utente: string;
	stato: StatoPartecipante;
	/** ordine di arrivo (ISO): la lista d'attesa scorre in quest'ordine */
	iscritto: string;
}

export function confermati(iscrizioni: Iscrizione[]): number {
	return iscrizioni.filter((i) => i.stato === 'confermato').length;
}

/** Stato di chi si iscrive ora: confermato se c'è posto (o i posti non sono limitati). */
export function statoNuovaIscrizione(posti: number | null, iscrizioni: Iscrizione[]): StatoPartecipante {
	if (posti == null) return 'confermato';
	return confermati(iscrizioni) < posti ? 'confermato' : 'attesa';
}

/**
 * Chi passa da «attesa» a «confermato» quando si libera un posto: i primi arrivati, fino a
 * riempire i posti. Restituisce gli utenti promossi, in ordine.
 */
export function promossi(posti: number | null, iscrizioni: Iscrizione[]): string[] {
	const attesa = iscrizioni
		.filter((i) => i.stato === 'attesa')
		.sort((a, b) => a.iscritto.localeCompare(b.iscritto));
	if (posti == null) return attesa.map((i) => i.utente);
	const liberi = Math.max(0, posti - confermati(iscrizioni));
	return attesa.slice(0, liberi).map((i) => i.utente);
}

/** Le iscrizioni sono aperte? (uscita non annullata e termine non scaduto) */
export function iscrizioniAperte(stato: string, entro: string | null, adesso: string): boolean {
	if (stato === 'annullata') return false;
	return entro == null || adesso <= entro;
}
