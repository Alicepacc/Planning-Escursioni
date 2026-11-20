<script lang="ts">
	// Data come sul calendario: giorno della settimana, numero grande, mese (ora italiana).
	let { iso }: { iso: string } = $props();
	const d = $derived(new Date(iso));
	const fmt = (o: Intl.DateTimeFormatOptions) =>
		new Intl.DateTimeFormat('it-IT', { timeZone: 'Europe/Rome', ...o }).format(d);
</script>

<span class="data" aria-hidden="true">
	<span>{fmt({ weekday: 'short' })}</span>
	<b>{fmt({ day: 'numeric' })}</b>
	<span>{fmt({ month: 'short' })}</span>
</span>

<style>
	.data {
		flex: none;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		width: 3.4rem;
		height: 3.6rem;
		border-radius: 12px;
		background: var(--brand-soft);
		color: var(--accent);
		font: 600 0.7rem/1.1 var(--font-body);
		text-transform: lowercase;
	}
	b {
		font: 700 1.35rem/1 var(--font-display);
		color: var(--text);
	}
</style>
