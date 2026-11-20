// Tema dell'app (ADR 0015): segue il telefono, oppure chiaro o scuro scelto nel profilo.

export type ThemePref = 'auto' | 'light' | 'dark';
const KEY = 'cordata.tema';

export function getTheme(): ThemePref {
	try {
		const v = localStorage.getItem(KEY);
		return v === 'light' || v === 'dark' ? v : 'auto';
	} catch {
		return 'auto';
	}
}

export function setTheme(pref: ThemePref): void {
	const root = document.documentElement;
	if (pref === 'auto') delete root.dataset.theme;
	else root.dataset.theme = pref;
	try {
		if (pref === 'auto') localStorage.removeItem(KEY);
		else localStorage.setItem(KEY, pref);
	} catch {
		// spazio locale non disponibile: il tema vale solo per questa visita
	}
}
