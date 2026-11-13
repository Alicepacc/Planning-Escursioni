"""Siti delle sezioni CAI: scoperta dei PDF di locandine e programmi (SPEC §7.1).

Legge `config/sources/cai_sections.yaml`, verifica per ogni sito WordPress la REST API dei media
e analizza con PyMuPDF due PDF campione (una locandina e un libretto annuale) per capire se il
testo è estraibile. I PDF restano in `data/samples/` (non versionati); nel report finiscono solo
conteggi e nomi di file, mai nomi o recapiti di persone.
"""

from __future__ import annotations

import re

import fitz  # PyMuPDF
import yaml

from ..config import repo_root
from .base import STATUS_PARTIAL, ProbeContext, ProbeResult

PROBE_ID = "cai_sections"
ORG = "https://organizzazione.cai.it"
QUADERNO = (
    f"{ORG}/sez-appiano-caiaa/wp-content/uploads/sites/152/2026/02/SENTIERI-QUADERNO-NR.-1-CCE.pdf"
)
TRIP_NAME = re.compile(r"^\d{1,2}[a-z]?_\d{8}|^\d{4}[-_]\d{2}[-_]\d{2}", re.IGNORECASE)
NUMBERED_TRIP = re.compile(r"^\d{1,2}_\d{8}-(?!.*(ciclo|castagnata))", re.IGNORECASE)


def _pdf_stats(content: bytes) -> dict[str, float | int | bool]:
    doc = fitz.open(stream=content, filetype="pdf")
    chars = sum(len(page.get_text()) for page in doc)
    images = sum(len(page.get_images()) for page in doc)
    return {
        "pagine": doc.page_count,
        "caratteri": chars,
        "immagini": images,
        "testuale": chars / max(doc.page_count, 1) > 200,
    }


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="Siti delle sezioni CAI (locandine e programmi PDF)",
        format="WordPress REST (JSON) → PDF; siti non WordPress: HTML",
        license="Contenuti delle sezioni; uso consentito dal CAI con citazione dei crediti (§3). "
        "Dati personali dei capigita mai memorizzati.",
        limits="Nessun limite pubblicato: 1 richiesta ogni pochi secondi per host; robots.txt "
        "vieta solo /wp-admin/.",
        update_frequency="Irregolare: nuove locandine 1-3 settimane prima di ogni gita",
    )
    config = yaml.safe_load(
        (repo_root() / "config" / "sources" / "cai_sections.yaml").read_text(encoding="utf-8")
    )
    media_lists: dict[str, list[dict]] = {}
    for section in config["sections"]:
        slug, base = section["slug"], section["base_url"]
        if not base or not section["site_type"].startswith("wordpress"):
            r.check(f"{slug}: sito verificabile", False, f"{section['site_type']}: {base}")
            continue
        res = ctx.try_get(
            r,
            f"{slug}: elenco PDF via REST",
            f"{base}/wp-json/wp/v2/media",
            params={
                "mime_type": "application/pdf",
                "per_page": 100,
                "_fields": "id,date,title,source_url",
            },
            ttl=6 * 3600,
        )
        if not res:
            continue
        items = res.json()
        media_lists[slug] = items
        total = res.header("x-wp-total")
        trips = sum(bool(TRIP_NAME.match(i["source_url"].rsplit("/", 1)[-1])) for i in items)
        newest = max((i["date"][:10] for i in items), default="–")
        r.notes.append(
            f"{slug}: {total} PDF totali ({res.header('x-wp-totalpages')} pagine da 100); "
            f"tra gli ultimi {len(items)}, {trips} hanno un nome file da locandina datata; "
            f"più recente {newest}"
        )

    # filtro incrementale `after=`
    if "bolzano" in media_lists:
        base = next(s["base_url"] for s in config["sections"] if s["slug"] == "bolzano")
        inc = ctx.try_get(
            r,
            "bolzano: filtro incrementale after=",
            f"{base}/wp-json/wp/v2/media",
            params={
                "mime_type": "application/pdf",
                "after": "2026-10-01T00:00:00",
                "_fields": "id,date",
                "per_page": 100,
            },
            ttl=6 * 3600,
        )
        if inc:
            ok = all(i["date"] >= "2026-10-01" for i in inc.json())
            r.check(
                "after= restituisce solo PDF successivi alla data", ok, f"{len(inc.json())} PDF"
            )
        sitemap = ctx.try_get(r, "bolzano: sitemap XML (fallback)", f"{base}/wp-sitemap.xml")
        if sitemap:
            r.notes.append(f"wp-sitemap.xml: {sitemap.text().count('<sitemap>')} sotto-sitemap")

    # PDF campione: una locandina di gita e un libretto annuale
    samples = []
    trip = next(
        (
            i
            for i in media_lists.get("bolzano", [])
            if NUMBERED_TRIP.match(i["source_url"].rsplit("/", 1)[-1])
        ),
        None,
    )
    if trip:
        samples.append(("locandina di gita (Bolzano)", trip["source_url"]))
    booklet = next(
        (
            i
            for i in media_lists.get("appiano", [])
            if "PROGRAMMA-ATTIVITA" in i["source_url"].upper()
        ),
        None,
    )
    if booklet:
        samples.append(("libretto annuale (Appiano)", booklet["source_url"]))
    for label, url in samples:
        pdf = ctx.try_get(r, f"download {label}", url, ttl=30 * 86400)
        if pdf:
            name = url.rsplit("/", 1)[-1]
            r.samples.append(ctx.save_sample(PROBE_ID, name, pdf.content))
            stats = _pdf_stats(pdf.content)
            r.check(
                f"{label}: testo estraibile senza OCR", bool(stats["testuale"]), f"{name}: {stats}"
            )
            r.examples.append(url)

    quaderno = ctx.try_get(r, "Quaderno n.1 CCE (formula dei tempi, §8)", QUADERNO, ttl=30 * 86400)
    if quaderno:
        r.samples.append(
            ctx.save_sample(PROBE_ID, "SENTIERI-QUADERNO-NR.-1-CCE.pdf", quaderno.content)
        )
        r.notes.append(f"Quaderno n.1: {_pdf_stats(quaderno.content)}")

    # API strutturata delle attività: esiste ma è riservata ai frontend del CAI
    ns = ctx.try_get(r, "namespace REST cai-activities/v1", f"{ORG}/wp-json/cai-activities/v1")
    if ns:
        routes = sorted(k.rsplit("/", 1)[-1] for k in ns.json()["routes"] if k.count("/") == 3)
        r.notes.append(
            "organizzazione.cai.it espone il namespace REST «cai-activities/v1» (rotte: "
            + ", ".join(routes)
            + "). La ricerca è POST e risponde 403 «Origin header mancante»: è un'API riservata "
            "ai frontend del CAI e NON viene usata senza autorizzazione esplicita (SPEC §13-bis)."
        )
    r.notes.append(
        "Il nome del file è un segnale debole: il prefisso con data cattura anche documenti come "
        "«2026_11_03-Guida-alla-prima-iscrizione-online» (Bolzano). Serve il classificatore sul "
        "contenuto (SPEC §7.3)."
    )
    r.notes.append(
        "Locandina reale della fixture (Val d'Inferno, 15/11/2026): non trovata con la ricerca "
        "«Nassere» / «Inferno» sul sito di CAI Mestre; il sito di CAI Merano è da individuare."
    )
    return r.finish(STATUS_PARTIAL if r.reachable else None)
