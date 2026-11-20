<script lang="ts">
	// Pannello dei filtri di Esplora (SPEC §5.1). Modifica direttamente i filtri della pagina.
	import {
		EMPTY_FILTERS,
		MONTHS,
		TAG_LABEL,
		TYPE_LABEL,
		type Difficulty,
		type Filters,
		type RouteType,
		type Tag
	} from '../search/explore';

	interface Props {
		filters: Filters;
		count: number;
		/** sezioni organizzatrici presenti nell'indice */
		sections?: string[];
		onclose: () => void;
	}
	let { filters = $bindable(), count, sections = [], onclose }: Props = $props();

	const DIFFS: Difficulty[] = ['T', 'E', 'EE', 'EEA', 'EAI'];
	const HOURS = [1, 2, 3, 4, 5, 6, 7, 8, 10];
	let locating = $state(false);
	let geoError = $state('');

	function toggle<T>(list: T[], value: T): T[] {
		return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
	}
	function num(value: string): number | null {
		return value === '' ? null : Number(value);
	}
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
				filters = {
					...filters,
					near: {
						lon: pos.coords.longitude,
						lat: pos.coords.latitude,
						label: 'te',
						km: filters.near?.km ?? 20
					}
				};
			},
			() => {
				locating = false;
				geoError = 'Non riesco a leggere la posizione (permesso negato o segnale assente).';
			},
			{ enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
		);
	}
</script>

<div class="pannello" role="dialog" aria-modal="true" aria-label="Filtri">
	<header>
		<h2>Filtri</h2>
		<button type="button" class="chiudi" onclick={onclose} aria-label="Chiudi">✕</button>
	</header>

	<div class="corpo">
		<fieldset>
			<legend>Tempo (senza soste)</legend>
			<label
				>da <select
					value={filters.minMinutes ?? ''}
					onchange={(e) => (filters = { ...filters, minMinutes: num(e.currentTarget.value) })}
				>
					<option value="">–</option>
					{#each HOURS as h (h)}<option value={h * 60}>{h} h</option>{/each}
				</select></label
			>
			<label
				>a <select
					value={filters.maxMinutes ?? ''}
					onchange={(e) => (filters = { ...filters, maxMinutes: num(e.currentTarget.value) })}
				>
					<option value="">–</option>
					{#each HOURS as h (h)}<option value={h * 60}>{h} h</option>{/each}
					<option value={210}>3:30 h</option>
					<option value={150}>2:30 h</option>
				</select></label
			>
		</fieldset>

		<fieldset>
			<legend>Lunghezza (km)</legend>
			<label
				>da <input
					type="number"
					min="0"
					inputmode="decimal"
					value={filters.minKm ?? ''}
					onchange={(e) => (filters = { ...filters, minKm: num(e.currentTarget.value) })}
				/></label
			>
			<label
				>a <input
					type="number"
					min="0"
					inputmode="decimal"
					value={filters.maxKm ?? ''}
					onchange={(e) => (filters = { ...filters, maxKm: num(e.currentTarget.value) })}
				/></label
			>
		</fieldset>

		<fieldset>
			<legend>Dislivello in salita (m)</legend>
			<label
				>da <input
					type="number"
					min="0"
					step="50"
					inputmode="numeric"
					value={filters.minUp ?? ''}
					onchange={(e) => (filters = { ...filters, minUp: num(e.currentTarget.value) })}
				/></label
			>
			<label
				>a <input
					type="number"
					min="0"
					step="50"
					inputmode="numeric"
					value={filters.maxUp ?? ''}
					onchange={(e) => (filters = { ...filters, maxUp: num(e.currentTarget.value) })}
				/></label
			>
		</fieldset>

		<fieldset>
			<legend>Quota massima (m)</legend>
			<label
				>da <input
					type="number"
					min="0"
					step="100"
					inputmode="numeric"
					value={filters.minEle ?? ''}
					onchange={(e) => (filters = { ...filters, minEle: num(e.currentTarget.value) })}
				/></label
			>
			<label
				>a <input
					type="number"
					min="0"
					step="100"
					inputmode="numeric"
					value={filters.maxEle ?? ''}
					onchange={(e) => (filters = { ...filters, maxEle: num(e.currentTarget.value) })}
				/></label
			>
		</fieldset>

		<fieldset>
			<legend>Difficoltà CAI</legend>
			<div class="toggle">
				{#each DIFFS as dif (dif)}
					<button
						type="button"
						aria-pressed={filters.difficulties.includes(dif)}
						onclick={() =>
							(filters = { ...filters, difficulties: toggle(filters.difficulties, dif) })}
						>{dif}</button
					>
				{/each}
			</div>
		</fieldset>

		<fieldset>
			<legend>Tipo</legend>
			<div class="toggle">
				{#each Object.entries(TYPE_LABEL) as [t, label] (t)}
					<button
						type="button"
						aria-pressed={filters.types.includes(t as RouteType)}
						onclick={() => (filters = { ...filters, types: toggle(filters.types, t as RouteType) })}
						>{label}</button
					>
				{/each}
			</div>
		</fieldset>

		<fieldset>
			<legend>Lungo il percorso</legend>
			<div class="toggle">
				{#each Object.entries(TAG_LABEL) as [t, label] (t)}
					<button
						type="button"
						aria-pressed={filters.tags.includes(t as Tag)}
						onclick={() => (filters = { ...filters, tags: toggle(filters.tags, t as Tag) })}
						>{label}</button
					>
				{/each}
			</div>
		</fieldset>

		<fieldset>
			<legend>Stagione consigliata (indicativa)</legend>
			<select
				value={filters.month ?? ''}
				onchange={(e) => (filters = { ...filters, month: num(e.currentTarget.value) })}
			>
				<option value="">qualsiasi mese</option>
				{#each MONTHS as m, i (m)}<option value={i + 1}>{m}</option>{/each}
			</select>
		</fieldset>

		<fieldset>
			<legend>Distanza da me</legend>
			<div class="riga">
				<button type="button" onclick={locate} disabled={locating}
					>{locating
						? 'Cerco…'
						: filters.near?.label === 'te'
							? 'Aggiorna posizione'
							: 'Usa la mia posizione'}</button
				>
				{#if filters.near}
					<label
						>entro <select
							value={filters.near.km}
							onchange={(e) =>
								(filters = {
									...filters,
									near: filters.near && { ...filters.near, km: Number(e.currentTarget.value) }
								})}
						>
							{#each [5, 10, 20, 30, 50, 80] as k (k)}<option value={k}>{k} km</option>{/each}
						</select></label
					>
					<span class="nota">da {filters.near.label}</span>
				{/if}
			</div>
			{#if geoError}<p class="nota">{geoError}</p>{/if}
		</fieldset>

		<fieldset>
			<legend>Sezione</legend>
			<div class="toggle">
				{#each sections as s (s)}
					<button
						type="button"
						aria-pressed={filters.sections.includes(s)}
						onclick={() => (filters = { ...filters, sections: toggle(filters.sections, s) })}
						>{s}</button
					>
				{/each}
			</div>
			<label class="check"
				><input
					type="checkbox"
					checked={filters.futureOnly}
					onchange={(e) => (filters = { ...filters, futureOnly: e.currentTarget.checked })}
				/> solo attività in programma (con data futura)</label
			>
			<p class="nota">Raggiungibile con i mezzi pubblici: in una fase successiva.</p>
		</fieldset>
	</div>

	<footer>
		<button
			type="button"
			class="secondario"
			onclick={() => (filters = { ...EMPTY_FILTERS, area: filters.area })}>Azzera</button
		>
		<button type="button" class="primario" onclick={onclose}>Mostra {count} risultati</button>
	</footer>
</div>

<style>
	.pannello {
		position: fixed;
		inset: auto 0 0 0;
		max-height: 88dvh;
		background: var(--surface);
		border-top-left-radius: 16px;
		border-top-right-radius: 16px;
		box-shadow: 0 -8px 30px rgba(0, 0, 0, 0.25);
		z-index: 50;
		display: flex;
		flex-direction: column;
	}
	@media (min-width: 900px) {
		.pannello {
			inset: 4rem auto 1rem 1rem;
			width: 380px;
			max-height: none;
			border-radius: 16px;
		}
	}
	header,
	footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.6rem 1rem;
		border-bottom: 1px solid var(--border);
	}
	footer {
		border-top: 1px solid var(--border);
		border-bottom: none;
		gap: 0.75rem;
		padding-bottom: calc(0.6rem + env(safe-area-inset-bottom));
	}
	h2 {
		margin: 0;
		font-size: 1.1rem;
	}
	.corpo {
		overflow-y: auto;
		padding: 0.25rem 1rem 1rem;
	}
	fieldset {
		border: none;
		padding: 0;
		margin: 0.75rem 0 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}
	legend {
		font-weight: 700;
		margin-bottom: 0.35rem;
		padding: 0;
	}
	input[type='number'] {
		width: 6rem;
	}
	input,
	select,
	button {
		font: inherit;
		min-height: 44px;
	}
	.toggle,
	.riga {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
	}
	.toggle button,
	.riga button,
	footer button,
	.chiudi {
		border: 1px solid var(--border);
		background: var(--surface);
		color: inherit;
		border-radius: 999px;
		padding: 0 0.9rem;
		cursor: pointer;
	}
	.toggle button[aria-pressed='true'] {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--on-accent);
	}
	.primario {
		background: var(--accent) !important;
		border-color: var(--accent) !important;
		color: var(--on-accent);
		font-weight: 700;
		flex: 1;
	}
	.check {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		width: 100%;
	}
	.check input {
		min-height: auto;
		width: 1.2rem;
		height: 1.2rem;
	}
	.nota {
		color: var(--muted);
		font-size: 0.85rem;
		margin: 0.2rem 0 0;
		width: 100%;
	}
</style>
