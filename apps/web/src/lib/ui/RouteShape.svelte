<script lang="ts">
	// Miniatura della forma del giro (dall'indice di Esplora): linea, partenza e arrivo, su un
	// fondo a isoipse. Solo per riconoscere il giro a colpo d'occhio, non per orientarsi.
	let {
		line,
		width = 74,
		height = 74,
		stroke = 2.4,
		dashed = false
	}: {
		line: [number, number][] | number[][];
		width?: number;
		height?: number;
		stroke?: number;
		dashed?: boolean;
	} = $props();

	const shape = $derived.by(() => {
		if (!line || line.length < 2) return null;
		const lat0 = line.reduce((s, p) => s + p[1], 0) / line.length;
		const kx = Math.cos((lat0 * Math.PI) / 180); // gradi di longitudine più corti in quota
		const xs = line.map((p) => p[0] * kx);
		const ys = line.map((p) => p[1]);
		const [mnx, mxx, mny, mxy] = [
			Math.min(...xs),
			Math.max(...xs),
			Math.min(...ys),
			Math.max(...ys)
		];
		const pad = Math.max(8, Math.min(width, height) * 0.14);
		const k = Math.min(
			(width - 2 * pad) / (mxx - mnx || 1e-6),
			(height - 2 * pad) / (mxy - mny || 1e-6)
		);
		const ox = (width - (mxx - mnx) * k) / 2;
		const oy = (height - (mxy - mny) * k) / 2;
		const pts = xs.map((x, i) => [ox + (x - mnx) * k, height - oy - (ys[i] - mny) * k]);
		return {
			d: pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(''),
			a: pts[0],
			b: pts[pts.length - 1]
		};
	});
	const contours = $derived(
		Array.from({ length: Math.ceil(height / 16) + 1 }, (_, i) => {
			const y = 10 + i * 16;
			return `M-10 ${y} C ${width * 0.3} ${y - 9}, ${width * 0.62} ${y + 13}, ${width + 10} ${y - 3}`;
		})
	);
</script>

<svg viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
	{#each contours as d (d)}<path {d} class="iso" />{/each}
	{#if shape}
		<path
			d={shape.d}
			class="route"
			stroke-width={stroke}
			stroke-dasharray={dashed ? '5 4' : undefined}
		/>
		<circle cx={shape.a[0]} cy={shape.a[1]} r={stroke + 1.6} class="start" />
		<circle cx={shape.b[0]} cy={shape.b[1]} r={stroke + 0.6} class="end" />
	{/if}
</svg>

<style>
	svg {
		display: block;
		width: 100%;
		height: 100%;
		background: var(--brand-soft);
	}
	.iso {
		fill: none;
		stroke: var(--accent);
		stroke-opacity: 0.12;
		stroke-width: 1.2;
	}
	.route {
		fill: none;
		stroke: var(--accent);
		stroke-linejoin: round;
		stroke-linecap: round;
	}
	.start {
		fill: var(--surface);
		stroke: var(--accent);
		stroke-width: 2.4;
	}
	.end {
		fill: var(--accent);
	}
</style>
