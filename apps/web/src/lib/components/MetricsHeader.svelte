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
	.metriche {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.5rem;
		margin: 0;
	}
	.metriche > div {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 0.5rem 0.6rem;
		min-width: 0;
	}
	dt {
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
	}
	dd {
		margin: 0.15rem 0 0;
		font-size: 1.15rem;
		font-weight: 700;
		display: flex;
		flex-wrap: wrap;
		gap: 0 0.5rem;
	}
	.nota {
		font-size: 0.72rem;
		color: var(--muted);
	}
	.fonte {
		margin: 0.35rem 0 0;
		font-size: 0.8rem;
		color: var(--muted);
	}
	@media (max-width: 420px) {
		.metriche {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
