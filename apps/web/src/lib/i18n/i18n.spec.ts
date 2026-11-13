import { describe, expect, it } from 'vitest';
import { locales, t } from './index';
import { messages } from './messages';

describe('i18n', () => {
	it('usa l’italiano come lingua predefinita', () => {
		expect(t('nav.explore')).toBe('Esplora');
	});

	it('traduce in tedesco e in inglese', () => {
		expect(t('nav.plan', 'de')).toBe('Planen');
		expect(t('nav.plan', 'en')).toBe('Plan');
	});

	it('ricade sull’italiano quando la chiave manca', () => {
		expect(messages.de['home.title']).toBeUndefined();
		expect(t('home.title', 'de')).toBe('Esplora le proposte');
	});

	it('sostituisce i parametri', () => {
		expect(t('placeholder.phase', 'it', { phase: 4 })).toBe('Questa sezione arriva nella Fase 4.');
	});

	it('non ha chiavi sconosciute nelle altre lingue', () => {
		const known = new Set(Object.keys(messages.it));
		for (const locale of locales) {
			for (const key of Object.keys(messages[locale])) {
				expect(known.has(key), `${locale}: ${key}`).toBe(true);
			}
		}
	});
});
