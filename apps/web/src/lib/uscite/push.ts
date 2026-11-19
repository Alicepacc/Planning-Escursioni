// Iscrizione del browser alle notifiche push delle uscite.

import { pushKey, removePush, savePush } from './api';

export type PushState = 'non-supportate' | 'negate' | 'attive' | 'spente';

export function pushSupported(): boolean {
	return (
		typeof navigator !== 'undefined' &&
		'serviceWorker' in navigator &&
		typeof window !== 'undefined' &&
		'PushManager' in window &&
		'Notification' in window
	);
}

/** iPhone e iPad: le notifiche arrivano solo con l'app aggiunta alla schermata Home. */
export function needsInstallOnIos(): boolean {
	if (typeof navigator === 'undefined') return false;
	const ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
	const standalone =
		typeof window !== 'undefined' && window.matchMedia?.('(display-mode: standalone)').matches;
	return ios && !standalone;
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
	const b64 =
		base64url.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((base64url.length + 3) % 4);
	return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

export async function pushState(): Promise<PushState> {
	if (!pushSupported()) return 'non-supportate';
	if (Notification.permission === 'denied') return 'negate';
	const reg = await navigator.serviceWorker.getRegistration();
	const sub = await reg?.pushManager.getSubscription();
	return sub ? 'attive' : 'spente';
}

export async function enablePush(): Promise<PushState> {
	if (!pushSupported()) return 'non-supportate';
	const permission = await Notification.requestPermission();
	if (permission !== 'granted') return 'negate';
	const { chiave } = await pushKey();
	const reg = await navigator.serviceWorker.ready;
	const sub =
		(await reg.pushManager.getSubscription()) ??
		(await reg.pushManager.subscribe({
			userVisibleOnly: true,
			applicationServerKey: keyBytes(chiave)
		}));
	await savePush(sub.toJSON());
	return 'attive';
}

export async function disablePush(): Promise<PushState> {
	const reg = await navigator.serviceWorker.getRegistration();
	const sub = await reg?.pushManager.getSubscription();
	if (sub) {
		await removePush(sub.endpoint).catch(() => undefined);
		await sub.unsubscribe();
	}
	return 'spente';
}
