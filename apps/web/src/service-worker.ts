/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />
// Service worker minimo per le notifiche delle uscite (Fase 5). La cache per l'uso offline
// arriverà nella Fase 7: qui nessuna risposta viene intercettata.

const sw = self as unknown as ServiceWorkerGlobalScope;

interface Message {
	titolo?: string;
	testo?: string;
	url?: string;
}

sw.addEventListener('install', () => {
	void sw.skipWaiting();
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(sw.clients.claim());
});

sw.addEventListener('push', (event) => {
	let msg: Message;
	try {
		msg = event.data?.json() ?? {};
	} catch {
		msg = { testo: event.data?.text() };
	}
	event.waitUntil(
		sw.registration.showNotification(msg.titolo ?? 'Cordata', {
			body: msg.testo ?? '',
			icon: new URL('icons/icona-192.png', sw.registration.scope).href,
			data: { url: msg.url ?? sw.registration.scope },
			lang: 'it'
		})
	);
});

sw.addEventListener('notificationclick', (event) => {
	event.notification.close();
	const url = (event.notification.data as { url?: string } | null)?.url ?? sw.registration.scope;
	event.waitUntil(
		(async () => {
			const windows = await sw.clients.matchAll({ type: 'window', includeUncontrolled: true });
			const open = windows.find((w) => w.url === url);
			if (open) return open.focus();
			return sw.clients.openWindow(url);
		})()
	);
});
