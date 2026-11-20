<script lang="ts">
	import { onMount } from 'svelte';
	import { resolve } from '$app/paths';
	import AccessPanel from '#lib/uscite/AccessPanel.svelte';
	import OutingList from '#lib/uscite/OutingList.svelte';
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

<div class="pagina">
	<h1>Uscite di gruppo</h1>
	<p class="avvertenza">
		Le uscite create qui sono <strong>private tra persone</strong>, non organizzate dal CAI: nessuna
		copertura assicurativa CAI, ognuno partecipa sotto la propria responsabilità. Per le gite delle
		sezioni ci si iscrive presso la sezione.
	</p>

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
		<p>
			Ciao <strong>{user.nome}</strong> ·
			<button
				type="button"
				class="link"
				onclick={async () => {
					await logout();
					user = null;
					list = [];
				}}>Esci</button
			>
		</p>
		<p><a class="bottone" href={resolve('/uscite/nuova')}>Organizza un’uscita</a></p>
		<PushToggle />
		<h2>Le mie uscite</h2>
		{#if list.length}
			<ul class="elenco">
				{#each list as u (u.id)}
					<li>
						<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- percorso da resolve() con parametri -->
						<a href={`${resolve('/uscita')}?id=${encodeURIComponent(u.id)}`}>{u.titolo}</a>
						<span class="nota"
							>{formatWhen(u.ritrovo_quando)} · {u.organizzo
								? 'organizzi tu'
								: STATO[u.mio_stato]}{#if u.stato !== 'aperta'}
								· {STATO[u.stato]}{/if}</span
						>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="nota">Nessuna uscita per ora. Organizzane una da una scheda o dal planner.</p>
		{/if}
		{#if fromContacts.length}
			<h2>Proposte dai tuoi contatti</h2>
			<p class="nota">Uscite di chi ha già organizzato un’uscita con te.</p>
			<OutingList uscite={fromContacts} />
		{/if}
	{/if}

	{#if SERVICE_ON && ready}
		<section aria-labelledby="pubbliche">
			<h2 id="pubbliche">Uscite pubbliche dei prossimi 30 giorni</h2>
			<div class="filtri">
				<button type="button" class="chip" onclick={locate} disabled={locating}
					>{locating
						? 'Cerco la posizione…'
						: here
							? 'Aggiorna la posizione'
							: 'Vicino a me'}</button
				>
				<label class="chip"
					><input type="checkbox" bind:checked={soloWeekend} /> Questo fine settimana</label
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
				<p class="nota">
					{pubbliche.length
						? 'Nessuna uscita pubblica con questi filtri.'
						: 'Nessuna uscita pubblica in programma per ora.'}
				</p>
			{/if}
		</section>
	{/if}
	{#if error}<p class="errore" role="alert">{error}</p>{/if}
</div>

<style>
	.pagina {
		max-width: 46rem;
		margin: 0 auto;
		padding: 1rem;
	}
	.avvertenza {
		border-left: 4px solid #b54708;
		padding: 0.4rem 0.8rem;
		background: var(--surface);
	}
	.nota {
		color: var(--muted);
	}
	.elenco {
		list-style: none;
		padding: 0;
	}
	.elenco li {
		display: flex;
		flex-direction: column;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--border);
	}
	.bottone {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		padding: 0 1rem;
		border-radius: 999px;
		background: var(--accent);
		color: var(--on-accent);
		font-weight: 600;
		text-decoration: none;
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
	.filtri {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin: 0.5rem 0;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		min-height: 44px;
		padding: 0 0.9rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: inherit;
		font: inherit;
		cursor: pointer;
	}
</style>
