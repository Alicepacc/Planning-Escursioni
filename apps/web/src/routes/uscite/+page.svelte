<script lang="ts">
	import { onMount } from 'svelte';
	import { resolve } from '$app/paths';
	import AccessPanel from '#lib/uscite/AccessPanel.svelte';
	import PushToggle from '#lib/uscite/PushToggle.svelte';
	import { SERVICE_ON, logout, me, myOutings, type Utente } from '#lib/uscite/api.ts';
	import { formatWhen } from '#lib/uscite/local.ts';

	type Mia = Awaited<ReturnType<typeof myOutings>>['uscite'][number];
	let user = $state<Utente | null>(null);
	let list = $state<Mia[]>([]);
	let ready = $state(false);
	let error = $state('');

	async function refresh() {
		try {
			list = user ? (await myOutings()).uscite : [];
		} catch (e) {
			error = (e as Error).message;
		}
	}

	onMount(async () => {
		user = await me();
		await refresh();
		ready = true;
	});

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
		background: var(--accent, #1f6f43);
		color: #fff;
		font-weight: 600;
		text-decoration: none;
	}
	.link {
		background: none;
		border: none;
		color: var(--accent, #1f6f43);
		text-decoration: underline;
		font: inherit;
		cursor: pointer;
		min-height: 44px;
	}
	.errore {
		color: #b42318;
	}
</style>
