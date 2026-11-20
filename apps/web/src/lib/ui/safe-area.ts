// Altezza della tacca in alto (env(safe-area-inset-top)) in pixel, per i margini delle mappe:
// MapLibre vuole numeri, il CSS sa il valore vero. Zero fuori da iPhone o senza viewport-fit=cover.
export function safeAreaTop(): number {
	if (typeof document === 'undefined') return 0;
	const probe = document.createElement('div');
	probe.style.cssText = 'position:absolute;visibility:hidden;padding-top:env(safe-area-inset-top)';
	document.body.appendChild(probe);
	const value = parseFloat(getComputedStyle(probe).paddingTop) || 0;
	probe.remove();
	return value;
}
