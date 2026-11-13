import { messages, type Locale, type MessageKey } from './messages';

export { locales, type Locale, type MessageKey } from './messages';

/** Traduce una chiave; se manca nella lingua richiesta usa l'italiano. */
export function t(
	key: MessageKey,
	locale: Locale = 'it',
	params: Record<string, string | number> = {}
): string {
	const template = messages[locale][key] ?? messages.it[key] ?? key;
	return template.replace(/\{(\w+)\}/g, (match, name: string) =>
		name in params ? String(params[name]) : match
	);
}
