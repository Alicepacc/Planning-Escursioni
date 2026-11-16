// Formattazione dei numeri in italiano: 15,5 km · 2253 m · 12.345 m · 5:50 h.
import { formatMinutes } from './time';

const km1 = new Intl.NumberFormat('it-IT', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const int = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 0 });

export function formatKm(km: number | null | undefined): string {
	return km == null ? '–' : `${km1.format(km)} km`;
}

export function formatMeters(m: number | null | undefined): string {
	return m == null ? '–' : `${int.format(Math.round(m))} m`;
}

export function formatDuration(minutes: number | null | undefined): string {
	return minutes == null ? '–' : `${formatMinutes(minutes)} h`;
}

export function formatDate(iso: string | null | undefined): string {
	if (!iso) return '–';
	const date = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
	if (Number.isNaN(date.getTime())) return iso;
	return new Intl.DateTimeFormat('it-IT', {
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	}).format(date);
}
