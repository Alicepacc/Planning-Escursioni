<script lang="ts">
	import { t } from '#lib/i18n/index.ts';
	import { dataSources } from '#lib/sources.ts';
</script>

<div class="pagina">
	<h1>{t('sources.title')}</h1>
	<p>{t('sources.intro')}</p>

	<ul>
		{#each dataSources as source (source.name)}
			<li>
				<h2><a href={source.url} rel="external noopener">{source.name}</a></h2>
				<p>{source.use}</p>
				<p><strong>{source.license}</strong> · {source.attribution}</p>
			</li>
		{/each}
	</ul>
</div>

<style>
	ul {
		list-style: none;
		padding: 0;
		display: grid;
		gap: 0.75rem;
	}
	li {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 0.75rem 1rem;
	}
	h2 {
		font-size: 1.05rem;
		margin: 0 0 0.25rem;
	}
	p {
		margin: 0.15rem 0;
	}
</style>
