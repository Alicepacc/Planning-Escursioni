import { error } from '@sveltejs/kit';
import { generatedAsset } from '#lib/data/paths.ts';
import type { TrailDoc } from '#lib/data/types.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	const res = await fetch(generatedAsset(`data/sentieri/${params.id}.json`));
	if (!res.ok) error(404, `Sentiero ${params.id} non trovato`);
	return { trail: (await res.json()) as TrailDoc };
};
