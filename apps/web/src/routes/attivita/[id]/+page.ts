import { error } from '@sveltejs/kit';
import { generatedAsset } from '#lib/data/paths.ts';
import type { ItineraryDoc } from '#lib/data/types.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	const res = await fetch(generatedAsset(`data/attivita/${params.id}.json`));
	if (!res.ok) error(404, `Attività ${params.id} non trovata`);
	return { activity: (await res.json()) as ItineraryDoc };
};
