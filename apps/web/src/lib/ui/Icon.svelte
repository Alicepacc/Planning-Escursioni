<script module lang="ts">
	// Icone dell'interfaccia (disegnate per Cordata, tratto 2 px su griglia 24): niente librerie.
	type Shape = { d: string } | { c: [number, number, number] };
	const ICONS = {
		scopri: [{ d: 'M3 19 9.5 8l3.5 5.5 2-3L21 19Z' }, { c: [17, 5.5, 1.6] }],
		mappa: [{ d: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Z' }, { d: 'M9 4v14M15 6v14' }],
		pianifica: [
			{ c: [6, 18, 2.2] },
			{ c: [18, 6, 2.2] },
			{ d: 'M8 18h7a3.5 3.5 0 0 0 0-7H9a3.5 3.5 0 0 1 0-7h7' }
		],
		uscite: [
			{ c: [9, 8, 3.2] },
			{ d: 'M3.5 19a5.5 5.5 0 0 1 11 0' },
			{ c: [17, 9, 2.6] },
			{ d: 'M15.5 14.2A4.6 4.6 0 0 1 21 18.5' }
		],
		cerca: [{ c: [11, 11, 7] }, { d: 'm20 20-3.6-3.6' }],
		filtri: [{ d: 'M4 7h10M18 7h2M4 17h4M12 17h8' }, { c: [16, 7, 2] }, { c: [10, 17, 2] }],
		distanza: [{ d: 'M4 12h16M7 8l-4 4 4 4M17 8l4 4-4 4' }],
		salita: [{ d: 'M3 18 9 9l4 5 3-4 5 8' }],
		tempo: [{ c: [12, 12, 8.5] }, { d: 'M12 7.5V12l3 2' }],
		affidabile: [
			{ d: 'M12 3 4.5 6v5.5c0 4.3 3.1 8 7.5 9.5 4.4-1.5 7.5-5.2 7.5-9.5V6L12 3Z' },
			{ d: 'm8.6 12.2 2.4 2.4 4.6-4.8' }
		],
		indietro: [{ d: 'm15 5-7 7 7 7' }],
		condividi: [{ d: 'M12 3v12M7.5 7.5 12 3l4.5 4.5M6 11H5v9h14v-9h-1' }],
		salva: [{ d: 'M6 3.5h12v17l-6-4-6 4Z' }],
		posizione: [
			{ d: 'M12 21s7-6.2 7-11.5a7 7 0 0 0-14 0C5 14.8 12 21 12 21Z' },
			{ c: [12, 9.5, 2.4] }
		],
		locandina: [{ d: 'M6 3h8l4 4v14H6Z' }, { d: 'M14 3v4h4M9 12h6M9 16h6' }],
		calendario: [{ d: 'M4 6h16v14H4Z' }, { d: 'M4 10h16M8 3v4M16 3v4' }],
		freccia: [{ d: 'm9 5 7 7-7 7' }],
		chiudi: [{ d: 'M6 6l12 12M18 6 6 18' }]
	} satisfies Record<string, Shape[]>;
	export type IconName = keyof typeof ICONS;
	export const iconShapes = (name: IconName): Shape[] => ICONS[name];
</script>

<script lang="ts">
	let {
		name,
		size = 24,
		label,
		stroke = 2
	}: { name: IconName; size?: number; label?: string; stroke?: number } = $props();
</script>

<svg
	viewBox="0 0 24 24"
	width={size}
	height={size}
	fill="none"
	stroke="currentColor"
	stroke-width={stroke}
	stroke-linecap="round"
	stroke-linejoin="round"
	role={label ? 'img' : undefined}
	aria-label={label}
	aria-hidden={label ? undefined : 'true'}
>
	{#each iconShapes(name) as s, i (i)}
		{#if 'd' in s}<path d={s.d} />{:else}<circle cx={s.c[0]} cy={s.c[1]} r={s.c[2]} />{/if}
	{/each}
</svg>

<style>
	svg {
		display: block;
		flex: none;
	}
</style>
