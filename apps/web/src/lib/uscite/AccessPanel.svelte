<script lang="ts">
	// Accesso con passkey (ADR 0014): niente email né password.
	import { login, register, type Utente } from './api';

	interface Props {
		onlogin: (u: Utente) => void;
		/** perché serve accedere, mostrato sopra i pulsanti */
		why?: string;
	}
	let { onlogin, why = 'Per partecipare o organizzare serve un account.' }: Props = $props();

	let nome = $state('');
	let busy = $state(false);
	let error = $state('');
	let creating = $state(false);

	async function run(action: () => Promise<Utente>) {
		busy = true;
		error = '';
		try {
			onlogin(await action());
		} catch (e) {
			const err = e as Error;
			error =
				err.name === 'NotAllowedError'
					? 'Operazione annullata o non consentita dal dispositivo.'
					: err.message || 'Non è stato possibile completare l’accesso.';
		} finally {
			busy = false;
		}
	}
</script>

<section class="accesso" aria-labelledby="accesso-titolo">
	<h2 id="accesso-titolo">Accedi</h2>
	<p>{why}</p>
	<p class="nota">
		Si usa una <strong>passkey</strong>: la crea il tuo dispositivo e la sblocchi con impronta,
		volto o PIN. Niente email né password. Se perdi tutti i dispositivi con la passkey, l’account
		non si può recuperare.
	</p>
	<div class="azioni">
		<button type="button" disabled={busy} onclick={() => run(login)}
			>Ho già una passkey: accedi</button
		>
		<button type="button" class="secondario" disabled={busy} onclick={() => (creating = !creating)}
			>Crea un account</button
		>
	</div>
	{#if creating}
		<form
			onsubmit={(e) => {
				e.preventDefault();
				run(() => register(nome));
			}}
		>
			<label for="nome-account">Come ti chiami? (lo vedrà chi organizza le uscite)</label>
			<input
				id="nome-account"
				bind:value={nome}
				minlength="2"
				maxlength="40"
				required
				autocomplete="nickname"
			/>
			<button type="submit" disabled={busy || nome.trim().length < 2}>Crea la passkey</button>
		</form>
	{/if}
	{#if error}<p class="errore" role="alert">{error}</p>{/if}
</section>

<style>
	.accesso {
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 0.8rem 1rem;
		background: var(--surface);
	}
	h2 {
		margin: 0 0 0.3rem;
		font-size: 1.1rem;
	}
	.nota {
		color: var(--muted);
		font-size: 0.9rem;
	}
	.azioni,
	form {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
		margin-top: 0.5rem;
	}
	form label {
		flex-basis: 100%;
	}
	input {
		flex: 1;
		min-width: 12rem;
		min-height: 44px;
		padding: 0 0.6rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		font: inherit;
	}
	button {
		min-height: 44px;
		padding: 0 1rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: var(--accent);
		color: var(--on-accent);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	button.secondario {
		background: transparent;
		color: var(--accent);
	}
	button:disabled {
		opacity: 0.6;
	}
	.errore {
		color: #b42318;
	}
</style>
