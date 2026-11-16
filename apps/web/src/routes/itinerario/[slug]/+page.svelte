<script lang="ts">
	// Scheda di un itinerario (oggi la fixture Val d'Inferno): stesso componente delle attività.
	import ItineraryView from '#lib/components/ItineraryView.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<ItineraryView doc={data.itinerary} />
