<script lang="ts">
	// Difficoltà CAI come pillola: sempre la sigla (mai solo il colore), colori come le piste.
	import { scaleInfo } from '../hiking/difficulty';

	let { code, label = false }: { code: string | null | undefined; label?: boolean } = $props();
	const info = $derived(scaleInfo(code));
</script>

{#if info}
	<span class="pill" style="--c:{info.color}" title="{info.code} – {info.label}: {info.description}"
		>{info.code}</span
	>{#if label}<span class="nome">{info.label}</span>{/if}
{/if}

<style>
	.pill {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 1.9rem;
		height: 1.4rem;
		padding: 0 0.45rem;
		border-radius: 7px;
		background: var(--c);
		color: #fff;
		font: 700 0.75rem/1 var(--font-body);
		box-shadow: inset 0 0 0 1px rgb(255 255 255 / 12%);
	}
	.nome {
		display: inline-flex;
		align-items: center;
		height: 1.6rem;
		padding: 0 0.55rem;
		border-radius: 8px;
		background: var(--chip);
		font: 600 0.8rem var(--font-body);
		margin-left: 0.35rem;
	}
</style>
