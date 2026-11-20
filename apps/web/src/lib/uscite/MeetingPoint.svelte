<script lang="ts">
	// Punto di ritrovo sulla mappa (SPEC §5.4): si tocca la mappa o si usa la propria posizione.
	// Serve per le uscite pubbliche, che compaiono nell'elenco delle uscite vicine.
	import type { Map as MlMap } from 'maplibre-gl';
	import MapView from '#lib/map/MapView.svelte';

	let { point = $bindable() }: { point: [number, number] | null } = $props();

	let locating = $state(false);
	let geoError = $state('');
	// riquadro iniziale: intorno al punto già scelto (per esempio la partenza dell'itinerario)
	const initial = point
		? ([point[0] - 0.05, point[1] - 0.03, point[0] + 0.05, point[1] + 0.03] as [
				number,
				number,
				number,
				number
			])
		: undefined;
	let focus = $state<[number, number, number, number] | null>(null);

	// 5 decimali: circa un metro, più che sufficiente per un parcheggio
	const round = (v: number) => Math.round(v * 1e5) / 1e5;

	function onReady(map: MlMap) {
		map.on('click', (e) => {
			point = [round(e.lngLat.lng), round(e.lngLat.lat)];
		});
	}

	function locate() {
		if (!navigator.geolocation) {
			geoError = 'Posizione non disponibile su questo dispositivo.';
			return;
		}
		locating = true;
		geoError = '';
		navigator.geolocation.getCurrentPosition(
			(pos) => {
				locating = false;
				const p: [number, number] = [round(pos.coords.longitude), round(pos.coords.latitude)];
				point = p;
				focus = [p[0] - 0.02, p[1] - 0.012, p[0] + 0.02, p[1] + 0.012];
			},
			() => {
				locating = false;
				geoError = 'Non riesco a leggere la posizione (permesso negato o segnale assente).';
			},
			{ enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
		);
	}
</script>

<div class="riquadro">
	<MapView
		bbox={initial}
		cursor={point}
		{focus}
		{onReady}
		label="Mappa per scegliere il punto di ritrovo: tocca dove vi trovate"
	/>
</div>
<div class="azioni">
	<button type="button" class="link" onclick={locate} disabled={locating}
		>{locating ? 'Cerco la posizione…' : 'Usa la mia posizione'}</button
	>
	{#if point}
		<button type="button" class="link" onclick={() => (point = null)}>Togli il punto</button>
	{/if}
</div>
<p class="nota" aria-live="polite">
	{point
		? `Punto di ritrovo: ${point[1].toFixed(5)}, ${point[0].toFixed(5)}. Tocca la mappa per spostarlo.`
		: 'Nessun punto: tocca la mappa dove vi trovate.'}
</p>
{#if geoError}<p class="errore" role="alert">{geoError}</p>{/if}

<style>
	.riquadro {
		position: relative;
		height: 16rem;
		border-radius: 8px;
		overflow: hidden;
		border: 1px solid var(--border);
	}
	.azioni {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.link {
		background: none;
		border: none;
		padding: 0;
		min-height: 44px;
		color: var(--accent);
		text-decoration: underline;
		font: inherit;
		cursor: pointer;
	}
	.nota {
		color: var(--muted);
		margin: 0;
	}
	.errore {
		color: #b42318;
	}
</style>
