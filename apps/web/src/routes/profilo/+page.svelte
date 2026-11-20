<script lang="ts">
	// Profilo: aspetto dell'app, fonti e licenze. Le uscite e l'account sono in «Uscite».
	import { onMount } from 'svelte';
	import { resolve } from '$app/paths';
	import { t } from '#lib/i18n/index.ts';
	import { getTheme, setTheme, type ThemePref } from '#lib/ui/theme.ts';

	let theme = $state<ThemePref>('auto');
	onMount(() => (theme = getTheme()));

	const OPTIONS: { value: ThemePref; label: string; hint: string }[] = [
		{ value: 'auto', label: 'Automatico', hint: 'come il telefono' },
		{ value: 'light', label: 'Chiaro', hint: 'sempre' },
		{ value: 'dark', label: 'Scuro', hint: 'sempre' }
	];
</script>

<svelte:head><title>{t('nav.profile')} – Cordata</title></svelte:head>

<div class="pagina">
	<h1>{t('nav.profile')}</h1>

	<section aria-labelledby="aspetto">
		<h2 id="aspetto">Aspetto</h2>
		<div class="scelte" role="radiogroup" aria-labelledby="aspetto">
			{#each OPTIONS as o (o.value)}
				<label class:on={theme === o.value}>
					<input
						type="radio"
						name="tema"
						value={o.value}
						checked={theme === o.value}
						onchange={() => {
							theme = o.value;
							setTheme(o.value);
						}}
					/>
					<b>{o.label}</b>
					<span>{o.hint}</span>
				</label>
			{/each}
		</div>
	</section>

	<section aria-labelledby="account">
		<h2 id="account">Account e uscite</h2>
		<p>
			L'accesso con passkey, le uscite di gruppo e le notifiche sono in <a href={resolve('/uscite')}
				>Uscite</a
			>.
		</p>
	</section>

	<section aria-labelledby="dati">
		<h2 id="dati">Dati e licenze</h2>
		<p>
			Cordata usa solo dati aperti: OpenStreetMap, il catasto dei sentieri CAI (INFOMONT) e le
			locandine pubbliche delle sezioni CAI, di cui mostra una sintesi con il link all'originale.
		</p>
		<p><a href={resolve('/fonti')}>{t('nav.sources')}</a></p>
	</section>
</div>

<style>
	h1 {
		font-size: 1.9rem;
		margin: 0.5rem 0 1rem;
	}
	h2 {
		font-size: 1.2rem;
		margin: 1.5rem 0 0.6rem;
	}
	.scelte {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.5rem;
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		padding: 0.75rem;
		border-radius: var(--r-md);
		background: var(--surface);
		border: 1px solid var(--border);
		cursor: pointer;
		min-height: 44px;
	}
	label.on {
		border-color: var(--accent);
		box-shadow: inset 0 0 0 1px var(--accent);
	}
	label span {
		color: var(--muted);
		font-size: 0.82rem;
	}
	input {
		position: absolute;
		opacity: 0;
		pointer-events: none;
	}
	label:has(input:focus-visible) {
		outline: 3px solid var(--rust);
		outline-offset: 2px;
	}
</style>
