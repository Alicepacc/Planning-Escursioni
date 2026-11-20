<script lang="ts">
	// Benvenuto al primo avvio (ADR 0015): tre schermate brevi, saltabili, mostrate una volta.
	import { onMount } from 'svelte';
	import Icon, { type IconName } from './Icon.svelte';

	const KEY = 'cordata.primo-avvio';
	let open = $state(false);
	let step = $state(0);

	const STEPS: { icon: IconName; title: string; text: string }[] = [
		{
			icon: 'scopri',
			title: 'Escursioni in Trentino-Alto Adige e Dolomiti',
			text: 'Le gite delle sezioni CAI e SAT, dalle loro locandine: itinerari di ogni anno e uscite in programma, con mappa, profilo e tempi.'
		},
		{
			icon: 'affidabile',
			title: 'Solo tracce affidabili',
			text: 'La traccia la ricostruiamo noi sui sentieri e la confrontiamo con la locandina: distanza, dislivello, quota. Pubblichiamo solo quelle che coincidono almeno all’80%, e la locandina originale è sempre a un tocco.'
		},
		{
			icon: 'uscite',
			title: 'Pianifica e organizza',
			text: 'Componi un giro sulla mappa, esporta il GPX, organizza un’uscita con gli amici e ricevi gli avvisi. La posizione e le notifiche le chiediamo solo quando servono.'
		}
	];

	onMount(() => {
		try {
			open = localStorage.getItem(KEY) !== 'visto';
		} catch {
			open = false; // senza spazio locale non lo si riproporrebbe a ogni pagina
		}
	});

	function close() {
		open = false;
		try {
			localStorage.setItem(KEY, 'visto');
		} catch {
			// spazio locale non disponibile
		}
	}
	function next() {
		if (step < STEPS.length - 1) step += 1;
		else close();
	}
</script>

{#if open}
	<div class="velo" role="presentation"></div>
	<div class="benvenuto" role="dialog" aria-modal="true" aria-labelledby="benvenuto-titolo">
		<button type="button" class="salta" onclick={close}>Salta</button>
		<div class="icona"><Icon name={STEPS[step].icon} size={44} stroke={1.8} /></div>
		<h2 id="benvenuto-titolo">{STEPS[step].title}</h2>
		<p>{STEPS[step].text}</p>
		<div class="punti" aria-hidden="true">
			{#each STEPS.keys() as i (i)}<span class:on={i === step}></span>{/each}
		</div>
		<button type="button" class="avanti" onclick={next}
			>{step < STEPS.length - 1 ? 'Avanti' : 'Inizia'}</button
		>
	</div>
{/if}

<style>
	.velo {
		position: fixed;
		inset: 0;
		z-index: 60;
		background: rgb(0 0 0 / 40%);
	}
	.benvenuto {
		position: fixed;
		left: 50%;
		bottom: calc(1rem + env(safe-area-inset-bottom));
		transform: translateX(-50%);
		z-index: 61;
		width: min(26rem, calc(100% - 2rem));
		box-sizing: border-box;
		padding: 1.6rem 1.4rem 1.2rem;
		border-radius: 24px;
		background: var(--surface);
		color: var(--text);
		box-shadow: 0 12px 40px rgb(0 0 0 / 25%);
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
	}
	.icona {
		display: grid;
		place-items: center;
		width: 76px;
		height: 76px;
		border-radius: 22px;
		background: var(--brand-soft);
		color: var(--accent);
		margin-bottom: 0.9rem;
	}
	h2 {
		font-size: 1.45rem;
		margin: 0 0 0.5rem;
	}
	p {
		margin: 0 0 1rem;
		color: var(--muted);
		line-height: 1.5;
	}
	.punti {
		display: flex;
		gap: 0.4rem;
		margin-bottom: 1rem;
	}
	.punti span {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--border);
	}
	.punti span.on {
		width: 22px;
		border-radius: 4px;
		background: var(--accent);
	}
	.avanti {
		width: 100%;
		min-height: 50px;
		border: 0;
		border-radius: 14px;
		background: var(--accent);
		color: var(--on-accent);
		font: 600 1rem var(--font-body);
		cursor: pointer;
	}
	.salta {
		position: absolute;
		top: 0.6rem;
		right: 0.8rem;
		min-height: 44px;
		border: 0;
		background: none;
		color: var(--muted);
		font: 500 0.9rem var(--font-body);
		cursor: pointer;
	}
</style>
