<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { generatedAsset } from '#lib/data/paths.ts';
	import type { ItineraryDoc } from '#lib/data/types.ts';
	import AccessPanel from '#lib/uscite/AccessPanel.svelte';
	import Icon from '#lib/ui/Icon.svelte';
	import MeetingPoint from '#lib/uscite/MeetingPoint.svelte';
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
	let visibilita = $state<'link' | 'contatti' | 'pubblica'>('link');
	let punto = $state<[number, number] | null>(null);
	let puntoDaItinerario = $state(false);

	onMount(async () => {
		const q = new URL(location.href).searchParams;
		titolo = q.get('titolo') ?? '';
		itinerario = q.get('da') ?? '';
		difficolta = q.get('difficolta') ?? '';
		// da una scheda: il punto di ritrovo parte dalla partenza dell'itinerario (si può spostare)
		const slug = /^\/attivita\/([\w-]+)$/.exec(itinerario)?.[1];
		if (slug) {
			try {
				const doc = (await (
					await fetch(generatedAsset(`data/attivita/${slug}.json`))
				).json()) as ItineraryDoc;
				if (doc.start.lon != null && doc.start.lat != null) {
					punto = [doc.start.lon, doc.start.lat];
					puntoDaItinerario = true;
				}
			} catch {
				// scheda non raggiungibile: il punto si sceglie sulla mappa
			}
		}
		user = await me();
		ready = true;
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (visibilita === 'pubblica' && !punto) {
			error = 'Per un’uscita pubblica scegli il punto di ritrovo sulla mappa.';
			return;
		}
		busy = true;
		error = '';
		try {
			const { id, invito } = await createOuting({
				titolo,
				itinerario: itinerario || undefined,
				ritrovo_quando: localToIso(quando),
				ritrovo_luogo: luogo,
				ritrovo_lon: punto?.[0],
				ritrovo_lat: punto?.[1],
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

<div class="pagina nuova">
	<h1>Organizza un’uscita</h1>
	<aside class="avvertenza">
		<Icon name="affidabile" size={20} />
		<p>
			Uscita <strong>privata tra persone</strong>, non organizzata dal CAI: nessuna copertura
			assicurativa CAI, ognuno partecipa sotto la propria responsabilità.
		</p>
	</aside>
	{#if !SERVICE_ON}
		<p class="nota" role="status">Il servizio delle uscite non è ancora attivo su questa demo.</p>
	{:else if !ready}
		<p class="nota">Caricamento…</p>
	{:else if !user}
		<AccessPanel why="Per organizzare un’uscita serve un account." onlogin={(u) => (user = u)} />
	{:else}
		<form onsubmit={submit}>
			<section class="gruppo">
				<h2>Dove e quando</h2>
				<label>Titolo <input bind:value={titolo} required maxlength="120" /></label>
				<label
					>Ritrovo: data e ora <input type="datetime-local" bind:value={quando} required /></label
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
			</section>

			<section class="gruppo">
				<h2>Ritrovo sulla mappa</h2>
				<p class="nota">
					{puntoDaItinerario
						? 'Proposto: la partenza dell’itinerario. Spostalo se vi trovate altrove.'
						: 'Serve per le uscite pubbliche: chi cerca vicino a sé la trova.'}
				</p>
				<MeetingPoint bind:point={punto} />
			</section>

			<section class="gruppo">
				<h2>Il gruppo</h2>
				<div class="due">
					<label
						>Posti, te compreso <input type="number" min="1" max="200" bind:value={posti} /></label
					>
					<label
						>Difficoltà <input
							bind:value={difficolta}
							maxlength="20"
							placeholder="T, E, EE, EEA"
						/></label
					>
				</div>
				<label>Iscrizioni entro <input type="datetime-local" bind:value={entro} /></label>
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
						placeholder="scarponi, giacca, frontale…"
					/></label
				>
				<label>Note <textarea bind:value={note} maxlength="2000"></textarea></label>
			</section>

			<fieldset class="gruppo visibilita">
				<legend>Chi può vederla</legend>
				<label class="scelta"
					><input type="radio" bind:group={visibilita} value="link" />
					<span><b>Solo chi ha il link</b> <small>lo mandi tu a chi vuoi</small></span></label
				>
				<label class="scelta"
					><input type="radio" bind:group={visibilita} value="contatti" />
					<span
						><b>I miei contatti</b>
						<small>(chi è già uscito con te la trova in «Uscite» e riceve un avviso)</small></span
					></label
				>
				<label class="scelta"
					><input type="radio" bind:group={visibilita} value="pubblica" />
					<span
						><b>Pubblica</b>
						<small
							>(compare nell’elenco delle uscite dei prossimi 30 giorni, con il punto di ritrovo)</small
						></span
					></label
				>
			</fieldset>
			{#if itinerario}
				<p class="nota">Itinerario collegato: {itinerario}</p>
			{/if}
			<button type="submit" disabled={busy}>Crea l’uscita e il link d’invito</button>
		</form>
	{/if}
	{#if error}<p class="errore" role="alert">{error}</p>{/if}
</div>

<style>
	.nuova {
		max-width: 40rem;
		padding-bottom: 2rem;
	}
	h1 {
		font-size: 1.8rem;
		margin: 0.5rem 0 0.8rem;
	}
	.avvertenza {
		display: flex;
		gap: 0.6rem;
		align-items: flex-start;
		padding: 0.7rem 0.85rem;
		border-radius: var(--r-md);
		background: color-mix(in srgb, var(--rust) 9%, var(--surface));
		border: 1px solid color-mix(in srgb, var(--rust) 25%, transparent);
		color: var(--rust);
	}
	.avvertenza p {
		margin: 0;
		color: var(--text);
		font-size: 0.85rem;
	}
	form {
		display: grid;
		gap: 0.9rem;
		margin-top: 1rem;
	}
	.gruppo {
		display: grid;
		gap: 0.75rem;
		margin: 0;
		padding: 0.9rem 1rem 1rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--r-lg);
	}
	h2,
	legend {
		margin: 0;
		font: 600 1.1rem var(--font-display);
	}
	legend {
		float: left;
		width: 100%;
		padding: 0 0 0.2rem;
	}
	label {
		display: grid;
		gap: 0.3rem;
		font-size: 0.9rem;
		font-weight: 500;
	}
	input,
	textarea {
		width: 100%;
		padding: 0 0.75rem;
		font-size: 1rem;
		font-weight: 400;
	}
	textarea {
		min-height: 4.5rem;
		padding: 0.6rem 0.75rem;
	}
	.due {
		display: grid;
		grid-template-columns: 1fr 1fr;
		align-items: end;
		gap: 0.6rem;
	}
	.scelta {
		display: flex;
		align-items: flex-start;
		gap: 0.65rem;
		padding: 0.7rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: var(--r-md);
		cursor: pointer;
	}
	.scelta:has(input:checked) {
		border-color: var(--accent);
		background: var(--brand-soft);
	}
	.scelta input {
		width: 20px;
		height: 20px;
		margin: 0.1rem 0 0;
		flex: none;
	}
	.scelta span {
		display: flex;
		flex-direction: column;
	}
	.scelta b {
		font-size: 1rem;
		font-weight: 600;
	}
	.scelta small {
		color: var(--muted);
		font-weight: 400;
		font-size: 0.82rem;
	}
	button {
		min-height: 54px;
		border-radius: 999px;
		border: none;
		background: var(--accent);
		color: var(--on-accent);
		font: 600 1.05rem var(--font-body);
		cursor: pointer;
	}
	button:disabled {
		opacity: 0.6;
	}
	.nota {
		margin: 0;
		color: var(--muted);
		font-size: 0.88rem;
	}
	.errore {
		color: #b42318;
	}
</style>
