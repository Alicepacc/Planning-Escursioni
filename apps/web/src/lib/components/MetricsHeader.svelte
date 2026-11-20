<script lang="ts">
	// Le 4 metriche chiave nell'ordine della locandina CAI: tempo · difficoltà · km · D+/D−.
	import DifficultyBadge from './DifficultyBadge.svelte';
	import { formatDuration, formatKm, formatMeters } from '../hiking/format';

	interface Props {
		minutes: number | null;
		minutesNote?: string;
		difficulty: string | null;
		km: number | null;
		up: number | null;
		down: number | null;
		source?: string;
	}
	let {
		minutes,
		minutesNote = 'tempo netto, senza soste',
		difficulty,
		km,
		up,
		down,
		source
	}: Props = $props();
</script>

<dl class="metriche">
	<div>
		<dt>Tempo</dt>
		<dd>{formatDuration(minutes)}</dd>
		<span class="nota">{minutesNote}</span>
	</div>
	<div>
		<dt>Difficoltà</dt>
		<dd><DifficultyBadge code={difficulty} size="large" /></dd>
	</div>
	<div>
		<dt>Lunghezza</dt>
		<dd>{formatKm(km)}</dd>
	</div>
	<div>
		<dt>Dislivello</dt>
		<dd>
			<span aria-label="salita">↗ {formatMeters(up)}</span>
			<span aria-label="discesa">↘ {formatMeters(down)}</span>
		</dd>
	</div>
</dl>
{#if source}<p class="fonte">{source}</p>{/if}

<style>
	/* una sola scheda con quattro colonne: numeri grandi, etichette piccole (ADR 0015) */
	.metriche {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		margin: 0;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--r-md, 14px);
		padding: 0.7rem 0.2rem;
	}
	.metriche > div {
		min-width: 0;
		padding: 0 0.5rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		border-right: 1px solid var(--border);
	}
	.metriche > div:last-child {
		border-right: 0;
	}
	dt {
		order: 2;
		font-size: 0.72rem;
		color: var(--muted);
	}
	dd {
		order: 1;
		margin: 0;
		font: 600 1.15rem/1.15 var(--font-display, serif);
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0 0.35rem;
	}
	.nota {
		order: 3;
		font-size: 0.66rem;
		color: var(--muted);
		line-height: 1.2;
	}
	.fonte {
		margin: 0.4rem 0 0;
		font-size: 0.78rem;
		color: var(--muted);
	}
	/* sul telefono due per riga: i numeri restano su una riga */
	@media (max-width: 480px) {
		.metriche {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			row-gap: 0.8rem;
		}
		.metriche > div:nth-child(2n) {
			border-right: 0;
		}
	}
	dd :global(span) {
		white-space: nowrap;
	}
</style>
