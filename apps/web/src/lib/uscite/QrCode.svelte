<script lang="ts">
	// Codice QR del link d'invito, disegnato in SVG nel browser (nessun servizio esterno).
	import { encode } from 'uqr';

	let { text, label }: { text: string; label: string } = $props();

	const qr = $derived(encode(text, { ecc: 'M', border: 2 }));
	// un rettangolo per ogni tratto orizzontale di moduli scuri
	const path = $derived.by(() => {
		let d = '';
		qr.data.forEach((row, y) => {
			let x = 0;
			while (x < row.length) {
				if (!row[x]) {
					x += 1;
					continue;
				}
				const start = x;
				while (x < row.length && row[x]) x += 1;
				d += `M${start} ${y}h${x - start}v1h${start - x}z`;
			}
		});
		return d;
	});
</script>

<svg
	viewBox={`0 0 ${qr.size} ${qr.size}`}
	role="img"
	aria-label={label}
	shape-rendering="crispEdges"
	xmlns="http://www.w3.org/2000/svg"
>
	<rect width={qr.size} height={qr.size} fill="#fff" />
	<path d={path} fill="#000" />
</svg>

<style>
	svg {
		display: block;
		width: min(16rem, 100%);
		height: auto;
		background: #fff;
	}
</style>
