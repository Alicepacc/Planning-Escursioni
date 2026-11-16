import { asset } from '$app/paths';

type AssetArg = Parameters<typeof asset>[0];

/**
 * URL di un file prodotto dalla pipeline di ingestion in `static/` (dati e tile). Questi file
 * non esistono al momento del type-check (sono generati e non versionati), quindi il percorso
 * non può essere verificato dal tipo di `asset()`.
 */
export function generatedAsset(path: string): string {
	return asset(path.replace(/^\//, '') as AssetArg);
}
