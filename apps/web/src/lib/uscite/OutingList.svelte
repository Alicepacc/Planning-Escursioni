<script lang="ts">
	// Elenco compatto di uscite (feed pubblico, proposte dei contatti).
	import { resolve } from '$app/paths';
	import type { UscitaInElenco } from './api';
	import { formatWhen } from './local';

	let {
		uscite,
		distance
	}: { uscite: UscitaInElenco[]; distance?: (u: UscitaInElenco) => number | null } = $props();

	function where(u: UscitaInElenco): string {
		const km = distance?.(u) ?? null;
		const far =
			km == null ? '' : ` · a ${km < 10 ? km.toFixed(1).replace('.', ',') : Math.round(km)} km`;
		return `${formatWhen(u.ritrovo_quando)} · ${u.ritrovo_luogo}${far}`;
	}

	function details(u: UscitaInElenco): string {
		const seats = `${u.confermati} ${u.confermati === 1 ? 'confermato' : 'confermati'}${u.posti ? ` su ${u.posti}` : ''}`;
		return [u.stato === 'rinviata' ? 'rinviata' : null, u.difficolta, seats]
			.filter(Boolean)
			.join(' · ');
	}
</script>

<ul class="elenco">
	{#each uscite as u (u.id)}
		<li>
			<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso da resolve() con parametri -->
			<a href={`${resolve('/uscita')}?id=${encodeURIComponent(u.id)}`}>{u.titolo}</a>
			<span class="nota">{where(u)}</span>
			<span class="nota">{details(u)}</span>
		</li>
	{/each}
</ul>

<style>
	.elenco {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.elenco li {
		display: flex;
		flex-direction: column;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--border);
	}
	.elenco a {
		font-weight: 600;
		min-height: 32px;
		display: inline-flex;
		align-items: center;
	}
	.nota {
		color: var(--muted);
	}
</style>
