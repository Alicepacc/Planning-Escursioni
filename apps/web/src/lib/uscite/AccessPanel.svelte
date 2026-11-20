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
	<span class="chiave" aria-hidden="true">
		<svg viewBox="0 0 24 24" width="26" height="26"
			><circle cx="8" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2" /><path
				d="M12 12h9m-3 0v3m-3-3v2"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
			/></svg
		>
	</span>
	<h2 id="accesso-titolo">Accedi</h2>
	<p class="perche">{why}</p>
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
		margin-top: 0.9rem;
		border: 1px solid var(--border);
		border-radius: var(--r-lg);
		padding: 1.1rem;
		background: var(--surface);
		box-shadow: var(--shadow);
	}
	.chiave {
		display: grid;
		place-items: center;
		width: 2.8rem;
		height: 2.8rem;
		border-radius: 12px;
		background: var(--brand-soft);
		color: var(--accent);
	}
	h2 {
		margin: 0.6rem 0 0.2rem;
		font-size: 1.3rem;
	}
	.perche {
		margin: 0 0 0.4rem;
		font-weight: 500;
	}
	.nota {
		margin: 0;
		color: var(--muted);
		font-size: 0.88rem;
	}
	.azioni {
		display: grid;
		gap: 0.5rem;
		margin-top: 0.9rem;
	}
	form {
		display: grid;
		gap: 0.5rem;
		margin-top: 0.9rem;
	}
	form label {
		font-size: 0.9rem;
		font-weight: 500;
	}
	input {
		width: 100%;
		padding: 0 0.75rem;
	}
	button {
		min-height: 48px;
		padding: 0 1rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: var(--accent);
		color: var(--on-accent);
		font: 600 1rem var(--font-body);
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
