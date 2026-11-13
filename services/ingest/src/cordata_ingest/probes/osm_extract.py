"""Estratto OpenStreetMap: disponibilità dei mirror e copertura dei tag nell'area Lagorai.

Tre controlli distinti:

1. dove si può scaricare l'estratto `.osm.pbf` rispettando robots.txt (Geofabrik, OSM-FR,
   Estratti OSM Italia di Wikimedia Italia);
2. un campione piccolo scaricato davvero (il comune di Scurelle, quello della fixture);
3. l'analisi con pyosmium dell'estratto regionale già presente in `data/osm/`: relazioni
   `route=hiking`, sentieri, POI e i punti chiave della fixture "Val d'Inferno".

L'estratto regionale non viene scaricato dallo script (oltre 100 MB): se manca, il controllo
fallisce spiegando come ottenerlo.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..config import Area, areas, data_dir
from ..http import Fetched, FetchError
from .base import STATUS_BLOCKED, STATUS_OK, STATUS_PARTIAL, ProbeContext, ProbeResult

PROBE_ID = "osm_extract"

GEOFABRIK = "https://download.geofabrik.de"
OSMFR = "https://download.openstreetmap.fr"
OSMFR_ITALY = f"{OSMFR}/extracts/europe/italy"
OSMIT = "https://osmit-estratti.wmcloud.org"
OSMIT_PBF = f"{OSMIT}/output/pbf"
OSMIT_SAMPLE = "comuni/022171_Scurelle.osm.pbf"

REL_TAGS = (
    "ref",
    "name",
    "cai_scale",
    "ref:REI",
    "reg_ref",
    "osmc:symbol",
    "from",
    "to",
    "distance",
    "ascent",
    "descent",
    "duration:forward",
    "duration:backward",
    "network",
    "operator",
    "source",
    "website",
)
WAY_TAGS = ("sac_scale", "trail_visibility", "surface", "tracktype", "name", "foot", "informal")
POI_TAGS = ("name", "name:it", "name:de", "ele")
HIGHWAY_FOOT = ("path", "track", "footway", "steps", "bridleway", "via_ferrata")
NAME_KEYS = ("name", "name:it", "name:de", "alt_name", "loc_name", "official_name", "old_name")

# punti chiave della fixture golden: (etichetta, alternative di parole da trovare nel nome, quota)
FIXTURE_TARGETS: tuple[tuple[str, tuple[tuple[str, ...], ...], int | None], ...] = (
    ("Parcheggio Tedon", (("tedon",),), 1350),
    ("Strada forestale Campivelo", (("campivelo",),), None),
    ("Piana Caldenave", (("piana", "caldenave"),), 1752),
    ("Rifugio Claudio e Renzo", (("claudio", "renzo"),), None),
    ("Laghi della Val d'Inferno", (("laghi", "inferno"),), 1950),
    ("Lago Nassere", (("lago", "nassere"), ("nassare",)), None),
    ("Cima Nassere", (("cima", "nassere"),), 2253),
    ("Laghetto del Cengello", (("laghetto", "cengello"),), 1985),
    ("Cucuzzolo dei Morti", (("cucuzzolo", "morti"), ("cocuzzolo", "morti")), 1924),
    ("Malga Conseria", (("malga", "conseria"),), 1848),
    ("Ponte Conseria", (("ponte", "conseria"),), 1460),
)
FIXTURE_REFS = ("332", "360", "326")
FIXTURE_NETWORKS = {
    "Alta Via del Granito": "alta via del granito",
    "Sentiero della Pace": "sentiero della pace",
    "Translagorai": "translagorai",
}


def norm(text: str | None) -> str:
    """Minuscolo senza accenti, per confrontare toponimi (Consèria = Conseria)."""
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", plain.lower()).strip()


def poi_kinds(tags: dict[str, str]) -> list[str]:
    kinds = []
    if tags.get("tourism") == "alpine_hut":
        kinds.append("rifugio (tourism=alpine_hut)")
    if tags.get("tourism") == "wilderness_hut":
        kinds.append("bivacco (tourism=wilderness_hut)")
    if tags.get("amenity") == "shelter":
        kinds.append("riparo (amenity=shelter)")
    if tags.get("natural") == "peak":
        kinds.append("cima (natural=peak)")
    if tags.get("natural") == "saddle" or tags.get("mountain_pass") == "yes":
        kinds.append("sella (natural=saddle / mountain_pass)")
    if tags.get("natural") == "water":
        kinds.append("lago / specchio d'acqua (natural=water)")
    if tags.get("natural") == "spring":
        kinds.append("sorgente (natural=spring)")
    if tags.get("amenity") == "drinking_water":
        kinds.append("acqua potabile (amenity=drinking_water)")
    if tags.get("amenity") == "parking":
        kinds.append("parcheggio (amenity=parking)")
    if tags.get("tourism") == "viewpoint":
        kinds.append("punto panoramico (tourism=viewpoint)")
    if tags.get("tourism") == "information" and tags.get("information") == "guidepost":
        kinds.append("palina segnavia (information=guidepost)")
    if tags.get("place") == "locality":
        kinds.append("località (place=locality)")
    return kinds


def _in_bbox(lon: float, lat: float, bbox: tuple[float, float, float, float]) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def _metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distanza approssimata (equirettangolare) tra due punti lon/lat: basta per tratti brevi."""
    mean_lat = math.radians((a[1] + b[1]) / 2)
    dx = math.radians(b[0] - a[0]) * math.cos(mean_lat)
    dy = math.radians(b[1] - a[1])
    return 6371008.8 * math.hypot(dx, dy)


def _coverage(items: Iterable[dict[str, str]], keys: Iterable[str]) -> dict[str, Any]:
    rows = list(items)
    total = len(rows)
    out: dict[str, Any] = {"totale": total}
    for key in keys:
        count = sum(1 for tags in rows if tags.get(key))
        out[key] = {"n": count, "pct": round(100 * count / total, 1) if total else 0.0}
    return out


def _main_tags(tags: dict[str, str]) -> dict[str, str]:
    keep = ("natural", "tourism", "amenity", "place", "highway", "man_made", "water", "bridge")
    return {k: v for k, v in tags.items() if k in keep}


def analyse_pbf(path: Path, sample: Area, fixture: Area) -> dict[str, Any]:
    """Una passata sull'estratto: statistiche nella bbox campione e oggetti della fixture."""
    import osmium  # dipendenza del gruppo `geo`

    union = (
        min(sample.bbox[0], fixture.bbox[0]),
        min(sample.bbox[1], fixture.bbox[1]),
        max(sample.bbox[2], fixture.bbox[2]),
        max(sample.bbox[3], fixture.bbox[3]),
    )
    counts = Counter()
    pois: dict[str, list[dict[str, str]]] = {}
    foot_ways: dict[int, dict[str, Any]] = {}  # way pedonali nella bbox campione
    ways_in_sample: set[int] = set()
    ways_in_fixture: set[int] = set()
    named: list[dict[str, Any]] = []  # oggetti con nome nell'area della fixture
    relations: list[dict[str, Any]] = []

    def add_poi(tags: dict[str, str]) -> None:
        for kind in poi_kinds(tags):
            pois.setdefault(kind, []).append(tags)

    def add_named(kind: str, osm_id: int, lon: float, lat: float, tags: dict[str, str]) -> None:
        if any(tags.get(k) for k in NAME_KEYS):
            names = {k: tags[k] for k in NAME_KEYS if tags.get(k)}
            named.append(
                {
                    "osm_type": kind,
                    "osm_id": osm_id,
                    "lon": round(lon, 6),
                    "lat": round(lat, 6),
                    "ele": tags.get("ele"),
                    "names": names,
                    "tags": _main_tags(tags),
                }
            )

    for obj in osmium.FileProcessor(str(path)).with_locations():
        if obj.is_node():
            counts["nodi"] += 1
            if not obj.tags or not obj.location.valid():
                continue
            lon, lat = obj.location.lon, obj.location.lat
            if not _in_bbox(lon, lat, union):
                continue
            tags = dict(obj.tags)
            if _in_bbox(lon, lat, sample.bbox):
                add_poi(tags)
            if _in_bbox(lon, lat, fixture.bbox):
                add_named("node", obj.id, lon, lat, tags)
        elif obj.is_way():
            counts["way"] += 1
            if not obj.tags:
                continue
            pts = [(n.location.lon, n.location.lat) for n in obj.nodes if n.location.valid()]
            if not pts or not any(_in_bbox(x, y, union) for x, y in pts):
                continue
            tags = dict(obj.tags)
            centre = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            in_sample = any(_in_bbox(x, y, sample.bbox) for x, y in pts)
            if in_sample:
                ways_in_sample.add(obj.id)
                add_poi(tags)
                if tags.get("highway") in HIGHWAY_FOOT:
                    length = sum(
                        _metres(a, b)
                        for a, b in itertools.pairwise(pts)
                        if _in_bbox((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, sample.bbox)
                    )
                    foot_ways[obj.id] = {"tags": tags, "m": length}
            if any(_in_bbox(x, y, fixture.bbox) for x, y in pts):
                ways_in_fixture.add(obj.id)
                add_named("way", obj.id, centre[0], centre[1], tags)
        elif obj.is_relation():
            counts["relazioni"] += 1
            tags = dict(obj.tags)
            if tags.get("route") not in ("hiking", "foot"):
                continue
            if tags.get("type") not in ("route", "superroute"):
                continue
            way_ids = [m.ref for m in obj.members if m.type == "w"]
            rel_ids = [m.ref for m in obj.members if m.type == "r"]
            relations.append(
                {
                    "id": obj.id,
                    "tags": tags,
                    "n_way": len(way_ids),
                    "member_relations": rel_ids,
                    "way_ids": way_ids,
                    "in_sample": sum(1 for w in way_ids if w in ways_in_sample),
                    "in_fixture": sum(1 for w in way_ids if w in ways_in_fixture),
                }
            )

    in_sample = [r for r in relations if r["in_sample"]]
    way_in_route = {w for r in relations for w in r["way_ids"]}

    # --- sentieri (way) nella bbox campione
    by_highway: dict[str, dict[str, Any]] = {}
    for kind in HIGHWAY_FOOT:
        rows = [w for w in foot_ways.values() if w["tags"]["highway"] == kind]
        if not rows:
            continue
        ids = [i for i, w in foot_ways.items() if w["tags"]["highway"] == kind]
        km = sum(w["m"] for w in rows) / 1000
        km_route = sum(foot_ways[i]["m"] for i in ids if i in way_in_route) / 1000
        by_highway[kind] = {
            "km": round(km, 1),
            "km_in_relazioni_escursionistiche": round(km_route, 1),
            "copertura_tag": _coverage((w["tags"] for w in rows), WAY_TAGS),
        }
    paths = [w["tags"] for w in foot_ways.values() if w["tags"]["highway"] == "path"]

    summary = {
        "file": path.name,
        "bbox_campione": list(sample.bbox),
        "totali_estratto": dict(counts),
        "relazioni_escursionistiche": {
            "nell_estratto": len(relations),
            "nella_bbox_campione": len(in_sample),
            "per_network": dict(Counter(r["tags"].get("network", "(assente)") for r in in_sample)),
            "per_operator": dict(
                Counter(r["tags"].get("operator", "(assente)") for r in in_sample).most_common(8)
            ),
            "cai_scale": dict(Counter(r["tags"].get("cai_scale", "(assente)") for r in in_sample)),
            "copertura_tag": _coverage((r["tags"] for r in in_sample), REL_TAGS),
            "esempi_duration_forward": sorted(
                {
                    r["tags"]["duration:forward"]
                    for r in in_sample
                    if "duration:forward" in r["tags"]
                }
            )[:5],
        },
        "way_pedonali": by_highway,
        "path_sac_scale": dict(Counter(t.get("sac_scale", "(assente)") for t in paths)),
        "path_trail_visibility": dict(
            Counter(t.get("trail_visibility", "(assente)") for t in paths)
        ),
        "poi": {kind: _coverage(rows, POI_TAGS) for kind, rows in sorted(pois.items())},
    }

    # --- fixture: punti chiave e relazioni citate
    points: dict[str, list[dict[str, Any]]] = {}
    for label, alternatives, declared_ele in FIXTURE_TARGETS:
        hits = []
        for item in named:
            text = " | ".join(norm(v) for v in item["names"].values())
            if any(all(word in text for word in words) for words in alternatives):
                hits.append({**item, "quota_dichiarata": declared_ele})
        hits.sort(key=lambda h: (h["ele"] is None, "highway" in h["tags"]))
        points[label] = hits

    def rel_view(rel: dict[str, Any]) -> dict[str, Any]:
        keys = ("ref", "reg_ref", "name", "cai_scale", "network", "operator", "from", "to")
        keys += ("distance", "ascent", "descent", "duration:forward", "duration:backward", "stage")
        view = {k: rel["tags"][k] for k in keys if k in rel["tags"]}
        return {"id": rel["id"], **view, "n_way": rel["n_way"], "way_in_area": rel["in_fixture"]}

    near = [r for r in relations if r["in_fixture"]]
    by_ref = {
        ref: [rel_view(r) for r in near if r["tags"].get("ref") in {ref, f"E{ref}", f"O{ref}"}]
        for ref in FIXTURE_REFS
    }
    networks = {
        label: [rel_view(r) for r in near if needle in norm(r["tags"].get("name"))]
        for label, needle in FIXTURE_NETWORKS.items()
    }
    networks["Sentiero Italia CAI"] = [rel_view(r) for r in near if r["tags"].get("ref") == "SI"]
    parents = [
        rel_view(r)
        for r in relations
        if r["member_relations"] and {n["id"] for n in near} & set(r["member_relations"])
    ]
    fixture_out = {
        "bbox": list(fixture.bbox),
        "punti_chiave": points,
        "sentieri_citati": by_ref,
        "reti_citate": networks,
        "superrelazioni": parents,
        "relazioni_escursionistiche_nell_area": len(near),
    }
    return {"summary": summary, "fixture": fixture_out}


def _robots(ctx: ProbeContext, r: ProbeResult, label: str, origin: str) -> Fetched | None:
    """Un solo tentativo sul robots.txt dell'host (leggerlo è sempre lecito)."""
    saved = ctx.client.max_retries
    ctx.client.max_retries = 0  # niente insistenza sugli host che rifiutano la connessione
    url = f"{origin}/robots.txt"
    try:
        res = ctx.client.get(url, ttl=None, respect_robots=False)
    except FetchError as exc:
        r.check(f"{label}: host raggiungibile", False, f"errore di rete: {exc.reason}", url)
        return None
    finally:
        ctx.client.max_retries = saved
    r.check(f"{label}: host raggiungibile", True, f"robots.txt → HTTP {res.status}", url)
    return res


def _listing(html: str) -> dict[str, tuple[str, int]]:
    """Indice nginx → {nome file: (data, byte)}."""
    rows = re.findall(
        r'<a href="[^"]+">([^<]+)</a>\s+(\d{2}-\w{3}-\d{4} \d{2}:\d{2})\s+(\d+)', html
    )
    return {name: (date, int(size)) for name, date, size in rows}


def _local_extract() -> Path | None:
    folder = data_dir() / "osm"
    files = sorted(folder.glob("*.osm.pbf"), key=lambda p: p.stat().st_size, reverse=True)
    return files[0] if files else None


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="OpenStreetMap – estratto regionale .osm.pbf",
        format="OSM PBF (nodi, way, relazioni con tutti i tag)",
        license="ODbL 1.0 – © OpenStreetMap contributors",
        license_url="https://www.openstreetmap.org/copyright",
        limits=(
            "Un download per regione e per aggiornamento (file statici, niente API). "
            "OSM-FR vieta i client automatici via robots.txt; Geofabrik non verificabile da qui."
        ),
        update_frequency="Giornaliera (Estratti OSM Italia, OSM-FR); nel progetto: settimanale",
    )

    # 1) Geofabrik: la fonte indicata dalla SPEC
    if _robots(ctx, r, "Geofabrik", GEOFABRIK):
        ctx.try_get(r, "Geofabrik: pagina Nord-Est", f"{GEOFABRIK}/europe/italy/nord-est.html")
    else:
        r.notes.append(
            "Geofabrik non è verificabile da questo ambiente (connessione chiusa durante il "
            "TLS): licenza, dimensione di nord-est-latest.osm.pbf e copertura del Tirolo "
            "restano da controllare da una rete normale."
        )

    # 2) OSM-FR: raggiungibile, ma il robots.txt esclude tutto
    robots = _robots(ctx, r, "OSM-FR", OSMFR)
    if robots and robots.ok:
        r.notes.append(f"robots.txt di OSM-FR: {' / '.join(robots.text().split())!r}")
    state_url = f"{OSMFR_ITALY}/trentino_alto_adige.state.txt"
    allowed = ctx.client.allowed_by_robots(state_url)
    r.check(
        "OSM-FR: download automatico consentito da robots.txt",
        allowed,
        "consentito" if allowed else "Disallow: / per tutti gli user-agent → fonte non usabile",
        state_url,
    )

    # 3) Estratti OSM Italia (Wikimedia Italia): alternativa compatibile con robots.txt
    info = ctx.try_get(r, "Estratti OSM Italia: testi informativi", f"{OSMIT}/locales/it.json")
    if info:
        texts = info.json().get("infoText", {})
        r.notes.append(f"Estratti OSM Italia: «{texts.get('p1', '')}» «{texts.get('p5', '')}»")
    regions = ctx.try_get(r, "Estratti OSM Italia: elenco regioni", f"{OSMIT_PBF}/regioni/")
    if regions:
        files = _listing(regions.text())
        needed = [n for n in files if n.startswith(("04_", "05_"))]
        detail = "; ".join(f"{n} {files[n][1] / 1e6:.0f} MB del {files[n][0]}" for n in needed)
        r.check("Estratti OSM Italia: regioni dell'area pilota", len(needed) == 2, detail)
        r.examples.extend(f"{OSMIT_PBF}/regioni/{n}" for n in needed)
    sample_path = ctx.samples_dir(PROBE_ID) / Path(OSMIT_SAMPLE).name
    try:
        meta = ctx.client.download(f"{OSMIT_PBF}/{OSMIT_SAMPLE}", sample_path)
        ok = sample_path.exists() and sample_path.stat().st_size > 10_000
        r.check(
            "Estratti OSM Italia: download campione (comune di Scurelle)",
            ok,
            f"{sample_path.stat().st_size} byte, sha256 {meta['sha256'][:16]}…, "
            f"Last-Modified {meta.get('last_modified')}",
            f"{OSMIT_PBF}/{OSMIT_SAMPLE}",
        )
        r.samples.append(str(sample_path.relative_to(data_dir())))
        r.examples.append(f"{OSMIT_PBF}/{OSMIT_SAMPLE}")
    except Exception as exc:  # il campione è utile ma non indispensabile
        r.check("Estratti OSM Italia: download campione", False, f"{type(exc).__name__}: {exc}")

    fixture_area = areas()["val_inferno"]
    if sample_path.exists():
        small = analyse_pbf(sample_path, fixture_area, fixture_area)
        refs = sorted(
            {v["ref"] for rows in small["fixture"]["sentieri_citati"].values() for v in rows}
        )
        totals = small["summary"]["totali_estratto"]
        r.check(
            "campione comunale leggibile con pyosmium",
            totals.get("way", 0) > 0,
            f"{totals}; relazioni escursionistiche nell'area: "
            f"{small['fixture']['relazioni_escursionistiche_nell_area']}; "
            f"sentieri della fixture presenti: {refs}",
        )

    # 4) analisi dell'estratto regionale già scaricato
    local = _local_extract()
    if not r.check(
        "estratto regionale presente in data/osm/",
        local is not None,
        f"{local.name}, {local.stat().st_size / 1e6:.0f} MB"
        if local
        else f"assente: scaricare {OSMIT_PBF}/regioni/04_Trentino-Alto_Adige-Südtirol.osm.pbf",
    ):
        r.reachable = any(c.ok for c in r.checks)
        r.status = STATUS_PARTIAL if r.reachable else STATUS_BLOCKED
        return r
    assert local is not None
    digest = hashlib.md5(local.read_bytes()).hexdigest()
    r.notes.append(f"Estratto analizzato: {local.name}, md5 {digest}")

    result = analyse_pbf(local, ctx.lagorai, fixture_area)
    summary, fixture = result["summary"], result["fixture"]
    r.samples.append(ctx.save_sample(PROBE_ID, "lagorai_summary.json", summary))
    r.samples.append(ctx.save_sample(PROBE_ID, "fixture_val_inferno_osm.json", fixture))

    rels = summary["relazioni_escursionistiche"]
    cov = rels["copertura_tag"]
    r.check(
        "relazioni route=hiking nella bbox Lagorai",
        rels["nella_bbox_campione"] > 0,
        f"{rels['nella_bbox_campione']} (su {rels['nell_estratto']} nell'estratto)",
    )
    for tag in ("ref", "cai_scale", "osmc:symbol", "duration:forward", "ascent"):
        r.check(
            f"tag {tag} sulle relazioni",
            cov[tag]["pct"] >= 50,
            f"{cov[tag]['n']}/{cov['totale']} ({cov[tag]['pct']}%)",
        )
    r.check(
        "tag ref:REI sulle relazioni",
        cov["ref:REI"]["n"] > 0,
        f"{cov['ref:REI']['n']}/{cov['totale']}; in Trentino il prefisso SAT è in reg_ref "
        f"({cov['reg_ref']['n']}/{cov['totale']})",
    )
    path = summary["way_pedonali"].get("path", {})
    if path:
        pc = path["copertura_tag"]
        r.check(
            "sac_scale sui path",
            pc["sac_scale"]["pct"] >= 50,
            f"{pc['sac_scale']['n']}/{pc['totale']} ({pc['sac_scale']['pct']}%), "
            f"trail_visibility {pc['trail_visibility']['pct']}%; {path['km']} km di path, "
            f"{path['km_in_relazioni_escursionistiche']} km dentro relazioni escursionistiche",
        )
    for kind, stats in summary["poi"].items():
        r.notes.append(
            f"POI {kind}: {stats['totale']} – name {stats['name']['pct']}%, "
            f"name:it {stats['name:it']['pct']}%, name:de {stats['name:de']['pct']}%, "
            f"ele {stats['ele']['pct']}%"
        )

    for label, hits in fixture["punti_chiave"].items():
        first = hits[0] if hits else None
        detail = (
            f"{len(hits)} oggetti; es. {first['osm_type']} {first['osm_id']} "
            f"«{first['names'].get('name')}» {first['lat']},{first['lon']} ele={first['ele']}"
            if first
            else "nessun oggetto OSM con questo nome"
        )
        r.check(f"fixture: {label}", bool(hits), detail)
    for ref, rows in fixture["sentieri_citati"].items():
        first = rows[0] if rows else None
        detail = (
            f"relazione {first['id']} «{first.get('name', '')}» cai_scale="
            f"{first.get('cai_scale')} reg_ref={first.get('reg_ref')}"
            if first
            else "nessuna relazione"
        )
        r.check(f"fixture: sentiero {ref}", bool(rows), detail)
    for label, rows in fixture["reti_citate"].items():
        ids = ", ".join(str(v["id"]) for v in rows)
        r.check(f"fixture: rete «{label}»", bool(rows), f"relazioni {ids}" if rows else "assente")

    r.reachable = True
    failed = [c for c in r.checks if not c.ok]
    r.status = STATUS_PARTIAL if failed else STATUS_OK
    return r
