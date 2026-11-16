<script lang="ts">
	// Badge della scala CAI: lettere + colore + descrizione (mai solo colore).
	import { scaleInfo } from '../hiking/difficulty';

	interface Props {
		code: string | null | undefined;
		size?: 'normal' | 'large';
		showLabel?: boolean;
	}
	let { code, size = 'normal', showLabel = false }: Props = $props();
	const info = $derived(scaleInfo(code));
</script>

{#if info}
	<span
		class="badge {size}"
		style="--c:{info.color}"
		title="{info.code} – {info.label}: {info.description}"
	>
		<span class="codice">{info.code}</span>
		{#if showLabel}<span class="nome">{info.label}</span>{/if}
	</span>
{:else}
	<span class="badge sconosciuta {size}" title="Difficoltà non indicata">?</span>
{/if}

<style>
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		background: var(--c, #666);
		color: #fff;
		border-radius: 6px;
		padding: 0.1rem 0.5rem;
		font-weight: 700;
		line-height: 1.5;
		white-space: nowrap;
	}
	.large {
		font-size: 1.2rem;
		padding: 0.2rem 0.65rem;
	}
	.nome {
		font-weight: 600;
		font-size: 0.85em;
	}
	.sconosciuta {
		background: #8a8f94;
	}
</style>
