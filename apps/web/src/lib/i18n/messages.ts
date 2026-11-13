// Testi dell'interfaccia. L'italiano è la lingua di riferimento; tedesco e inglese vengono
// completati nelle fasi successive (le chiavi mancanti ricadono sull'italiano).
export const locales = ['it', 'de', 'en'] as const;
export type Locale = (typeof locales)[number];

const it = {
	'app.name': 'Cordata',
	'app.tagline': 'Escursioni in montagna, con dati aperti',
	'nav.explore': 'Esplora',
	'nav.plan': 'Pianifica',
	'nav.outings': 'Uscite',
	'nav.profile': 'Profilo',
	'nav.sources': 'Fonti e licenze',
	'home.title': 'Esplora le proposte',
	'home.status': 'Fondamenta in costruzione: mappa e proposte arrivano nelle prossime fasi.',
	'placeholder.phase': 'Questa sezione arriva nella Fase {phase}.',
	'sources.title': 'Fonti e licenze',
	'sources.intro':
		'Cordata usa solo dati aperti. Ogni dato mostrato riporta la fonte da cui proviene.',
	'safety.emergency': 'Emergenza in montagna: 112'
} as const;

export type MessageKey = keyof typeof it;

const de: Partial<Record<MessageKey, string>> = {
	'app.tagline': 'Bergwanderungen mit offenen Daten',
	'nav.explore': 'Entdecken',
	'nav.plan': 'Planen',
	'nav.outings': 'Touren',
	'nav.profile': 'Profil',
	'nav.sources': 'Quellen und Lizenzen',
	'safety.emergency': 'Notruf am Berg: 112'
};

const en: Partial<Record<MessageKey, string>> = {
	'app.tagline': 'Mountain hikes, built on open data',
	'nav.explore': 'Explore',
	'nav.plan': 'Plan',
	'nav.outings': 'Outings',
	'nav.profile': 'Profile',
	'nav.sources': 'Sources and licences',
	'safety.emergency': 'Mountain emergency: 112'
};

export const messages: Record<Locale, Partial<Record<MessageKey, string>>> = { it, de, en };
