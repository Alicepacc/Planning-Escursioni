<script lang="ts">
	// Scheda di un'attività CAI dell'archivio (SPEC §5.2): link alla locandina, sintesi dai dati,
	// traccia ricostruita con l'esito della verifica.
	import ItineraryView from '#lib/components/ItineraryView.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<ItineraryView doc={data.activity} />
