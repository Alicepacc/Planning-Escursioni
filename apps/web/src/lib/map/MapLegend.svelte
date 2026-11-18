<script lang="ts">
	// Legenda della mappa (ADR 0012): sempre testo accanto ai colori, mai solo colore.
	import { CAI_SCALES } from '../hiking/difficulty';
	import { ESCURSIONE_COLOR, ESCURSIONE_POINT_COLOR, POI_COLORS } from './style';

	interface Props {
		parts?: ('escursioni' | 'percorso' | 'planner')[];
	}
	let { parts = [] }: Props = $props();
	let open = $state(false);

	const trails = [
		{ color: CAI_SCALES.T.color, label: 'T – turistico' },
		{ color: CAI_SCALES.E.color, label: 'E – escursionistico' },
		{ color: CAI_SCALES.EE.color, label: 'EE – per escursionisti esperti' },
		{ color: CAI_SCALES.EEA.color, label: 'EEA – attrezzato (vie ferrate)' },
		{ color: '#8a5a44', label: 'difficoltà non indicata' }
	];
	const places = [
		{ color: POI_COLORS.rifugio, label: 'rifugio, bivacco' },
		{ color: POI_COLORS.cima, label: 'cima, sella' },
		{ color: POI_COLORS.lago, label: 'lago, sorgente, acqua' },
		{ color: POI_COLORS.panorama, label: 'punto panoramico' },
		{ color: POI_COLORS.parcheggio, label: 'parcheggio' }
	];
</script>

<div class="legenda">
	<button
		type="button"
		class="apri"
		aria-expanded={open}
		aria-controls="legenda-mappa"
		onclick={() => (open = !open)}>{open ? 'Chiudi legenda' : 'Legenda'}</button
	>
	{#if open}
		<div class="pannello" id="legenda-mappa" role="region" aria-label="Legenda della mappa">
			{#if parts.includes('escursioni')}
				<h3>Escursioni</h3>
				<ul>
					<li>
						<svg width="28" height="16" aria-hidden="true"
							><circle
								cx="14"
								cy="8"
								r="6"
								fill={ESCURSIONE_POINT_COLOR}
								stroke="#1f2933"
								stroke-width="2"
							/></svg
						>
						partenza di un'escursione delle sezioni CAI (dalla locandina)
					</li>
				</ul>
			{/if}
			{#if parts.includes('percorso')}
				<h3>Escursione</h3>
				<ul>
					<li>
						<svg width="28" height="10" aria-hidden="true"
							><line x1="2" y1="5" x2="26" y2="5" stroke={ESCURSIONE_COLOR} stroke-width="4" /></svg
						>
						traccia ricostruita e verificata
					</li>
					<li>
						<svg width="28" height="10" aria-hidden="true"
							><line
								x1="2"
								y1="5"
								x2="26"
								y2="5"
								stroke={ESCURSIONE_COLOR}
								stroke-width="4"
								stroke-dasharray="6 4"
							/></svg
						>
						traccia ricostruita, non ancora verificata
					</li>
					<li>
						<svg width="28" height="16" aria-hidden="true"
							><circle cx="14" cy="8" r="7" fill="#1f2933" stroke="#fff" stroke-width="2" /><text
								x="14"
								y="11.5"
								text-anchor="middle"
								font-size="9"
								fill="#fff">1</text
							></svg
						>
						punti chiave della locandina
					</li>
				</ul>
			{/if}
			{#if parts.includes('planner')}
				<h3>Il tuo percorso</h3>
				<ul>
					<li>
						<svg width="28" height="10" aria-hidden="true"
							><line x1="2" y1="5" x2="26" y2="5" stroke="#174ea6" stroke-width="4" /></svg
						>
						sui sentieri
					</li>
					<li>
						<svg width="28" height="10" aria-hidden="true"
							><line
								x1="2"
								y1="5"
								x2="26"
								y2="5"
								stroke="#a85200"
								stroke-width="4"
								stroke-dasharray="6 4"
							/></svg
						>
						a mano libera (fuori dai sentieri noti)
					</li>
					<li>
						<svg width="28" height="10" aria-hidden="true"
							><line x1="2" y1="5" x2="26" y2="5" stroke="#7b2cbf" stroke-width="4" /></svg
						>
						giro composto automaticamente, in anteprima
					</li>
					<li>
						<svg width="28" height="16" aria-hidden="true"
							><circle cx="14" cy="8" r="7" fill="#1f7a3f" stroke="#fff" stroke-width="2" /></svg
						>
						partenza; i punti blu sono intermedi, quello scuro l'arrivo
					</li>
				</ul>
			{/if}
			<h3>Sentieri (catasto CAI e OpenStreetMap)</h3>
			<ul>
				{#each trails as t (t.label)}
					<li>
						<svg width="28" height="10" aria-hidden="true"
							><line x1="2" y1="5" x2="26" y2="5" stroke={t.color} stroke-width="3.5" /></svg
						>
						{t.label}
					</li>
				{/each}
				<li>
					<svg width="28" height="10" aria-hidden="true"
						><line
							x1="2"
							y1="5"
							x2="26"
							y2="5"
							stroke={CAI_SCALES.E.color}
							stroke-width="3.5"
							stroke-dasharray="5 4"
						/></svg
					>
					tratteggio: difficoltà stimata da OpenStreetMap, non dichiarata nel catasto
				</li>
			</ul>
			<p class="nota">Tocca un sentiero per vederne numero, tempi e stato nel catasto.</p>
			<h3>Luoghi</h3>
			<ul>
				{#each places as p (p.label)}
					<li>
						<svg width="28" height="16" aria-hidden="true"
							><circle cx="14" cy="8" r="5" fill={p.color} stroke="#fff" stroke-width="1.5" /></svg
						>
						{p.label}
					</li>
				{/each}
				<li>
					<svg width="28" height="10" aria-hidden="true"
						><line x1="2" y1="5" x2="26" y2="5" stroke="rgb(120, 85, 45)" stroke-width="1" /></svg
					>
					curve di livello, con la quota in metri
				</li>
			</ul>
		</div>
	{/if}
</div>

<style>
	.legenda {
		position: absolute;
		top: 0.6rem;
		left: 0.6rem;
		z-index: 2;
		max-width: min(320px, calc(100% - 4.5rem));
		max-height: calc(100% - 3rem);
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.3rem;
	}
	.apri {
		min-height: 40px;
		padding: 0 0.9rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
		font: inherit;
		font-size: 0.9rem;
		font-weight: 600;
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
		cursor: pointer;
	}
	.pannello {
		overflow-y: auto;
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		border-radius: 12px;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
		padding: 0.4rem 0.8rem 0.6rem;
		font-size: 0.86rem;
	}
	h3 {
		font-size: 0.9rem;
		margin: 0.5rem 0 0.2rem;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.1rem 0;
	}
	svg {
		flex: none;
	}
	.nota {
		margin: 0.3rem 0 0;
		color: var(--muted);
		font-size: 0.8rem;
	}
</style>
