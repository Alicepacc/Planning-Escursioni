<script lang="ts">
	// Affidabilità della traccia (ADR 0015). Finché il punteggio non è nell'indice si usa lo stato
	// della verifica: verificata, da verificare, senza traccia.
	import Icon from './Icon.svelte';

	let {
		ok = false,
		noTrack = false,
		score = null,
		long = false
	}: { ok?: boolean; noTrack?: boolean; score?: number | null; long?: boolean } = $props();
</script>

{#if noTrack}
	<span class="trust muted">Senza traccia</span>
{:else if score != null && score >= 80}
	<span class="trust ok" title="Affidabilità della traccia: {score} su 100"
		><Icon name="affidabile" size={14} stroke={2.4} />{long
			? `Traccia affidabile al ${score}%`
			: `Traccia ${score}%`}</span
	>
{:else if ok}
	<span class="trust ok"
		><Icon name="affidabile" size={14} stroke={2.4} />{long
			? 'Traccia verificata'
			: 'Verificata'}</span
	>
{:else}
	<span class="trust muted">Da verificare</span>
{/if}

<style>
	.trust {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		height: 1.4rem;
		padding: 0 0.45rem;
		border-radius: 7px;
		font: 600 0.75rem var(--font-body);
		white-space: nowrap;
	}
	.ok {
		color: var(--ok);
		background: color-mix(in srgb, var(--ok) 14%, transparent);
	}
	.muted {
		color: var(--muted);
		background: var(--chip);
	}
</style>
