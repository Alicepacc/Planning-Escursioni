<script lang="ts">
	// Pagina invito (SPEC §5.4): si legge col link, senza account; per partecipare serve una passkey.
	import { onMount } from 'svelte';
	import { resolve } from '$app/paths';
	import AccessPanel from '#lib/uscite/AccessPanel.svelte';
	import PushToggle from '#lib/uscite/PushToggle.svelte';
	import QrCode from '#lib/uscite/QrCode.svelte';
	import {
		API,
		SERVICE_ON,
		announce,
		getOuting,
		joinOuting,
		leaveOuting,
		me,
		setOutingStatus,
		setParticipant,
		type Uscita,
		type Utente
	} from '#lib/uscite/api.ts';
	import { formatWhen, knownInvite, localToIso } from '#lib/uscite/local.ts';

	let id = $state('');
	let token = $state<string | null>(null);
	let user = $state<Utente | null>(null);
	let u = $state<Uscita | null>(null);
	let error = $state('');
	let notice = $state('');
	let busy = $state(false);
	let wantsAccess = $state(false);
	let nuovaData = $state('');
	let annuncio = $state('');

	async function load() {
		try {
			u = await getOuting(id, token);
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
	}

	onMount(async () => {
		const q = new URL(location.href).searchParams;
		id = q.get('id') ?? '';
		token = q.get('t') ?? knownInvite(id);
		if (!SERVICE_ON || !id) return;
		user = await me();
		await load();
	});

	async function act(action: () => Promise<unknown>, done: string) {
		busy = true;
		notice = '';
		error = '';
		try {
			await action();
			notice = done;
			await load();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	const seatsText = $derived(
		u
			? [
					`${u.confermati} ${u.confermati === 1 ? 'confermato' : 'confermati'}${u.posti ? ` su ${u.posti}` : ''}`,
					u.in_attesa ? `${u.in_attesa} in lista d’attesa` : ''
				]
					.filter(Boolean)
					.join(' · ')
			: ''
	);
	const itineraryHref = $derived(
		u?.itinerario?.startsWith('/')
			? `${resolve('/')}${u.itinerario.slice(1)}`
			: (u?.itinerario ?? '')
	);
	const inviteUrl = $derived(
		// le uscite pubbliche si condividono anche senza il segreto del link
		(token || u?.visibilita === 'pubblica') && typeof location !== 'undefined'
			? `${location.origin}${resolve('/uscita')}?id=${encodeURIComponent(id)}${token ? `&t=${encodeURIComponent(token)}` : ''}`
			: ''
	);

	// il link da condividere passa dal servizio, che mostra l'anteprima nelle app di messaggistica
	// e rimanda alla pagina; il codice QR punta direttamente alla pagina
	const shareUrl = $derived(
		token || u?.visibilita === 'pubblica'
			? `${API}/invito/${encodeURIComponent(id)}${token ? `?t=${encodeURIComponent(token)}` : ''}`
			: ''
	);

	async function share() {
		if (!u || !shareUrl) return;
		const data = {
			title: u.titolo,
			text: `${u.titolo} – ${formatWhen(u.ritrovo_quando)}`,
			url: shareUrl
		};
		try {
			if (navigator.share) await navigator.share(data);
			else {
				await navigator.clipboard.writeText(shareUrl);
				notice = 'Link d’invito copiato.';
			}
		} catch {
			// condivisione annullata
		}
	}

	const STATO_MIO: Record<string, string> = {
		confermato: 'Partecipi: il tuo posto è confermato.',
		attesa: 'Sei in lista d’attesa: se si libera un posto passi tra i confermati.',
		rinunciato: 'Hai rinunciato.'
	};
</script>

<svelte:head><title>{u ? `${u.titolo} – Uscita` : 'Uscita'} – Cordata</title></svelte:head>

<div class="pagina">
	{#if !SERVICE_ON}
		<h1>Uscita</h1>
		<p class="nota" role="status">Il servizio delle uscite non è ancora attivo su questa demo.</p>
	{:else if error && !u}
		<h1>Uscita</h1>
		<p class="errore" role="alert">{error}</p>
		<p class="nota">Serve il link d’invito completo, quello ricevuto dall’organizzatore.</p>
	{:else if !u}
		<p class="nota">Caricamento…</p>
	{:else}
		<p class="tipo">Uscita di gruppo · organizza {u.organizzatore_nome}</p>
		<h1>{u.titolo}</h1>
		{#if u.stato === 'annullata'}
			<p class="stato annullata" role="status">Uscita annullata dall’organizzatore.</p>
		{:else if u.stato === 'rinviata'}
			<p class="stato rinviata" role="status">Uscita rinviata: nuova data qui sotto.</p>
		{/if}
		<p class="avvertenza">{u.avvertenza}</p>

		<dl class="dati">
			<dt>Ritrovo</dt>
			<dd>
				{formatWhen(u.ritrovo_quando)} · {u.ritrovo_luogo}{#if u.ritrovo_lon != null && u.ritrovo_lat != null}
					·
					<a
						href={`https://www.openstreetmap.org/?mlat=${u.ritrovo_lat}&mlon=${u.ritrovo_lon}#map=16/${u.ritrovo_lat}/${u.ritrovo_lon}`}
						target="_blank"
						rel="noopener noreferrer">punto sulla mappa</a
					>{/if}
			</dd>
			{#if u.mezzi}<dt>Mezzi</dt>
				<dd>{u.mezzi}</dd>{/if}
			<dt>Posti</dt>
			<dd>
				{seatsText}
			</dd>
			{#if u.iscrizioni_entro}<dt>Iscrizioni entro</dt>
				<dd>{formatWhen(u.iscrizioni_entro)}</dd>{/if}
			{#if u.difficolta}<dt>Difficoltà</dt>
				<dd>{u.difficolta}</dd>{/if}
			{#if u.requisiti}<dt>Requisiti</dt>
				<dd>{u.requisiti}</dd>{/if}
			{#if u.attrezzatura.length}
				<dt>Attrezzatura</dt>
				<dd>
					<ul class="checklist">
						{#each u.attrezzatura as a (a)}<li>
								<label><input type="checkbox" /> {a}</label>
							</li>{/each}
					</ul>
				</dd>
			{/if}
			{#if u.note}<dt>Note</dt>
				<dd>{u.note}</dd>{/if}
			{#if u.itinerario}
				<dt>Itinerario</dt>
				<dd>
					<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso interno salvato dall'organizzatore, con resolve() -->
					<a href={itineraryHref}>apri la scheda o il piano</a>
				</dd>
			{/if}
		</dl>

		<section class="azioni" aria-label="Partecipazione">
			{#if u.mio_stato && u.mio_stato !== 'rinunciato' && !u.sono_organizzatore}
				<p role="status">{STATO_MIO[u.mio_stato]}</p>
				<button
					type="button"
					class="secondario"
					disabled={busy}
					onclick={() => act(() => leaveOuting(id), 'Hai rinunciato.')}>Rinuncio</button
				>
			{:else if !u.sono_organizzatore}
				{#if !u.iscrizioni_aperte}
					<p class="nota">Le iscrizioni sono chiuse.</p>
				{:else if user}
					<button
						type="button"
						class="grande"
						disabled={busy}
						onclick={() => act(() => joinOuting(id, token), 'Iscrizione registrata.')}
						>Partecipo</button
					>
				{:else if wantsAccess}
					<AccessPanel
						why="Per partecipare serve un account: chi organizza vedrà il tuo nome."
						onlogin={async (who) => {
							user = who;
							wantsAccess = false;
							await act(() => joinOuting(id, token), 'Iscrizione registrata.');
						}}
					/>
				{:else}
					<button type="button" class="grande" onclick={() => (wantsAccess = true)}
						>Partecipo</button
					>
				{/if}
			{/if}
			{#if inviteUrl}
				<button type="button" class="secondario" onclick={share}>Condividi il link d’invito</button>
				<details class="qr">
					<summary>Mostra il codice QR</summary>
					<QrCode text={inviteUrl} label={`Codice QR dell’invito a ${u.titolo}`} />
					<p class="nota">Da inquadrare con la fotocamera del telefono: apre questa pagina.</p>
				</details>
			{/if}
		</section>

		{#if u.sono_organizzatore || u.mio_stato === 'confermato' || u.mio_stato === 'attesa'}
			<PushToggle />
		{/if}

		{#if u.annunci.length}
			<section aria-labelledby="bacheca">
				<h2 id="bacheca">Bacheca</h2>
				<ul class="annunci">
					{#each u.annunci as a (a.id)}<li>{a.testo}</li>{/each}
				</ul>
			</section>
		{/if}

		{#if u.sono_organizzatore}
			<section class="organizzatore" aria-labelledby="org">
				<h2 id="org">Gestisci l’uscita</h2>
				<h3>Partecipanti</h3>
				<ul class="partecipanti">
					{#each u.partecipanti ?? [] as p (p.utente)}
						<li>
							<span>{p.nome} · {p.stato}</span>
							{#if p.utente !== u.organizzatore && p.stato === 'attesa'}
								<button
									type="button"
									disabled={busy}
									onclick={() =>
										act(
											() => setParticipant(id, p.utente, 'confermato'),
											'Partecipante confermato.'
										)}>Conferma</button
								>
							{:else if p.utente !== u.organizzatore && p.stato === 'confermato'}
								<button
									type="button"
									class="secondario"
									disabled={busy}
									onclick={() =>
										act(
											() => setParticipant(id, p.utente, 'attesa'),
											'Spostato in lista d’attesa.'
										)}>In attesa</button
								>
							{/if}
						</li>
					{/each}
				</ul>
				<h3>Bacheca</h3>
				<form
					onsubmit={(e) => {
						e.preventDefault();
						act(() => announce(id, annuncio), 'Annuncio pubblicato.').then(() => (annuncio = ''));
					}}
				>
					<label for="annuncio">Annuncio ai partecipanti</label>
					<textarea id="annuncio" bind:value={annuncio} maxlength="1000" required></textarea>
					<button type="submit" disabled={busy || !annuncio.trim()}>Pubblica</button>
				</form>
				<h3>Annulla o rinvia</h3>
				<div class="riga">
					{#if u.stato !== 'annullata'}
						<button
							type="button"
							class="pericolo"
							disabled={busy}
							onclick={() => act(() => setOutingStatus(id, 'annullata'), 'Uscita annullata.')}
							>Annulla l’uscita</button
						>
					{:else}
						<button
							type="button"
							disabled={busy}
							onclick={() => act(() => setOutingStatus(id, 'aperta'), 'Uscita riaperta.')}
							>Riapri</button
						>
					{/if}
					<label class="inline"
						>Nuova data <input type="datetime-local" bind:value={nuovaData} /></label
					>
					<button
						type="button"
						class="secondario"
						disabled={busy || !nuovaData}
						onclick={() =>
							act(() => setOutingStatus(id, 'rinviata', localToIso(nuovaData)), 'Uscita rinviata.')}
						>Rinvia</button
					>
				</div>
				<p class="nota">
					Chi ha attivato le notifiche riceve un avviso per annullamenti, rinvii e annunci.
				</p>
			</section>
		{/if}
		{#if notice}<p class="ok" role="status">{notice}</p>{/if}
		{#if error}<p class="errore" role="alert">{error}</p>{/if}
	{/if}
</div>

<style>
	.pagina {
		max-width: 46rem;
		margin: 0 auto;
		padding: 1rem;
	}
	.tipo {
		color: var(--accent, #1f6f43);
		font-weight: 700;
		text-transform: uppercase;
		font-size: 0.85rem;
		letter-spacing: 0.04em;
	}
	.avvertenza {
		border-left: 4px solid #b54708;
		padding: 0.4rem 0.8rem;
		background: var(--surface);
	}
	.stato {
		font-weight: 700;
		padding: 0.4rem 0.8rem;
		border-radius: 8px;
	}
	.annullata {
		background: #fee4e2;
		color: #912018;
	}
	.rinviata {
		background: #fef0c7;
		color: #93370d;
	}
	.dati {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.3rem 1rem;
	}
	dt {
		font-weight: 700;
	}
	dd {
		margin: 0;
	}
	.checklist {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.azioni,
	.riga {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
		margin: 1rem 0;
	}
	button {
		min-height: 44px;
		padding: 0 1rem;
		border-radius: 999px;
		border: 1px solid var(--accent, #1f6f43);
		background: var(--accent, #1f6f43);
		color: #fff;
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	button.grande {
		min-height: 52px;
		font-size: 1.15rem;
		padding: 0 2rem;
	}
	button.secondario {
		background: transparent;
		color: var(--accent, #1f6f43);
	}
	.qr {
		width: 100%;
	}
	.qr summary {
		padding: 0.7rem 0;
		color: var(--accent, #1f6f43);
		font-weight: 600;
		cursor: pointer;
	}
	.qr :global(svg) {
		margin: 0.4rem 0;
		padding: 0.5rem;
		border: 1px solid var(--border);
		border-radius: 8px;
	}
	button.pericolo {
		background: #b42318;
		border-color: #b42318;
	}
	button:disabled {
		opacity: 0.6;
	}
	.organizzatore {
		border-top: 1px solid var(--border);
		margin-top: 1rem;
	}
	.partecipanti {
		list-style: none;
		padding: 0;
	}
	.partecipanti li {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		padding: 0.3rem 0;
		border-bottom: 1px solid var(--border);
	}
	form {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	textarea,
	input[type='datetime-local'] {
		min-height: 44px;
		border: 1px solid var(--border);
		border-radius: 8px;
		font: inherit;
		padding: 0.3rem 0.6rem;
	}
	.inline {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.nota {
		color: var(--muted);
	}
	.ok {
		color: #067647;
	}
	.errore {
		color: #b42318;
	}
</style>
