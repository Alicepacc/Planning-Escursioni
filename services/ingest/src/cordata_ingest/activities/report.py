# ruff: noqa: E501  (modulo di modelli HTML/CSS: righe lunghe volute)
"""Rapporto del pilota (SPEC §7.6): `reports/pilot-AAAA-MM-GG/pilot.html`.

Pagina autonoma: per ogni attività il link alla locandina originale (mai ripubblicata), i campi
estratti dal parser con confidenza e fonte accanto ai valori rivisti, il confronto dichiarato /
calcolato, la traccia (SVG sempre visibile, mappa interattiva se c'è rete), il profilo, i punti
geocodificati e lo stato con i motivi. Nessun dato personale: le citazioni con segnaposto di
dati rimossi non vengono mostrate.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import yaml

from ..config import data_dir, repo_root
from .evaluate import FIELDS
from .pilot import FIXTURE_ID, activities, tracks_dir

STATUS_LABEL = {"auto_ok": "auto_ok", "da_rivedere": "da rivedere", "fallita": "fallita"}
FIELD_LABEL = {
    "titolo": "Titolo",
    "data": "Data",
    "difficolta": "Difficoltà",
    "tipo_percorso": "Tipo di percorso",
    "durata": "Durata dichiarata",
    "distanza_km": "Distanza (km)",
    "salita_m": "Salita (m)",
    "discesa_m": "Discesa (m)",
    "quota_max_m": "Quota massima (m)",
    "partenza_nome": "Partenza",
    "partenza_quota_m": "Quota partenza (m)",
    "arrivo_nome": "Arrivo",
    "ora_ritrovo": "Ora di ritrovo",
    "mezzi": "Mezzi",
    "quota_eur": "Quota (€)",
    "sentieri": "Sentieri citati",
    "punti_chiave": "Punti chiave",
}


def e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _fmt(value: Any) -> str:
    if value is None or value == []:
        return "—"
    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            return ", ".join(
                f"{p['nome']}" + (f" ({p['quota_m']:.0f})" if p.get("quota_m") else "")
                for p in value
            )
        return ", ".join(str(v) for v in value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _safe_source(text: str) -> str:
    if not text or "rimoss" in text:
        return "" if not text else "(riga con dati personali rimossi: non mostrata)"
    return text


def _simplify(coords: list[list[float]], max_points: int = 400) -> list[list[float]]:
    if len(coords) <= max_points:
        return coords
    step = math.ceil(len(coords) / max_points)
    return [*coords[::step], coords[-1]]


def svg_track(
    coords: list[list[float]], points: list[dict[str, Any]], w: int = 340, h: int = 260
) -> str:
    pts = [(p["lon"], p["lat"]) for p in points if p.get("lon") is not None]
    allc = [(c[0], c[1]) for c in coords] + pts
    if not allc:
        return '<p class="muted">Nessuna traccia.</p>'
    lons, lats = [c[0] for c in allc], [c[1] for c in allc]
    lat0 = sum(lats) / len(lats)
    kx = math.cos(math.radians(lat0))
    minx, maxx = min(lons) * kx, max(lons) * kx
    miny, maxy = min(lats), max(lats)
    span = max(maxx - minx, maxy - miny, 1e-4)
    pad = 14
    s = (min(w, h) - 2 * pad) / span

    def xy(lon: float, lat: float) -> tuple[float, float]:
        x = pad + (lon * kx - minx) * s + ((w - 2 * pad) - (maxx - minx) * s) / 2
        y = pad + (maxy - lat) * s + ((h - 2 * pad) - (maxy - miny) * s) / 2
        return round(x, 1), round(y, 1)

    path = " ".join(f"{x},{y}" for x, y in (xy(c[0], c[1]) for c in coords))
    marks = []
    for i, p in enumerate(points, 1):
        if p.get("lon") is None:
            continue
        x, y = xy(p["lon"], p["lat"])
        marks.append(
            f'<g><circle cx="{x}" cy="{y}" r="7" class="pt"/><text x="{x}" y="{y + 3.5}" '
            f'class="ptn">{i}</text><title>{i}. {e(p["nome"])} → {e(p.get("trovato"))}</title></g>'
        )
    bar_km = 1 if span * 111 < 8 else 2 if span * 111 < 16 else 5
    bar_px = bar_km / 111 * s
    return (
        f'<svg viewBox="0 0 {w} {h}" class="trk" role="img" aria-label="Traccia ricostruita">'
        f'<polyline points="{path}" class="line-halo"/><polyline points="{path}" class="line"/>'
        + "".join(marks)
        + f'<line x1="{pad}" y1="{h - 8}" x2="{pad + bar_px:.1f}" y2="{h - 8}" class="bar"/>'
        f'<text x="{pad}" y="{h - 12}" class="bart">{bar_km} km</text></svg>'
    )


def svg_profile(profile: list[list[float]], w: int = 340, h: int = 140) -> str:
    if len(profile) < 2:
        return ""
    d = [p[0] / 1000 for p in profile]
    z = [p[1] for p in profile]
    zmin, zmax = min(z), max(z)
    zr = max(zmax - zmin, 50)
    left, bottom, top = 36, 18, 8

    def xy(di: float, zi: float) -> tuple[float, float]:
        x = left + (di / d[-1]) * (w - left - 6) if d[-1] else left
        y = top + (zmax - zi) / zr * (h - top - bottom)
        return round(x, 1), round(y, 1)

    line = " ".join(f"{x},{y}" for x, y in (xy(a, b) for a, b in zip(d, z, strict=True)))
    x0, _ = xy(0, zmin)
    x1, _ = xy(d[-1], zmin)
    area = f"{x0},{h - bottom} {line} {x1},{h - bottom}"
    return (
        f'<svg viewBox="0 0 {w} {h}" class="prof" role="img" aria-label="Profilo altimetrico">'
        f'<polygon points="{area}" class="area"/><polyline points="{line}" class="pl"/>'
        f'<text x="2" y="{top + 8}" class="ax">{zmax:.0f} m</text>'
        f'<text x="2" y="{h - bottom}" class="ax">{zmin:.0f} m</text>'
        f'<text x="{w - 6}" y="{h - 4}" class="ax" text-anchor="end">{d[-1]:.1f} km</text></svg>'
    )


def _compare_rows(t: dict[str, Any]) -> str:
    d, c, k = t["declared"], t["computed"], t["checks"]
    rows = []

    def row(label: str, dv: Any, cv: Any, check: dict[str, Any] | None, unit: str = "") -> None:
        if check is None:
            verdict = '<span class="muted">non confrontabile</span>'
        else:
            delta = (
                f"{check['scarto']:+.0%}"
                if "scarto" in check
                else f"{check.get('scarto_m', 0):+d} m"
            )
            verdict = f'<span class="{"ok" if check["ok"] else "ko"}">{"✓" if check["ok"] else "✗"} {delta}</span>'
        rows.append(
            f"<tr><td>{label}</td><td>{e(_fmt(dv))}{unit}</td><td>{e(_fmt(cv))}{unit}</td><td>{verdict}</td></tr>"
        )

    row("Distanza", d.get("distanza_km"), c.get("distanza_km"), k.get("distanza"), " km")
    row("Salita", d.get("salita_m"), c.get("salita_m"), k.get("salita"), " m")
    row("Discesa", d.get("discesa_m"), c.get("discesa_m"), None, " m")
    row("Quota massima", d.get("quota_max_m"), c.get("quota_max_m"), k.get("quota_max"), " m")
    mins = c.get("minuti_cai")
    calc_time = f"{int(mins // 60)}:{int(mins % 60):02d}" if mins else None
    rows.append(
        f"<tr><td>Tempo</td><td>{e(_fmt(d.get('durata')))}</td><td>{e(calc_time or '—')} "
        f'<span class="muted">(modello CAI, senza soste)</span></td><td></td></tr>'
    )
    if "anello_chiuso" in k:
        a = k["anello_chiuso"]
        rows.append(
            f"<tr><td>Chiusura dell'anello</td><td>inizio = fine</td><td>{a['distanza_m']} m</td>"
            f'<td><span class="{"ok" if a["ok"] else "ko"}">{"✓" if a["ok"] else "✗"}</span></td></tr>'
        )
    return "".join(rows)


def _fields_rows(parsed: dict[str, Any] | None) -> str:
    if not parsed:
        return '<tr><td colspan="5" class="muted">Fixture fornita dall\'utente: nessun PDF pubblico da analizzare.</td></tr>'
    out = []
    for f in FIELDS:
        if f not in parsed:
            continue
        r = parsed[f]
        ok = r["corretto"]
        extracted = r["value"] not in (None, [])
        verdict = (
            '<span class="ok">✓</span>'
            if ok and (extracted or r["verita"] in (None, []))
            else '<span class="ko">✗</span>'
            if extracted
            else '<span class="warn">mancante</span>'
        )
        if not extracted and r["verita"] in (None, []):
            verdict = '<span class="muted">assente</span>'
        conf = f"{r['confidence']:.2f}" if extracted else ""
        out.append(
            f"<tr><td>{FIELD_LABEL.get(f, f)}</td><td>{e(_fmt(r['value']))}"
            f'<span class="conf">{conf}</span></td><td>{e(_fmt(r["verita"]))}</td><td>{verdict}</td>'
            f'<td class="src">{e(_safe_source(r.get("source", "")))}</td></tr>'
        )
    return "".join(out)


def _points_rows(points: list[dict[str, Any]]) -> str:
    out = []
    for i, p in enumerate(points, 1):
        q = p.get("quota_osm") or p.get("quota_dem")
        out.append(
            f"<tr><td>{i}</td><td>{e(p['nome'])}</td><td>{e(p.get('trovato') or '— non trovato')}</td>"
            f"<td>{e(p.get('tipo') or '')}</td><td>{e(_fmt(p.get('quota_dichiarata')))}</td>"
            f"<td>{e(_fmt(round(q) if q else None))}</td></tr>"
        )
    return "".join(out)


def build(report_dir: Path, date: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((data_dir() / "activities" / "raw" / "manifest.json").read_text("utf-8"))
    candidates = {
        c["id"]: c
        for c in yaml.safe_load(
            (repo_root() / "config" / "pilot" / "candidates.yaml").read_text("utf-8")
        )["candidates"]
    }
    parsed_dir = data_dir() / "activities" / "parsed"
    parser_tracks = tracks_dir("parser")
    cards, toc, geo = [], [], {}
    counts: dict[str, int] = {}
    for n, (aid, act) in enumerate(activities().items()):
        t = json.loads((tracks_dir() / f"{aid}.json").read_text("utf-8"))
        parsed_path = parsed_dir / f"{aid}.json"
        parsed = json.loads(parsed_path.read_text("utf-8")) if parsed_path.exists() else None
        pt_path = parser_tracks / f"{aid}.json"
        parser_status = (
            json.loads(pt_path.read_text("utf-8"))["status"] if pt_path.exists() else None
        )
        doc_id = act.get("documento", aid)
        if aid != FIXTURE_ID:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
        url = manifest.get(doc_id, {}).get("url") or candidates.get(doc_id, {}).get("url")
        page = f" (pagina {act['pagina']})" if act.get("pagina") else ""
        link = (
            f'<a href="{e(url)}" rel="noopener" target="_blank">Locandina originale sul sito della sezione{page}</a>'
            if url
            else '<span class="muted">Locandina fornita dall\'utente (SPEC §2), non pubblica</span>'
        )
        coords = _simplify(t["coords"])
        geo[aid] = {
            "coords": coords,
            "points": [
                {"n": i, "nome": p["nome"], "lon": p["lon"], "lat": p["lat"]}
                for i, p in enumerate(t["points"], 1)
                if p.get("lon") is not None
            ],
        }
        reasons = [r for r in t["reasons"] if not r.startswith("nota:")]
        notes = [r[6:] for r in t["reasons"] if r.startswith("nota:")]
        label = "#0 (fixture)" if aid == FIXTURE_ID else f"#{n}"
        title = act.get("titolo", aid)
        badge = f'<span class="badge {t["status"]}">{STATUS_LABEL[t["status"]]}</span>'
        toc.append(
            f'<li><a href="#{e(aid)}">{label} {e(title)}</a> <span class="muted">{e(act.get("sezione"))}</span> {badge}</li>'
        )
        meta = " · ".join(
            x
            for x in [
                e(act.get("sezione")),
                e(act.get("data") or "senza data"),
                e(act.get("tipo_percorso")),
                e(act.get("difficolta") or act.get("difficolta_testo") or "difficoltà n.d."),
                e(act.get("zona")),
            ]
            if x
        )
        share = t.get("on_cited_share")
        cited = (
            f"Sentieri citati: {e(', '.join(t['cited_refs']) or '—')}; trovati: "
            f"{e(', '.join(str(x) for x in t['cited_found']) or '—')}"
            + (f"; traccia sui citati: {share:.0%}" if share is not None else "")
        )
        cards.append(
            f"""
<section class="card" id="{e(aid)}">
  <header><h2>{label} {e(title)} {badge}</h2><p class="meta">{meta}</p><p>{link}</p></header>
  {"<ul class='reasons'>" + "".join(f"<li>{e(r)}</li>" for r in reasons) + "</ul>" if reasons else "<p class='ok'>Tutti i controlli superati.</p>"}
  {"<p class='muted small'>Note: " + e("; ".join(notes)) + "</p>" if notes else ""}
  <div class="grid">
    <figure><div class="map" data-id="{e(aid)}">{svg_track(coords, t["points"])}</div>
      <figcaption>Traccia ricostruita e punti chiave numerati. {cited}</figcaption></figure>
    <figure>{svg_profile(t["profile"])}<figcaption>Profilo sul DEM (Mapterhorn). Ricostruzione in {t.get("seconds")} s.</figcaption>
      <table class="cmp"><thead><tr><th></th><th>Dichiarato</th><th>Calcolato</th><th>Esito</th></tr></thead>
      <tbody>{_compare_rows(t)}</tbody></table></figure>
  </div>
  <details><summary>Campi estratti: parser a regole contro revisione</summary>
    <table class="fields"><thead><tr><th>Campo</th><th>Parser (confidenza)</th><th>Rivisto</th><th>Esito</th><th>Fonte nel PDF</th></tr></thead>
    <tbody>{_fields_rows(parsed)}</tbody></table>
    {f"<p class='muted small'>Con i soli campi del parser la ricostruzione sarebbe: {STATUS_LABEL.get(parser_status, parser_status)}.</p>" if parser_status else ""}
  </details>
  <details><summary>Punti chiave geocodificati ({sum(1 for p in t["points"] if p.get("trovato"))}/{len(t["points"])})</summary>
    <table class="pts"><thead><tr><th>#</th><th>Nella locandina</th><th>Trovato in OSM</th><th>Tipo</th><th>Quota dichiarata</th><th>Quota OSM/DEM</th></tr></thead>
    <tbody>{_points_rows(t["points"])}</tbody></table>
  </details>
</section>"""
        )
    summary = " · ".join(f"{STATUS_LABEL[k]}: {v}" for k, v in sorted(counts.items()))
    page = TEMPLATE.format(
        date=e(date),
        summary=e(summary),
        toc="".join(toc),
        cards="".join(cards),
        geo=json.dumps(geo, separators=(",", ":")),
    )
    out = report_dir / "pilot.html"
    out.write_text(page, encoding="utf-8")
    return out


TEMPLATE = """<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pilota attività CAI</title>
<meta name="description" content="Cordata, Fase 2: 20 attività CAI estratte e ricostruite, {date}">
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css">
<style>
:root{{--bg:#f6f4ef;--fg:#1f2933;--card:#fff;--muted:#5f6b76;--line:#d9d4c7;--ok:#1f7a3a;--ko:#b3261e;--warn:#9a6700;--acc:#c0392b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#15191d;--fg:#e8e6e1;--card:#1e2328;--muted:#a3adb7;--line:#39424b;--ok:#6fcf8a;--ko:#ff8a80;--warn:#e0b54a;--acc:#ff7a6b}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:16px}}h1{{font-size:1.6rem;margin:.2em 0}}h2{{font-size:1.15rem;margin:0}}
a{{color:var(--acc)}}.muted{{color:var(--muted)}}.small{{font-size:.85rem}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:16px 0}}
.meta{{color:var(--muted);margin:.3em 0}}.badge{{font-size:.75rem;padding:2px 8px;border-radius:99px;vertical-align:middle;font-weight:600;white-space:nowrap}}
.badge.auto_ok{{background:#d8f0de;color:#145a2a}}.badge.da_rivedere{{background:#fdeccc;color:#7a4b00}}.badge.fallita{{background:#fbd9d6;color:#8c1d16}}
.ok{{color:var(--ok)}}.ko{{color:var(--ko)}}.warn{{color:var(--warn)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}@media (max-width:760px){{.grid{{grid-template-columns:1fr}}}}
figure{{margin:0}}figcaption{{font-size:.85rem;color:var(--muted);margin-top:4px}}
.map{{position:relative;min-height:260px;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#ece8de}}
@media (prefers-color-scheme:dark){{.map{{background:#2a3036}}}}
.trk{{width:100%;height:auto;display:block}}.line{{fill:none;stroke:var(--acc);stroke-width:3;stroke-linejoin:round}}
.line-halo{{fill:none;stroke:#fff;stroke-width:6;opacity:.8}}.pt{{fill:#1f2933;stroke:#fff;stroke-width:1.5}}
.ptn{{fill:#fff;font:700 9px system-ui;text-anchor:middle}}.bar{{stroke:var(--fg);stroke-width:2}}.bart{{fill:var(--fg);font-size:10px}}
.prof{{width:100%;height:auto}}.area{{fill:var(--acc);opacity:.18}}.pl{{fill:none;stroke:var(--acc);stroke-width:2}}.ax{{fill:var(--muted);font-size:10px}}
table{{width:100%;border-collapse:collapse;font-size:.88rem;margin-top:8px}}th,td{{text-align:left;padding:4px 6px;border-bottom:1px solid var(--line);vertical-align:top}}
.conf{{color:var(--muted);font-size:.75rem;margin-left:6px}}.src{{color:var(--muted);font-size:.8rem}}
details{{margin-top:10px}}summary{{cursor:pointer;font-weight:600}}.reasons{{margin:.4em 0;padding-left:1.2em}}
.toc li{{margin:2px 0}}.table-wrap{{overflow-x:auto}}footer{{color:var(--muted);font-size:.85rem;margin:24px 0}}
.btn{{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:6px 12px;cursor:pointer}}
</style></head><body><main>
<p class="muted">Cordata · Fase 2 · {date}</p>
<h1>Pilota: 20 attività CAI dalle locandine alla traccia</h1>
<p>Per ogni attività: locandina originale (link alla sezione, il PDF non è ripubblicato), campi estratti, traccia ricostruita su OSM/OSM2CAI, profilo, confronto tra dati dichiarati e calcolati, stato. Metriche complete in <code>metrics.md</code>, problemi e proposte in <code>decisions.md</code>.</p>
<p><strong>{summary}</strong> (la fixture #0 è fuori conteggio)</p>
<p><button class="btn" id="mappe">Carica le mappe interattive</button> <span class="muted small">(richiede la rete: MapLibre e OpenFreeMap; senza, resta lo schema della traccia)</span></p>
<ol class="toc">{toc}</ol>
{cards}
<footer>Tracce calcolate con GraphHopper su dati © OpenStreetMap contributors e OSM2CAI (CAI), licenza ODbL; quote: Mapterhorn (LiDAR PAT, TINITALY, Copernicus GLO-30); mappa di base: OpenFreeMap. Le locandine appartengono alle sezioni: qui solo sintesi, link e data, come da risposta del CAI (docs/legal). Nessun dato personale di capigita o accompagnatori.</footer>
</main>
<script>
const GEO = {geo};
document.getElementById('mappe').addEventListener('click', () => {{
  const s = document.createElement('script');
  s.src = 'https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js';
  s.onload = () => document.querySelectorAll('.map').forEach(el => {{
    const g = GEO[el.dataset.id]; if (!g || !g.coords.length) return;
    el.innerHTML = '';
    el.style.height = '320px';
    const map = new maplibregl.Map({{container: el, style: 'https://tiles.openfreemap.org/styles/liberty', attributionControl: {{compact: true}}}});
    const b = g.coords.reduce((b, c) => b.extend(c), new maplibregl.LngLatBounds(g.coords[0], g.coords[0]));
    map.fitBounds(b, {{padding: 30, duration: 0}});
    map.on('load', () => {{
      map.addSource('t', {{type: 'geojson', data: {{type: 'Feature', geometry: {{type: 'LineString', coordinates: g.coords}}}}}});
      map.addLayer({{id: 'h', type: 'line', source: 't', paint: {{'line-color': '#fff', 'line-width': 7}}}});
      map.addLayer({{id: 'l', type: 'line', source: 't', paint: {{'line-color': '#c0392b', 'line-width': 4}}}});
      g.points.forEach(p => new maplibregl.Marker({{color: '#1f2933', scale: .6}}).setLngLat([p.lon, p.lat]).setPopup(new maplibregl.Popup().setText(p.n + '. ' + p.nome)).addTo(map));
    }});
  }});
  s.onerror = () => alert('Mappe interattive non disponibili senza rete.');
  document.head.appendChild(s);
}}, {{once: true}});
</script></body></html>
"""
