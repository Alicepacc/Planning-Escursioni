<script lang="ts">
	// Notifiche delle uscite: iscrizioni, liste d'attesa, annullamenti, rinvii, promemoria.
	import { onMount } from 'svelte';
	import { disablePush, enablePush, needsInstallOnIos, pushState, type PushState } from './push';

	let stato = $state<PushState | null>(null);
	let busy = $state(false);
	let error = $state('');
	const ios = needsInstallOnIos();

	onMount(async () => {
		stato = await pushState();
	});

	async function toggle() {
		busy = true;
		error = '';
		try {
			stato = stato === 'attive' ? await disablePush() : await enablePush();
		} catch (e) {
			error =
				(e as Error).message === 'Notifiche non ancora attive.'
					? 'Le notifiche non sono ancora attive su questo servizio.'
					: 'Non è stato possibile attivare le notifiche su questo browser (nelle finestre private di Chrome non sono disponibili).';
		} finally {
			busy = false;
		}
	}
</script>

<div class="notifiche">
	{#if ios}
		<p class="nota">
			Su iPhone e iPad le notifiche arrivano solo dopo aver aggiunto Cordata alla schermata Home
			(Condividi → «Aggiungi a Home»).
		</p>
	{:else if stato === 'non-supportate'}
		<p class="nota">Questo browser non riceve notifiche: ricontrolla la pagina dell’uscita.</p>
	{:else if stato === 'negate'}
		<p class="nota">
			Le notifiche sono bloccate per questo sito: si riattivano dalle impostazioni del browser.
		</p>
	{:else if stato}
		<button type="button" class="secondario" disabled={busy} onclick={toggle}
			>{stato === 'attive' ? 'Disattiva le notifiche' : 'Attiva le notifiche'}</button
		>
		<span class="nota"
			>{stato === 'attive'
				? 'Riceverai avvisi su iscrizioni, lista d’attesa, annullamenti, rinvii e il promemoria della sera prima.'
				: 'Per sapere se un posto si libera, se l’uscita cambia e per il promemoria della sera prima.'}</span
		>
	{/if}
	{#if error}<p class="errore" role="alert">{error}</p>{/if}
</div>

<style>
	.notifiche {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
		margin: 0.6rem 0;
	}
	button {
		min-height: 44px;
		padding: 0 1rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.nota {
		color: var(--muted);
		font-size: 0.9rem;
	}
	.errore {
		color: #b42318;
	}
</style>
