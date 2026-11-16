// Periodo consigliato indicativo dalla quota massima (stessa regola di build/explore.py).

const MONTH_NAMES = [
	'gennaio',
	'febbraio',
	'marzo',
	'aprile',
	'maggio',
	'giugno',
	'luglio',
	'agosto',
	'settembre',
	'ottobre',
	'novembre',
	'dicembre'
];

export function seasonMonths(maxEle: number, difficulty: string | null | undefined): number[] {
	if (difficulty && difficulty.toUpperCase().startsWith('EAI')) return [12, 1, 2, 3];
	if (maxEle < 1200) return [3, 4, 5, 6, 7, 8, 9, 10, 11];
	if (maxEle < 1800) return [5, 6, 7, 8, 9, 10];
	if (maxEle < 2400) return [6, 7, 8, 9, 10];
	return [7, 8, 9];
}

export function seasonText(months: number[]): string {
	if (!months.length) return '–';
	return `da ${MONTH_NAMES[months[0] - 1]} a ${MONTH_NAMES[months[months.length - 1] - 1]}`;
}
