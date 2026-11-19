"""Adapter generico per i siti delle sezioni senza l'API di WordPress (ADR 0013).

Per ogni sito, con il `PoliteClient` (robots.txt, cache, pause tra le richieste):

1. la home;
2. al massimo `MAX_PAGES` pagine dello stesso sito collegate dalla home, scelte perché il link
   parla di gite, escursioni, programma, calendario o attività;
3. da queste pagine, solo i **link ai PDF** (titolo del link, indirizzo, data se è nel nome).

Nessun download dei PDF: come per l'API dei media, i metadati finiscono nell'indice
(`data/activities/index.json`) e la scelta dei candidati resta manuale, con revisione.
"""

from __future__ import annotations

import hashlib
import re
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlsplit

from ..http import FetchError, PoliteClient, RobotsDisallowed
from .classify import classify_name
from .discover import DocumentRef

MAX_PAGES = 6
LIST_WORDS = re.compile(
    r"gite|gita|escursion|programm|calendari|attivit|uscite|eventi|iniziative|locandin",
    re.IGNORECASE,
)
SKIP_WORDS = re.compile(r"privacy|cookie|login|carrello|cart|wp-admin|feed|mailto:", re.I)
ANCHOR = re.compile(r"<a\b[^>]*?href\s*=\s*[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
DATE_IN_NAME = re.compile(
    r"(20\d{2})[-_./]?(\d{2})[-_./]?(\d{2})|(\d{2})[-_.](\d{2})[-_.](20\d{2})"
)
YEAR_IN_PATH = re.compile(r"/(20\d{2})/(\d{2})/")


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def links(html: str, base: str) -> list[tuple[str, str]]:
    """(url assoluto, testo del link) di una pagina, senza doppioni."""
    out: dict[str, str] = {}
    for href, inner in ANCHOR.findall(html):
        url = urljoin(base, unescape(href.strip()))
        if url.startswith("http") and not SKIP_WORDS.search(url):
            out.setdefault(url.split("#")[0], _text(inner))
    return list(out.items())


def guess_date(url: str, title: str) -> str:
    """Data dal nome del file o dal titolo («2026-05-17», «17.05.2026»), altrimenti dal percorso
    dei caricamenti («/2026/05/»); stringa vuota se non c'è."""
    name = url.rsplit("/", 1)[-1]
    for text in (name, title):
        m = DATE_IN_NAME.search(text)
        if m and m.group(1):
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        if m:
            return f"{m.group(6)}-{m.group(5)}-{m.group(4)}"
    m = YEAR_IN_PATH.search(url)
    return f"{m.group(1)}-{m.group(2)}-01" if m else ""


def list_pages(home_html: str, home_url: str) -> list[str]:
    """Pagine dello stesso sito che probabilmente elencano gite o programmi."""
    host = urlsplit(home_url).netloc.removeprefix("www.")
    chosen: list[str] = []
    for url, text in links(home_html, home_url):
        same_site = urlsplit(url).netloc.removeprefix("www.") == host
        wanted = not url.lower().endswith(".pdf") and LIST_WORDS.search(f"{url} {text}")
        is_home = url.rstrip("/") == home_url.rstrip("/")
        if same_site and wanted and not is_home and url not in chosen:
            chosen.append(url)
    return chosen[:MAX_PAGES]


def crawl_section(client: PoliteClient, section: dict[str, Any]) -> list[DocumentRef]:
    """PDF pubblici della sezione trovati nella home e nelle pagine delle gite."""
    home = section["base_url"].rstrip("/") + "/"
    home_res = client.get(home, ttl=24 * 3600).raise_for_status()
    pages = [(home, home_res.text())]
    for url in list_pages(pages[0][1], str(home_res.url)):
        try:
            res = client.get(url, ttl=24 * 3600)
        except (FetchError, RobotsDisallowed):
            continue
        if res.ok:
            pages.append((url, res.text()))
    refs: dict[str, DocumentRef] = {}
    for page_url, html in pages:
        for url, text in links(html, page_url):
            if not urlsplit(url).path.lower().endswith(".pdf") or url in refs:
                continue
            title = text or url.rsplit("/", 1)[-1]
            refs[url] = DocumentRef(
                section=section["slug"],
                wp_id=int(hashlib.sha1(url.encode()).hexdigest()[:8], 16),
                title=title[:200],
                date=guess_date(url, title),
                modified="",
                url=url,
                page=page_url,
                guess=classify_name(f"{title} {url.rsplit('/', 1)[-1]}"),
            )
    return list(refs.values())
