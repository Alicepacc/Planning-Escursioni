<script lang="ts">
	// Pagina invito (SPEC §5.4): si legge col link, senza account; per partecipare serve una passkey.
	import { onMount } from 'svelte';
	import { resolve } from '$app/paths';
	import AccessPanel from '#lib/uscite/AccessPanel.svelte';
	import PushToggle from '#lib/uscite/PushToggle.svelte';
	import QrCode from '#lib/uscite/QrCode.svelte';
	import DateBadge from '#lib/ui/DateBadge.svelte';
	import DiffPill from '#lib/ui/DiffPill.svelte';
	import Icon from '#lib/ui/Icon.svelte';
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

	const timeOf = (iso: string) =>
		new Intl.DateTimeFormat('it-IT', {
			timeZone: 'Europe/Rome',
			weekday: 'long',
			day: 'numeric',
			month: 'long',
			hour: '2-digit',
			minute: '2-digit'
		}).format(new Date(iso));
	const STATO_P: Record<string, string> = {
		confermato: 'confermato',
		attesa: 'in attesa',
		rinunciato: 'ha rinunciato'
	};

	const STATO_MIO: Record<string, string> = {
		confermato: 'Partecipi: il tuo posto è confermato.',
		attesa: 'Sei in lista d’attesa: se si libera un posto passi tra i confermati.',
		rinunciato: 'Hai rinunciato.'
	};
</script>

<svelte:head><title>{u ? `${u.titolo} – Uscita` : 'Uscita'} – Cordata</title></svelte:head>

<div class="pagina uscita">
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

		<div class="quando">
			<DateBadge iso={u.ritrovo_quando} />
			<span class="testo">
				<b>{timeOf(u.ritrovo_quando)}</b>
				<span
					>{u.ritrovo_luogo +
						(u.ritrovo_lon != null && u.ritrovo_lat != null
							? ' · '
							: '')}{#if u.ritrovo_lon != null && u.ritrovo_lat != null}<a
							href={`https://www.openstreetmap.org/?mlat=${u.ritrovo_lat}&mlon=${u.ritrovo_lon}#map=16/${u.ritrovo_lat}/${u.ritrovo_lon}`}
							target="_blank"
							rel="noopener noreferrer">punto sulla mappa</a
						>{/if}</span
				>
			</span>
		</div>

		<div class="posti">
			<Icon name="uscite" size={20} />
			<span>{seatsText}</span>
			{#if u.difficolta}<DiffPill code={u.difficolta} />{/if}
		</div>

		<section class="azioni" aria-label="Partecipazione">
			{#if u.mio_stato && u.mio_stato !== 'rinunciato' && !u.sono_organizzatore}
				<p class="mio {u.mio_stato}" role="status">{STATO_MIO[u.mio_stato]}</p>
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
				<button type="button" class="secondario" onclick={share}
					><Icon name="condividi" size={18} /> Condividi il link d’invito</button
				>
				<details class="qr">
					<summary>Mostra il codice QR</summary>
					<QrCode text={inviteUrl} label={`Codice QR dell’invito a ${u.titolo}`} />
					<p class="nota">Da inquadrare con la fotocamera del telefono: apre questa pagina.</p>
				</details>
			{/if}
		</section>
		{#if notice}<p class="ok" role="status">{notice}</p>{/if}
		{#if error}<p class="errore" role="alert">{error}</p>{/if}

		<aside class="avvertenza">
			<Icon name="affidabile" size={20} />
			<p>{u.avvertenza}</p>
		</aside>

		<h2>Dettagli</h2>
		<dl class="dati">
			{#if u.mezzi}<div>
					<dt>Mezzi</dt>
					<dd>{u.mezzi}</dd>
				</div>{/if}
			{#if u.iscrizioni_entro}<div>
					<dt>Iscrizioni entro</dt>
					<dd>{formatWhen(u.iscrizioni_entro)}</dd>
				</div>{/if}
			{#if u.requisiti}<div>
					<dt>Requisiti</dt>
					<dd>{u.requisiti}</dd>
				</div>{/if}
			{#if u.note}<div>
					<dt>Note</dt>
					<dd>{u.note}</dd>
				</div>{/if}
			{#if u.attrezzatura.length}
				<div>
					<dt>Attrezzatura</dt>
					<dd>
						<ul class="checklist">
							{#each u.attrezzatura as a (a)}<li>
									<label><input type="checkbox" /> {a}</label>
								</li>{/each}
						</ul>
					</dd>
				</div>
			{/if}
			{#if u.itinerario}
				<div>
					<dt>Itinerario</dt>
					<dd>
						<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso interno salvato dall'organizzatore, con resolve() -->
						<a href={itineraryHref}>Apri la scheda o il piano</a>
					</dd>
				</div>
			{/if}
			{#if !u.mezzi && !u.iscrizioni_entro && !u.requisiti && !u.note && !u.attrezzatura.length && !u.itinerario}
				<div><dd class="nota">Nessun altro dettaglio dall’organizzatore.</dd></div>
			{/if}
		</dl>

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
							<span class="iniziale" aria-hidden="true">{p.nome.slice(0, 1).toUpperCase()}</span>
							<span class="chi"
								><b>{p.nome}</b>
								<small
									>{p.utente === u.organizzatore
										? 'organizza'
										: (STATO_P[p.stato] ?? p.stato)}</small
								></span
							>
							{#if p.utente !== u.organizzatore && p.stato === 'attesa'}
								<button
									type="button"
									class="piccolo"
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
									class="piccolo secondario"
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
				<label class="campo"
					>Nuova data <input type="datetime-local" bind:value={nuovaData} /></label
				>
				<div class="riga">
					<button
						type="button"
						class="secondario"
						disabled={busy || !nuovaData}
						onclick={() =>
							act(() => setOutingStatus(id, 'rinviata', localToIso(nuovaData)), 'Uscita rinviata.')}
						>Rinvia</button
					>
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
				</div>
				<p class="nota">
					Chi ha attivato le notifiche riceve un avviso per annullamenti, rinvii e annunci.
				</p>
			</section>
		{/if}
	{/if}
</div>

<style>
	.uscita {
		max-width: 46rem;
		padding-bottom: 2rem;
	}
	.tipo {
		margin: 0.6rem 0 0.2rem;
		color: var(--rust);
		font: 600 0.75rem var(--font-body);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	h1 {
		font-size: 1.8rem;
		margin: 0 0 0.8rem;
	}
	h2 {
		font-size: 1.2rem;
		margin: 1.5rem 0 0.6rem;
	}
	h3 {
		font: 600 0.95rem var(--font-body);
		margin: 1.1rem 0 0.4rem;
	}
	.stato {
		font-weight: 600;
		padding: 0.55rem 0.8rem;
		border-radius: var(--r-sm);
		margin: 0 0 0.8rem;
	}
	.annullata {
		background: color-mix(in srgb, #b42318 14%, var(--surface));
		color: #b42318;
	}
	.rinviata {
		background: color-mix(in srgb, var(--rust) 14%, var(--surface));
		color: var(--rust);
	}
	.quando,
	.posti,
	.dati,
	.organizzatore,
	.annunci li {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--r-md);
	}
	.quando {
		display: flex;
		gap: 0.85rem;
		align-items: center;
		padding: 0.8rem;
	}
	.quando .testo {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-width: 0;
	}
	.quando b {
		font-weight: 600;
	}
	.quando b::first-letter {
		text-transform: uppercase;
	}
	.quando span span {
		color: var(--muted);
		font-size: 0.9rem;
	}
	.posti {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin-top: 0.5rem;
		padding: 0.65rem 0.8rem;
		color: var(--accent);
	}
	.posti span {
		flex: 1;
		color: var(--text);
		font-size: 0.92rem;
	}
	.azioni {
		display: grid;
		gap: 0.5rem;
		margin: 1rem 0;
	}
	.mio {
		margin: 0;
		padding: 0.7rem 0.85rem;
		border-radius: var(--r-md);
		font-weight: 600;
		background: color-mix(in srgb, var(--ok) 14%, var(--surface));
		color: var(--ok);
	}
	.mio.attesa {
		background: color-mix(in srgb, var(--rust) 14%, var(--surface));
		color: var(--rust);
	}
	button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.45rem;
		min-height: 48px;
		padding: 0 1.1rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: var(--accent);
		color: var(--on-accent);
		font: 600 1rem var(--font-body);
		cursor: pointer;
	}
	button.grande {
		min-height: 54px;
		font-size: 1.1rem;
	}
	button.secondario {
		background: transparent;
		color: var(--accent);
	}
	button.piccolo {
		min-height: 40px;
		padding: 0 0.85rem;
		font-size: 0.88rem;
	}
	button.pericolo {
		background: #b42318;
		border-color: #b42318;
		color: #fff;
	}
	button:disabled {
		opacity: 0.6;
	}
	.qr summary {
		padding: 0.6rem 0;
		color: var(--accent);
		font-weight: 600;
		cursor: pointer;
		text-align: center;
	}
	.qr :global(svg) {
		display: block;
		margin: 0.4rem auto;
		padding: 0.6rem;
		background: #fff;
		border-radius: var(--r-md);
	}
	.qr .nota {
		text-align: center;
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
	.dati {
		margin: 0;
		padding: 0 0.85rem;
	}
	.dati > div {
		padding: 0.65rem 0;
		border-bottom: 1px solid var(--border);
	}
	.dati > div:last-child {
		border-bottom: 0;
	}
	dt {
		color: var(--muted);
		font-size: 0.8rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	dd {
		margin: 0.1rem 0 0;
	}
	.checklist {
		list-style: none;
		padding: 0;
		margin: 0.2rem 0 0;
		display: grid;
		gap: 0.1rem;
	}
	.checklist label {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		min-height: 40px;
	}
	.checklist input {
		width: 20px;
		height: 20px;
	}
	.annunci {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.5rem;
	}
	.annunci li {
		padding: 0.7rem 0.85rem;
		border-left: 4px solid var(--accent);
	}
	.organizzatore {
		margin-top: 1.5rem;
		padding: 0.2rem 1rem 1rem;
	}
	.organizzatore h2 {
		margin-top: 0.9rem;
	}
	.partecipanti {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.partecipanti li {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--border);
	}
	.partecipanti li:last-child {
		border-bottom: 0;
	}
	.iniziale {
		display: grid;
		place-items: center;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 50%;
		background: var(--brand-soft);
		color: var(--accent);
		font-weight: 700;
	}
	.chi {
		flex: 1;
		display: flex;
		flex-direction: column;
	}
	.chi small {
		color: var(--muted);
	}
	form {
		display: grid;
		gap: 0.45rem;
	}
	form label,
	.campo {
		font-size: 0.9rem;
		font-weight: 500;
	}
	textarea {
		min-height: 5rem;
	}
	.campo {
		display: grid;
		gap: 0.3rem;
	}
	.campo input {
		padding: 0 0.7rem;
	}
	.riga {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
		margin-top: 0.6rem;
	}
	.nota {
		color: var(--muted);
		font-size: 0.88rem;
	}
	.ok {
		color: var(--ok);
		font-weight: 600;
	}
	.errore {
		color: #b42318;
	}
</style>
