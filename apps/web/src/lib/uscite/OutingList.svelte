<script lang="ts">
	// Elenco compatto di uscite (feed pubblico, proposte dei contatti): data come sul calendario,
	// titolo, ora e luogo del ritrovo, distanza, difficoltà e posti.
	import { resolve } from '$app/paths';
	import DateBadge from '../ui/DateBadge.svelte';
	import DiffPill from '../ui/DiffPill.svelte';
	import Icon from '../ui/Icon.svelte';
	import type { UscitaInElenco } from './api';

	let {
		uscite,
		distance
	}: { uscite: UscitaInElenco[]; distance?: (u: UscitaInElenco) => number | null } = $props();

	function where(u: UscitaInElenco): string {
		const time = new Intl.DateTimeFormat('it-IT', {
			timeZone: 'Europe/Rome',
			hour: '2-digit',
			minute: '2-digit'
		}).format(new Date(u.ritrovo_quando));
		const km = distance?.(u) ?? null;
		const far =
			km == null ? '' : ` · a ${km < 10 ? km.toFixed(1).replace('.', ',') : Math.round(km)} km`;
		return `ore ${time} · ${u.ritrovo_luogo}${far}`;
	}

	function seats(u: UscitaInElenco): string {
		const s = `${u.confermati} ${u.confermati === 1 ? 'confermato' : 'confermati'}`;
		return u.posti ? `${s} su ${u.posti}` : s;
	}
</script>

<ul class="elenco">
	{#each uscite as u (u.id)}
		<li>
			<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso da resolve() con parametri -->
			<a href={`${resolve('/uscita')}?id=${encodeURIComponent(u.id)}`}>
				<DateBadge iso={u.ritrovo_quando} />
				<span class="testo">
					<b>{u.titolo}</b>
					<small>{where(u)}</small>
					<span class="dati">
						{#if u.stato === 'rinviata'}<span class="rinviata">rinviata</span>{/if}
						<DiffPill code={u.difficolta} />
						<small>{seats(u)}</small>
					</span>
				</span>
				<span class="vai"><Icon name="freccia" size={18} /></span>
			</a>
		</li>
	{/each}
</ul>

<style>
	.elenco {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.6rem;
	}
	a {
		display: flex;
		gap: 0.8rem;
		align-items: center;
		padding: 0.75rem;
		border-radius: var(--r-md);
		background: var(--surface);
		border: 1px solid var(--border);
		color: var(--text);
		text-decoration: none;
	}
	.testo {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-width: 0;
		flex: 1;
	}
	b {
		font: 600 1rem/1.25 var(--font-body);
	}
	small {
		color: var(--muted);
		font-size: 0.82rem;
	}
	.dati {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.2rem;
	}
	.rinviata {
		font: 600 0.72rem var(--font-body);
		color: var(--rust);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.vai {
		color: var(--muted);
	}
</style>
