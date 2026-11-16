import { error } from '@sveltejs/kit';
import { generatedAsset } from '#lib/data/paths.ts';
import type { ItineraryDoc } from '#lib/data/types.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	const res = await fetch(generatedAsset(`data/itinerari/${params.slug}.json`));
	if (!res.ok) error(404, `Itinerario ${params.slug} non trovato`);
	return { itinerary: (await res.json()) as ItineraryDoc };
};
