<script lang="ts">
	import { t } from '#lib/i18n/index.ts';
</script>

<h1>{t('home.title')}</h1>
<p>{t('home.status')}</p>
<p class="emergency">{t('safety.emergency')}</p>

<style>
	.emergency {
		font-weight: 600;
	}
</style>
