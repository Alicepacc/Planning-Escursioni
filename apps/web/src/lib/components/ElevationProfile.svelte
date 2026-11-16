<script lang="ts">
	// Profilo altimetrico interattivo (SPEC §5.2, §9.4): scorrendo, `index` cambia e la mappa
	// sposta il marker. Tratti colorati per pendenza, punti chiave numerati.
	import type { ProfilePoint } from '../data/types';
	import { formatDuration, formatKm, formatMeters } from '../hiking/format';

	interface Props {
		points: ProfilePoint[];
		stages?: { n: number; name: string; dist_km: number }[];
		index?: number | null;
		height?: number;
	}

	let { points, stages = [], index = $bindable(null), height = 190 }: Props = $props();

	let width = $state(640);
	const pad = { top: 18, right: 12, bottom: 26, left: 46 };

	const SLOPE_CLASSES = [
		{ max: 8, color: '#5f8f6b', label: 'fino all’8%' },
		{ max: 15, color: '#d9a21b', label: '8-15%' },
		{ max: 25, color: '#e0662a', label: '15-25%' },
		{ max: Infinity, color: '#b3261e', label: 'oltre 25%' }
	];

	const totalM = $derived(points.length ? points[points.length - 1][0] : 0);
	const eles = $derived(points.map((p) => p[1]));
	const minEle = $derived(Math.floor((Math.min(...eles) - 20) / 100) * 100);
	const maxEle = $derived(Math.ceil((Math.max(...eles) + 20) / 100) * 100);
	const innerW = $derived(Math.max(10, width - pad.left - pad.right));
	const innerH = $derived(height - pad.top - pad.bottom);
	const x = (d: number) => pad.left + (totalM ? (d / totalM) * innerW : 0);
	const y = (e: number) => pad.top + innerH - ((e - minEle) / (maxEle - minEle || 1)) * innerH;

	const areaPath = $derived.by(() => {
		if (!points.length) return '';
		const top = points.map((p, i) => `${i ? 'L' : 'M'}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`);
		return `${top.join('')}L${x(totalM).toFixed(1)},${pad.top + innerH}L${pad.left},${pad.top + innerH}Z`;
	});

	// pendenza media su ~100 m per colorare la linea
	const slopeSegments = $derived.by(() => {
		const byClass = SLOPE_CLASSES.map(() => [] as string[]);
		let j = 0;
		for (let i = 1; i < points.length; i++) {
			while (j < i && points[i][0] - points[j][0] > 100) j++;
			const k = Math.max(0, Math.min(j, i - 1));
			const span = points[i][0] - points[k][0];
			const slope = span > 0 ? (Math.abs(points[i][1] - points[k][1]) / span) * 100 : 0;
			const c = SLOPE_CLASSES.findIndex((s) => slope <= s.max);
			const a = points[i - 1];
			const b = points[i];
			byClass[c].push(
				`M${x(a[0]).toFixed(1)},${y(a[1]).toFixed(1)}L${x(b[0]).toFixed(1)},${y(b[1]).toFixed(1)}`
			);
		}
		return byClass.map((segs, c) => ({ color: SLOPE_CLASSES[c].color, d: segs.join('') }));
	});

	const xTicks = $derived.by(() => {
		const km = totalM / 1000;
		const step = km <= 3 ? 0.5 : km <= 8 ? 1 : km <= 20 ? 2 : 5;
		const out: number[] = [];
		for (let v = 0; v <= km + 1e-9; v += step) out.push(Math.round(v * 10) / 10);
		return out;
	});

	const yTicks = $derived.by(() => {
		const span = maxEle - minEle;
		const step = span <= 300 ? 50 : span <= 800 ? 100 : span <= 1600 ? 200 : 500;
		const out: number[] = [];
		for (let v = Math.ceil(minEle / step) * step; v <= maxEle; v += step) out.push(v);
		return out;
	});

	const current = $derived(index != null && points[index] ? points[index] : null);

	function nearestIndex(distM: number): number {
		let lo = 0;
		let hi = points.length - 1;
		while (hi - lo > 1) {
			const mid = (lo + hi) >> 1;
			if (points[mid][0] < distM) lo = mid;
			else hi = mid;
		}
		return distM - points[lo][0] < points[hi][0] - distM ? lo : hi;
	}

	function onPointer(event: PointerEvent) {
		const rect = (event.currentTarget as SVGElement).getBoundingClientRect();
		const px = event.clientX - rect.left;
		const ratio = Math.min(1, Math.max(0, (px - pad.left) / innerW));
		index = nearestIndex(ratio * totalM);
	}

	function onKey(event: KeyboardEvent) {
		if (!points.length) return;
		const stepM = totalM / 100;
		const here = current ? current[0] : 0;
		if (event.key === 'ArrowRight') index = nearestIndex(Math.min(totalM, here + stepM));
		else if (event.key === 'ArrowLeft') index = nearestIndex(Math.max(0, here - stepM));
		else if (event.key === 'Home') index = 0;
		else if (event.key === 'End') index = points.length - 1;
		else if (event.key === 'Escape') index = null;
		else return;
		event.preventDefault();
	}

	const summary = $derived(
		points.length
			? `Profilo altimetrico: ${formatKm(totalM / 1000)}, quota da ${formatMeters(Math.min(...eles))} a ${formatMeters(Math.max(...eles))}. Usa le frecce per scorrere.`
			: 'Profilo non disponibile'
	);
</script>

<figure class="profilo" bind:clientWidth={width}>
	<svg
		{width}
		{height}
		viewBox="0 0 {width} {height}"
		role="slider"
		tabindex="0"
		aria-label={summary}
		aria-valuemin={0}
		aria-valuemax={Math.round(totalM)}
		aria-valuenow={current ? Math.round(current[0]) : 0}
		aria-valuetext={current
			? `${formatKm(current[0] / 1000)}, ${formatMeters(current[1])}`
			: 'inizio'}
		onpointermove={onPointer}
		onpointerdown={onPointer}
		onpointerleave={(e) => e.pointerType === 'mouse' && (index = null)}
		onkeydown={onKey}
	>
		{#each yTicks as t (t)}
			<line class="griglia" x1={pad.left} x2={pad.left + innerW} y1={y(t)} y2={y(t)} />
			<text class="asse" x={pad.left - 6} y={y(t) + 4} text-anchor="end">{t}</text>
		{/each}
		{#each xTicks as t (t)}
			<text class="asse" x={x(t * 1000)} y={height - 8} text-anchor="middle">{t}</text>
		{/each}
		<text class="asse" x={pad.left + innerW} y={height - 8} text-anchor="end" dx="-2" opacity="0"
			>km</text
		>
		<path class="area" d={areaPath} />
		{#each slopeSegments as seg (seg.color)}
			<path d={seg.d} stroke={seg.color} stroke-width="3" fill="none" stroke-linecap="round" />
		{/each}
		{#each stages as s (s.n)}
			<g transform="translate({x(s.dist_km * 1000)},{pad.top - 8})">
				<line class="tappa-linea" y1="8" y2={innerH + 8} />
				<circle r="8" class="tappa" />
				<text class="tappa-n" y="4" text-anchor="middle">{s.n}</text>
			</g>
		{/each}
		{#if current}
			<line
				class="cursore"
				x1={x(current[0])}
				x2={x(current[0])}
				y1={pad.top}
				y2={pad.top + innerH}
			/>
			<circle cx={x(current[0])} cy={y(current[1])} r="5" class="punto" />
		{/if}
	</svg>
	<figcaption>
		{#if current}
			<strong>{formatKm(current[0] / 1000)}</strong> · {formatMeters(current[1])} · {formatDuration(
				current[4]
			)}
			dalla partenza (tempo netto)
		{:else}
			Scorri il profilo per seguire il percorso sulla mappa.
		{/if}
		<span class="legenda" aria-label="Legenda della pendenza">
			{#each SLOPE_CLASSES as s (s.label)}
				<span><i style="background:{s.color}"></i>{s.label}</span>
			{/each}
		</span>
	</figcaption>
</figure>

<style>
	.profilo {
		margin: 0;
		user-select: none;
	}
	svg {
		display: block;
		touch-action: pan-y;
		cursor: crosshair;
		border-radius: 8px;
	}
	svg:focus-visible {
		outline: 3px solid var(--accent);
		outline-offset: 2px;
	}
	.area {
		fill: color-mix(in srgb, var(--accent) 14%, transparent);
	}
	.griglia {
		stroke: var(--border);
		stroke-width: 1;
	}
	.asse {
		fill: var(--muted);
		font-size: 11px;
	}
	.cursore {
		stroke: var(--text);
		stroke-width: 1.5;
		stroke-dasharray: 3 3;
	}
	.punto {
		fill: #fff;
		stroke: var(--text);
		stroke-width: 3;
	}
	.tappa {
		fill: #1f2933;
		stroke: #fff;
		stroke-width: 1.5;
	}
	.tappa-linea {
		stroke: #1f2933;
		stroke-opacity: 0.25;
	}
	.tappa-n {
		fill: #fff;
		font-size: 10px;
		font-weight: 700;
	}
	figcaption {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.25rem 1rem;
		font-size: 0.9rem;
		color: var(--muted);
		padding: 0.25rem 0;
	}
	.legenda {
		display: inline-flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		font-size: 0.8rem;
	}
	.legenda i {
		display: inline-block;
		width: 14px;
		height: 4px;
		border-radius: 2px;
		margin-right: 4px;
		vertical-align: middle;
	}
</style>
