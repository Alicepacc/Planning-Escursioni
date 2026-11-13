// Rende su mappa le tracce dello spike (reports/phase0/routing-spike/tracks.geojson) e salva
// map.html (autonomo, dati inline) e map.png. Uso: node services/routing/spike/render_map.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const out = resolve(root, 'reports/phase0/routing-spike');
const data = JSON.parse(readFileSync(resolve(out, 'tracks.geojson'), 'utf8'));
const scenario = process.argv[2] ?? 'rado';

const html = `<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<title>Spike routing – Val d'Inferno (${scenario})</title>
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
  html,body,#map{margin:0;height:100%} body{font:14px system-ui,sans-serif}
  #legend{position:absolute;left:12px;top:12px;background:#fffd;padding:10px 12px;border-radius:8px;line-height:1.7}
  #legend i{display:inline-block;width:26px;height:0;border-top:4px solid;margin-right:6px;vertical-align:middle}
</style></head><body><div id="map"></div>
<div id="legend"><b>Fixture #0 – Val d'Inferno e Cima Nassere</b> (scenario «${scenario}»)<br>
<i style="border-color:#1d4ed8"></i>GraphHopper (hike)<br>
<i style="border-color:#ea580c;border-top-style:dashed"></i>BRouter (hiking-mountain)<br>
<i style="border-color:#16a34a66;border-top-width:9px"></i>sentieri citati 332 / 360 / 326 (OSM)<br>
● punti chiave della locandina</div>
<script>
const data = ${JSON.stringify(data)};
const pick = (f) => ({ type: 'FeatureCollection', features: data.features.filter(f) });
const map = new maplibregl.Map({ container: 'map', style: 'https://tiles.openfreemap.org/styles/liberty',
  center: [11.542, 46.153], zoom: 13.2, attributionControl: { compact: false } });
map.on('load', () => {
  map.addSource('cited', { type: 'geojson', data: pick((f) => f.properties.kind === 'cited_trail') });
  map.addLayer({ id: 'cited', type: 'line', source: 'cited', paint: { 'line-color': '#16a34a', 'line-opacity': 0.4, 'line-width': 10 } });
  const route = (engine) => pick((f) => f.properties.engine === engine && f.properties.scenario === '${scenario}' && !f.properties.variant.includes('max') && !f.properties.variant.includes('preferenza'));
  map.addSource('gh', { type: 'geojson', data: route('graphhopper') });
  map.addLayer({ id: 'gh', type: 'line', source: 'gh', paint: { 'line-color': '#1d4ed8', 'line-width': 4 } });
  map.addSource('br', { type: 'geojson', data: route('brouter') });
  map.addLayer({ id: 'br', type: 'line', source: 'br', paint: { 'line-color': '#ea580c', 'line-width': 2.5, 'line-dasharray': [2, 1.5] } });
  map.addSource('wp', { type: 'geojson', data: pick((f) => f.properties.kind === 'waypoint') });
  map.addLayer({ id: 'wp', type: 'circle', source: 'wp', paint: { 'circle-radius': 6, 'circle-color': '#111', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
  map.addLayer({ id: 'wp-label', type: 'symbol', source: 'wp', layout: { 'text-field': ['get', 'nome'], 'text-size': 13, 'text-offset': [0, 1.1], 'text-anchor': 'top', 'text-font': ['Noto Sans Bold'] }, paint: { 'text-halo-color': '#fff', 'text-halo-width': 2 } });
  map.once('idle', () => { window.__ready = true; });
});
</script></body></html>`;

writeFileSync(resolve(out, `map-${scenario}.html`), html);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 1000 }, deviceScaleFactor: 1 });
page.on('console', (m) => { if (m.type() === 'error') console.error('console:', m.text()); });
await page.setContent(html, { waitUntil: 'load' });
await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 }).catch(() => console.error('timeout: mappa non pronta'));
await page.waitForTimeout(1500);
await page.screenshot({ path: resolve(out, `map-${scenario}.png`) });
await browser.close();
console.log('ok', resolve(out, `map-${scenario}.png`));
