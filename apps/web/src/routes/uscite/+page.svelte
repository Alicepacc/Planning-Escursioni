<script lang="ts">
	import { onMount } from 'svelte';
	import { resolve } from '$app/paths';
	import AccessPanel from '#lib/uscite/AccessPanel.svelte';
	import OutingList from '#lib/uscite/OutingList.svelte';
	import DateBadge from '#lib/ui/DateBadge.svelte';
	import Icon from '#lib/ui/Icon.svelte';
	import PushToggle from '#lib/uscite/PushToggle.svelte';
	import {
		SERVICE_ON,
		contactOutings,
		logout,
		me,
		myOutings,
		publicOutings,
		type UscitaInElenco,
		type Utente
	} from '#lib/uscite/api.ts';
	import { formatWhen, romeDay, weekend } from '#lib/uscite/local.ts';
	import { haversineKm } from '#lib/search/explore.ts';

	type Mia = Awaited<ReturnType<typeof myOutings>>['uscite'][number];
	let user = $state<Utente | null>(null);
	let list = $state<Mia[]>([]);
	let fromContacts = $state<UscitaInElenco[]>([]);
	let ready = $state(false);
	let error = $state('');

	// feed pubblico: la posizione resta nel telefono, la distanza si calcola qui
	let pubbliche = $state<UscitaInElenco[] | null>(null);
	let feedError = $state('');
	let here = $state<[number, number] | null>(null);
	let locating = $state(false);
	let geoError = $state('');
	let soloWeekend = $state(false);
	let raggio = $state(50);

	async function refresh() {
		try {
			list = user ? (await myOutings()).uscite : [];
			fromContacts = user ? (await contactOutings()).uscite : [];
		} catch (e) {
			error = (e as Error).message;
		}
	}

	onMount(async () => {
		user = await me();
		await refresh();
		ready = true;
		if (SERVICE_ON) {
			try {
				pubbliche = (await publicOutings()).uscite;
			} catch (e) {
				feedError = (e as Error).message;
			}
		}
	});

	function distance(u: UscitaInElenco): number | null {
		if (!here || u.ritrovo_lon == null || u.ritrovo_lat == null) return null;
		return haversineKm(here, [u.ritrovo_lon, u.ritrovo_lat]);
	}

	const shown = $derived.by(() => {
		if (!pubbliche) return [];
		const [sat, sun] = weekend();
		let out = pubbliche.filter((u) => {
			if (soloWeekend) {
				const day = romeDay(u.ritrovo_quando);
				if (day < sat || day > sun) return false;
			}
			const km = distance(u);
			return km == null || km <= raggio;
		});
		if (here) out = [...out].sort((a, b) => (distance(a) ?? 0) - (distance(b) ?? 0));
		return out;
	});

	function locate() {
		if (!navigator.geolocation) {
			geoError = 'Posizione non disponibile su questo dispositivo.';
			return;
		}
		locating = true;
		geoError = '';
		navigator.geolocation.getCurrentPosition(
			(pos) => {
				locating = false;
				here = [pos.coords.longitude, pos.coords.latitude];
			},
			() => {
				locating = false;
				geoError = 'Non riesco a leggere la posizione (permesso negato o segnale assente).';
			},
			{ enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
		);
	}

	const STATO: Record<string, string> = {
		confermato: 'partecipi',
		attesa: "in lista d'attesa",
		annullata: 'annullata',
		rinviata: 'rinviata'
	};
</script>

<svelte:head><title>Uscite – Cordata</title></svelte:head>

<div class="pagina uscite">
	<h1>Uscite</h1>
	<p class="sotto">Organizza una gita con chi vuoi, o unisciti a un’uscita pubblica vicino a te.</p>
	<aside class="avvertenza">
		<Icon name="affidabile" size={20} />
		<p>
			Uscite <strong>private tra persone</strong>, non organizzate dal CAI: nessuna copertura
			assicurativa CAI, ognuno partecipa sotto la propria responsabilità. Alle gite delle sezioni ci
			si iscrive presso la sezione.
		</p>
	</aside>

	{#if !SERVICE_ON}
		<p class="nota" role="status">
			Il servizio delle uscite non è ancora attivo su questa demo: le pagine sono pronte, il
			servizio verrà pubblicato su Cloudflare.
		</p>
	{:else if !ready}
		<p class="nota">Caricamento…</p>
	{:else if !user}
		<AccessPanel
			onlogin={async (u) => {
				user = u;
				await refresh();
			}}
		/>
	{:else}
		<div class="ciao">
			<span>Ciao <strong>{user.nome}</strong></span>
			<button
				type="button"
				class="link"
				onclick={async () => {
					await logout();
					user = null;
					list = [];
				}}>Esci</button
			>
		</div>
		<a class="nuova" href={resolve('/uscite/nuova')}>
			<span class="piu"><Icon name="uscite" size={24} /></span>
			<span class="testo">
				<b>Organizza un’uscita</b>
				<small>Da una scheda, dal planner o da zero: ritrovo, posti, attrezzatura</small>
			</span>
			<Icon name="freccia" size={18} />
		</a>
		<PushToggle />

		<h2>Le mie uscite</h2>
		{#if list.length}
			<ul class="mie">
				{#each list as u (u.id)}
					<li>
						<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso da resolve() con parametri -->
						<a href={`${resolve('/uscita')}?id=${encodeURIComponent(u.id)}`}>
							<DateBadge iso={u.ritrovo_quando} />
							<span class="testo">
								<b>{u.titolo}</b>
								<small>{formatWhen(u.ritrovo_quando)}</small>
							</span>
							<span
								class="ruolo {u.stato !== 'aperta' ? u.stato : u.organizzo ? 'org' : u.mio_stato}"
								>{u.stato !== 'aperta'
									? STATO[u.stato]
									: u.organizzo
										? 'organizzi tu'
										: STATO[u.mio_stato]}</span
							>
						</a>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="vuoto">
				Nessuna uscita per ora. Apri una scheda e tocca «Organizza uscita», oppure partecipa a una
				di quelle qui sotto.
			</p>
		{/if}
		{#if fromContacts.length}
			<h2>Proposte dai tuoi contatti</h2>
			<p class="nota">Uscite di chi ha già organizzato un’uscita con te.</p>
			<OutingList uscite={fromContacts} />
		{/if}
	{/if}

	{#if SERVICE_ON && ready}
		<section aria-labelledby="pubbliche">
			<h2 id="pubbliche">Uscite pubbliche</h2>
			<p class="nota">Nei prossimi 30 giorni, aperte a tutti.</p>
			<div class="filtri">
				<button type="button" class="chip" class:on={here} onclick={locate} disabled={locating}
					>{locating ? 'Cerco la posizione…' : here ? 'Vicino a me ✓' : 'Vicino a me'}</button
				>
				<label class="chip" class:on={soloWeekend}
					><input type="checkbox" bind:checked={soloWeekend} />
					{soloWeekend ? 'Questo fine settimana ✓' : 'Questo fine settimana'}</label
				>
				{#if here}
					<label class="chip"
						>Entro
						<select bind:value={raggio}>
							{#each [10, 25, 50, 100] as km (km)}<option value={km}>{km} km</option>{/each}
						</select></label
					>
				{/if}
			</div>
			{#if here}
				<p class="nota">La posizione resta sul telefono: serve solo per ordinare l’elenco.</p>
			{/if}
			{#if geoError}<p class="errore" role="alert">{geoError}</p>{/if}
			{#if feedError}
				<p class="errore" role="alert">{feedError}</p>
			{:else if !pubbliche}
				<p class="nota">Caricamento…</p>
			{:else if shown.length}
				<OutingList uscite={shown} {distance} />
			{:else}
				<p class="vuoto">
					{pubbliche.length
						? 'Nessuna uscita pubblica con questi filtri.'
						: 'Nessuna uscita pubblica in programma per ora: organizzane una e scegli «Pubblica».'}
				</p>
			{/if}
		</section>
	{/if}
	{#if error}<p class="errore" role="alert">{error}</p>{/if}
</div>

<style>
	.uscite {
		padding-bottom: 2rem;
	}
	h1 {
		font-size: 1.9rem;
		margin: 0.5rem 0 0.2rem;
	}
	h2 {
		font-size: 1.25rem;
		margin: 1.6rem 0 0.6rem;
	}
	.sotto {
		margin: 0 0 0.9rem;
		color: var(--muted);
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
	.ciao {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin: 1rem 0 0.4rem;
	}
	.nuova,
	.mie a {
		display: flex;
		gap: 0.8rem;
		align-items: center;
		padding: 0.75rem;
		border-radius: var(--r-md);
		background: var(--surface);
		border: 1px solid var(--border);
		color: var(--text);
		text-decoration: none;
	}
	.nuova {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--on-accent);
		margin-bottom: 0.4rem;
	}
	.piu {
		display: grid;
		place-items: center;
		width: 3rem;
		height: 3rem;
		border-radius: 12px;
		background: color-mix(in srgb, var(--on-accent) 16%, transparent);
	}
	.testo {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		min-width: 0;
		flex: 1;
	}
	.testo b {
		font: 600 1rem/1.25 var(--font-body);
	}
	.testo small {
		font-size: 0.82rem;
		opacity: 0.8;
	}
	.mie {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.6rem;
	}
	.ruolo {
		flex: none;
		padding: 0.2rem 0.55rem;
		border-radius: 999px;
		font: 600 0.75rem var(--font-body);
		background: var(--chip);
		color: var(--muted);
	}
	.ruolo.org,
	.ruolo.confermato {
		background: color-mix(in srgb, var(--ok) 14%, transparent);
		color: var(--ok);
	}
	.ruolo.attesa,
	.ruolo.rinviata {
		background: color-mix(in srgb, var(--rust) 14%, transparent);
		color: var(--rust);
	}
	.ruolo.annullata {
		background: color-mix(in srgb, #b42318 14%, transparent);
		color: #b42318;
	}
	.filtri {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin: 0.5rem 0 0.8rem;
	}
	.chip {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		min-height: 40px;
		padding: 0 0.9rem;
		border-radius: 999px;
		border: 0;
		background: var(--chip);
		color: var(--text);
		font: 500 0.88rem var(--font-body);
		cursor: pointer;
	}
	.chip.on {
		background: var(--accent);
		color: var(--on-accent);
	}
	/* la casella resta per i lettori di schermo; si vede la pillola accesa */
	.chip input {
		position: absolute;
		opacity: 0;
		width: 1px;
		height: 1px;
	}
	.chip:has(input:focus-visible) {
		outline: 3px solid var(--rust);
		outline-offset: 2px;
	}
	.chip select {
		min-height: 30px;
		border: 0;
		background: transparent;
		color: inherit;
	}
	.nota {
		color: var(--muted);
		margin: 0.2rem 0;
	}
	.vuoto {
		padding: 1rem;
		border-radius: var(--r-md);
		border: 1px dashed var(--border);
		color: var(--muted);
		text-align: center;
	}
	.link {
		background: none;
		border: none;
		color: var(--accent);
		text-decoration: underline;
		font: inherit;
		cursor: pointer;
		min-height: 44px;
	}
	.errore {
		color: #b42318;
	}
</style>
