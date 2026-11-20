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
	<span class="campana" aria-hidden="true">
		<svg viewBox="0 0 24 24" width="22" height="22"
			><path
				d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15ZM10 20.5a2 2 0 0 0 4 0"
				fill="none"
				stroke="currentColor"
				stroke-width="1.9"
				stroke-linejoin="round"
			/></svg
		>
	</span>
	<div class="testo">
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
			<b>{stato === 'attive' ? 'Notifiche attive' : 'Notifiche'}</b>
			<span class="nota"
				>{stato === 'attive'
					? 'Iscrizioni, lista d’attesa, annullamenti, rinvii e il promemoria della sera prima.'
					: 'Per sapere se un posto si libera, se l’uscita cambia e per il promemoria della sera prima.'}</span
			>
			<button type="button" class:attivo={stato === 'attive'} disabled={busy} onclick={toggle}
				>{stato === 'attive' ? 'Disattiva le notifiche' : 'Attiva le notifiche'}</button
			>
		{/if}
		{#if error}<p class="errore" role="alert">{error}</p>{/if}
	</div>
</div>

<style>
	.notifiche {
		display: flex;
		gap: 0.75rem;
		align-items: flex-start;
		margin: 0.6rem 0;
		padding: 0.8rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--r-md);
	}
	.campana {
		flex: none;
		display: grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 12px;
		background: var(--brand-soft);
		color: var(--accent);
	}
	.testo {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.2rem;
		min-width: 0;
	}
	b {
		font-weight: 600;
	}
	button {
		margin-top: 0.4rem;
		min-height: 40px;
		padding: 0 1rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: var(--accent);
		color: var(--on-accent);
		font: 600 0.9rem var(--font-body);
		cursor: pointer;
	}
	button.attivo {
		background: transparent;
		color: var(--accent);
	}
	.nota {
		margin: 0;
		color: var(--muted);
		font-size: 0.85rem;
	}
	.errore {
		margin: 0;
		color: #b42318;
	}
</style>
