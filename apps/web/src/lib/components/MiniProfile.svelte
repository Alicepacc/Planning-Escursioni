<script lang="ts">
	// Mini-profilo altimetrico per le card di Esplora: 24 quote equidistanti.
	interface Props {
		values: number[];
		width?: number;
		height?: number;
	}
	let { values, width = 72, height = 22 }: Props = $props();

	const path = $derived.by(() => {
		if (values.length < 2) return '';
		const min = Math.min(...values);
		const range = Math.max(Math.max(...values) - min, 60);
		const step = width / (values.length - 1);
		const pts = values.map(
			(v, i) =>
				`${(i * step).toFixed(1)},${(height - 1 - ((v - min) / range) * (height - 3)).toFixed(1)}`
		);
		return `M0,${height} L${pts.join(' L')} L${width},${height} Z`;
	});
</script>

{#if path}
	<svg viewBox="0 0 {width} {height}" {width} {height} class="mini" aria-hidden="true">
		<path d={path} />
	</svg>
{/if}

<style>
	.mini path {
		fill: color-mix(in srgb, var(--accent) 22%, transparent);
		stroke: var(--accent);
		stroke-width: 1.2;
	}
</style>
