<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import AccessPanel from '#lib/uscite/AccessPanel.svelte';
	import { SERVICE_ON, createOuting, me, type Utente } from '#lib/uscite/api.ts';
	import { localToIso, rememberInvite } from '#lib/uscite/local.ts';

	let user = $state<Utente | null>(null);
	let ready = $state(false);
	let busy = $state(false);
	let error = $state('');

	// campi del modulo (precompilati dalla scheda o dal piano: ?titolo=…&da=…&difficolta=…)
	let titolo = $state('');
	let itinerario = $state('');
	let quando = $state('');
	let luogo = $state('');
	let mezzi = $state('auto condivise');
	let posti = $state<number | null>(8);
	let entro = $state('');
	let difficolta = $state('');
	let requisiti = $state('');
	let attrezzatura = $state('scarponi, giacca antivento, acqua, pranzo al sacco');
	let note = $state('');
	let visibilita = $state<'link' | 'pubblica'>('link');

	onMount(async () => {
		const q = new URL(location.href).searchParams;
		titolo = q.get('titolo') ?? '';
		itinerario = q.get('da') ?? '';
		difficolta = q.get('difficolta') ?? '';
		user = await me();
		ready = true;
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		try {
			const { id, invito } = await createOuting({
				titolo,
				itinerario: itinerario || undefined,
				ritrovo_quando: localToIso(quando),
				ritrovo_luogo: luogo,
				mezzi: mezzi || undefined,
				posti,
				iscrizioni_entro: localToIso(entro) ?? null,
				difficolta: difficolta || undefined,
				requisiti: requisiti || undefined,
				attrezzatura: attrezzatura
					.split(',')
					.map((a) => a.trim())
					.filter(Boolean),
				note: note || undefined,
				visibilita
			});
			rememberInvite(id, invito);
			const target = `${resolve('/uscita')}?id=${encodeURIComponent(id)}&t=${encodeURIComponent(invito)}`;
			// eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso da resolve() con parametri
			await goto(target);
		} catch (err) {
			error = (err as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>Organizza un’uscita – Cordata</title></svelte:head>

<div class="pagina">
	<h1>Organizza un’uscita</h1>
	<p class="avvertenza">
		Uscita <strong>privata tra persone</strong>, non organizzata dal CAI: nessuna copertura
		assicurativa CAI, ognuno partecipa sotto la propria responsabilità.
	</p>
	{#if !SERVICE_ON}
		<p class="nota" role="status">Il servizio delle uscite non è ancora attivo su questa demo.</p>
	{:else if !ready}
		<p class="nota">Caricamento…</p>
	{:else if !user}
		<AccessPanel why="Per organizzare un’uscita serve un account." onlogin={(u) => (user = u)} />
	{:else}
		<form onsubmit={submit}>
			<label>Titolo <input bind:value={titolo} required maxlength="120" /></label>
			<label>Ritrovo: data e ora <input type="datetime-local" bind:value={quando} required /></label
			>
			<label
				>Ritrovo: luogo <input
					bind:value={luogo}
					required
					maxlength="200"
					placeholder="es. parcheggio della funivia"
				/></label
			>
			<label
				>Mezzi <input
					bind:value={mezzi}
					maxlength="200"
					placeholder="auto condivise, treno…"
				/></label
			>
			<label
				>Posti (organizzatore compreso) <input
					type="number"
					min="1"
					max="200"
					bind:value={posti}
				/></label
			>
			<label>Iscrizioni entro <input type="datetime-local" bind:value={entro} /></label>
			<label
				>Difficoltà <input
					bind:value={difficolta}
					maxlength="20"
					placeholder="T, E, EE, EEA"
				/></label
			>
			<label
				>Requisiti <textarea
					bind:value={requisiti}
					maxlength="1000"
					placeholder="allenamento, assenza di vertigini…"></textarea></label
			>
			<label
				>Attrezzatura (separata da virgole) <input
					bind:value={attrezzatura}
					maxlength="800"
				/></label
			>
			<label>Note <textarea bind:value={note} maxlength="2000"></textarea></label>
			<fieldset>
				<legend>Chi può vederla</legend>
				<label class="scelta"
					><input type="radio" bind:group={visibilita} value="link" /> Solo chi ha il link</label
				>
				<label class="scelta"
					><input type="radio" bind:group={visibilita} value="pubblica" /> Pubblica (comparirà nell’elenco
					delle uscite vicine, in una fase successiva)</label
				>
			</fieldset>
			{#if itinerario}
				<p class="nota">Itinerario: {itinerario}</p>
			{/if}
			<button type="submit" disabled={busy}>Crea l’uscita e il link d’invito</button>
		</form>
	{/if}
	{#if error}<p class="errore" role="alert">{error}</p>{/if}
</div>

<style>
	.pagina {
		max-width: 40rem;
		margin: 0 auto;
		padding: 1rem;
	}
	.avvertenza {
		border-left: 4px solid #b54708;
		padding: 0.4rem 0.8rem;
		background: var(--surface);
	}
	form {
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		font-weight: 600;
	}
	label.scelta {
		flex-direction: row;
		align-items: center;
		font-weight: 400;
		gap: 0.5rem;
	}
	input,
	textarea {
		min-height: 44px;
		padding: 0.3rem 0.6rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		font: inherit;
		font-weight: 400;
	}
	input[type='radio'] {
		min-height: auto;
	}
	fieldset {
		border: 1px solid var(--border);
		border-radius: 8px;
	}
	button {
		min-height: 48px;
		border-radius: 999px;
		border: none;
		background: var(--accent, #1f6f43);
		color: #fff;
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.nota {
		color: var(--muted);
	}
	.errore {
		color: #b42318;
	}
</style>
