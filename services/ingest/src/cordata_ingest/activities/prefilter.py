"""Prefiltro per titolo dei documenti scoperti (ADR 0015).

Prima di scaricare migliaia di locandine, il titolo dice spesso dove va la gita: se nomina una
cima, un rifugio, un passo, un lago o un paese dell'area del catalogo è «dentro»; se nomina
solo mete lontane (Appennini, Liguria, Colli Euganei, Friuli…) è «fuori» e non si scarica;
altrimenti è «incerto» e si scarica comunque, perché la meta la dirà il testo. Meglio scaricare
qualche documento in più che perdere escursioni buone.

I nomi vengono dal gazetteer OSM (`data/osm/gazetteer/named.geojsonseq`): solo cime, selle,
valli, rifugi, laghi e località; un nome che compare sia dentro sia fuori dall'area non decide.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from ..config import data_dir
from ..geo.area import contains

HIKE_GUESSES = {
    "escursionismo",
    "escursionismo?",
    "ciaspolata",
    "programma",
    "alpinismo",
}

# tipi di luogo che possono nominare la meta di una gita
PLACE_TAGS = {
    ("natural", "peak"),
    ("natural", "saddle"),
    ("natural", "valley"),
    ("natural", "water"),
    ("natural", "glacier"),
    ("natural", "ridge"),
    ("tourism", "alpine_hut"),
    ("tourism", "wilderness_hut"),
    ("mountain_pass", "yes"),
    ("place", "village"),
    ("place", "town"),
    ("place", "hamlet"),
    ("place", "locality"),
}

# mete lontane dall'area: se il titolo ne nomina una (e nessun luogo dell'area) è «fuori».
# Con l'asterisco vale anche come inizio di parola (appennino, appenninica…). Niente nomi di
# città: molti rifugi ne portano uno (Capanna Trieste, Rifugio Venezia, Rifugio Padova…).
OUTSIDE_WORDS = [
    "appennin*",
    "liguria",
    "cinque terre",
    "portofino",
    "toscana",
    "apuane",
    "garfagnana",
    "umbria",
    "marche",
    "abruzzo",
    "lazio",
    "campania",
    "amalfi",
    "cilento",
    "puglia",
    "gargano",
    "basilicata",
    "calabria",
    "sicilia",
    "etna",
    "eolie",
    "sardegna",
    "elba",
    "capri",
    "ischia",
    "euganei",
    "berici",
    "montello",
    "colli asolani",
    "friuli",
    "carnia",
    "carnich*",
    "dolomiti friulane",
    "giulie",
    "tarvisio",
    "carso",
    "slovenia",
    "croazia",
    "istria",
    "lombardia",
    "orobie",
    "valtellina",
    "grigna",
    "lago di como",
    "valle d'aosta",
    "piemonte",
    "svizzera",
    "francia",
    "spagna",
    "grecia",
    "portogallo",
    "corsica",
    "madeira",
    "canarie",
    "laguna",
    "delta del po",
    "magredi",
    "dolom* friulan*",
    "piancavallo",
    "lago di garda",
]

# parole troppo comuni per decidere da sole
GENERIC = {
    "monte",
    "cima",
    "croce",
    "lago",
    "rifugio",
    "passo",
    "malga",
    "valle",
    "forcella",
    "madonna",
    "chiesa",
    "santa",
    "san",
    "col",
    "sasso",
    "punta",
    "bivacco",
    "anello",
    "sentiero",
    "gita",
    "escursione",
    "locandina",
    "programma",
    "giornata",
    "sociale",
    "senior",
    "seniores",
    "giovanile",
    "alpinismo",
    "ciaspolata",
    "trekking",
    "ferrata",
    "invernale",
    "estiva",
    "estivo",
    "notturna",
    "relazione",
    "manutenzione",
    "scheda",
    "tappa",
    "definitivo",
    "review",
    "family",
    "festa",
    "pranzo",
    "castelli",
    "i castelli",
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
    "lunedi",
    "martedi",
    "mercoledi",
    "giovedi",
    "venerdi",
    "sabato",
    "domenica",
}

# parole che bastano a dire «dentro» (gruppi, valli e altopiani dell'area)
INSIDE_WORDS = [
    "dolomit*",
    "brenta",
    "lagorai",
    "pale di san martino",
    "marmolada",
    "sella",
    "catinaccio",
    "latemar",
    "civetta",
    "pelmo",
    "antelao",
    "sorapis",
    "cristallo",
    "tofane",
    "fanes",
    "puez",
    "odle",
    "sciliar",
    "ortles",
    "cevedale",
    "adamello",
    "presanella",
    "pasubio",
    "carega",
    "lessinia",
    "asiago",
    "sette comuni",
    "grappa",
    "vette feltrine",
    "cadore",
    "ampezz*",
    "agordin*",
    "zoldo",
    "zoldan*",
    "primiero",
    "fassa",
    "fiemme",
    "gardena",
    "val badia",
    "alta badia",
    "pusteria",
    "venosta",
    "isarco",
    "val di non",
    "val di sole",
    "rendena",
    "giudicarie",
    "ledro",
    "valsugana",
    "tesino",
    "cembra",
    "alpago",
    "cansiglio",
    "feltrin*",
    "bellunes*",
    "trentin*",
    "alto adige",
    "sudtirol",
]

MIN_LEN = 5

# parole iniziali che si possono togliere dal nome di un luogo
PREFIXES = {
    "monte",
    "cima",
    "piz",
    "pizzo",
    "punta",
    "rifugio",
    "bivacco",
    "malga",
    "passo",
    "forcella",
    "lago",
    "laghi",
    "val",
    "valle",
    "col",
    "croda",
    "sasso",
    "corno",
    "dosso",
    "baita",
}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[_\-–—./,:;()'’\"]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _names(props: dict[str, Any]) -> Iterable[str]:
    for key in ("name", "name:it", "name:de", "alt_name"):
        value = props.get(key)
        if value:
            yield from value.split(";")


def _variants(n: str) -> Iterable[str]:
    """Il nome intero e, se resta distintivo, il nome senza la parola generica iniziale
    («monte vioz» → «vioz», «rifugio fonda savio» → «fonda savio»)."""
    if len(n) >= MIN_LEN and n not in GENERIC:
        yield n
    first, _, rest = n.partition(" ")
    if rest and first in PREFIXES:
        rest = re.sub(r"^(di|del|della|dei|delle|degli|d) ", "", rest)
        distinctive = (len(rest) >= MIN_LEN and " " not in rest) or len(rest) >= 9
        if distinctive and rest not in GENERIC:
            yield rest


def build_names(gazetteer: Path | None = None) -> tuple[set[str], set[str]]:
    """Nomi (normalizzati) dei luoghi dentro e fuori dall'area, senza quelli ambigui."""
    gazetteer = gazetteer or data_dir() / "osm" / "gazetteer" / "named.geojsonseq"
    inside: set[str] = set()
    outside: set[str] = set()
    with gazetteer.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip().lstrip("\x1e")
            if not line:
                continue
            feature = json.loads(line)
            props = feature["properties"]
            if not any((k, props.get(k)) in PLACE_TAGS for k, _ in PLACE_TAGS):
                continue
            geom = feature.get("geometry")
            if not geom:
                continue
            # valli, laghi e ghiacciai sono spesso linee o aree: basta un punto rappresentativo
            pt = shape(geom).representative_point()
            lon, lat = pt.x, pt.y
            target = inside if contains(lon, lat) else outside
            for name in _names(props):
                for n in _variants(norm(name)):
                    target.add(n)
    both = inside & outside
    return inside - both, outside - both


def _mentions(title: str, names: set[str]) -> list[str]:
    words = title.split()
    found = []
    # n-grammi del titolo (fino a 5 parole), confrontati con i nomi interi
    for size in range(5, 0, -1):
        for i in range(len(words) - size + 1):
            gram = " ".join(words[i : i + size])
            if gram in names and not any(gram in f for f in found):
                found.append(gram)
    return found


def _words(words: list[str], text: str) -> list[str]:
    found = []
    for w in words:
        stem = re.escape(norm(w.rstrip("*"))).replace(r"\*", r"\w*")
        if re.search(rf"\b{stem}" + ("" if w.endswith("*") else r"\b"), text):
            found.append(w)
    return found


def classify(
    title: str, inside: set[str], outside: set[str], programme: bool = False
) -> tuple[str, list[str]]:
    """«dentro», «fuori» o «incerto», con i nomi che hanno deciso.

    Ordine: le regioni lontane esplicite («Sardegna», «Dolomiti Friulane»…) decidono per prime,
    poi i luoghi e i gruppi dell'area, infine i luoghi di fuori. Un programma annuale non si
    scarta mai per un nome di luogo dell'area o di fuori: contiene molte gite.
    """
    t = norm(html.unescape(title))
    far = _words(OUTSIDE_WORDS, t)
    # «Dolomiti Friulane» contiene «dolomiti», che altrimenti direbbe «dentro»
    t_in = re.sub(r"dolom\w* friulan\w*", " ", t)
    near = _words(INSIDE_WORDS, t_in)
    hits = _mentions(t_in, inside)
    if far and not (programme and (near or hits)):
        return "fuori", far
    if hits or near:
        return "dentro", hits + near
    if programme:
        return "incerto", []
    out_hits = _mentions(t, outside)
    # un nome di fuori decide solo se è lungo, non una parola qualunque
    if out_hits and max(len(h) for h in out_hits) >= 8:
        return "fuori", out_hits
    return "incerto", []


def candidates(
    index: dict[str, Any], already: set[str], inside: set[str], outside: set[str]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Candidati da scaricare (dentro e incerti), alternando i siti: ogni sito resta al suo
    intervallo minimo tra le richieste, ma i siti diversi non si aspettano tra loro."""
    from collections import defaultdict
    from itertools import zip_longest
    from urllib.parse import urlsplit

    counts: dict[str, int] = defaultdict(int)
    per_host: dict[str, list[dict[str, Any]]] = defaultdict(list)
    used: set[str] = set()
    for doc in index["documents"]:
        if doc.get("guess") not in HIKE_GUESSES:
            continue
        verdict, _ = classify(
            doc.get("title", ""), inside, outside, programme=doc.get("guess") == "programma"
        )
        counts[verdict] += 1
        if verdict == "fuori" or doc["url"] in already:
            continue
        stem = Path(urlsplit(doc["url"]).path).stem
        base = f"{doc['section']}-{re.sub(r'[^a-z0-9]+', '-', norm(stem)).strip('-')}"[:90]
        cid, n = base, 2
        while cid in used:
            cid, n = f"{base}-{n}", n + 1
        used.add(cid)
        per_host[urlsplit(doc["url"]).netloc].append(
            {
                "id": cid,
                "section": doc["section"],
                "url": doc["url"],
                "published": (doc.get("date") or "")[:10],
                "prefiltro": verdict,
            }
        )
    for items in per_host.values():
        items.sort(key=lambda c: (c["prefiltro"] != "dentro", c["published"]), reverse=False)
    ordered = [c for group in zip_longest(*per_host.values()) for c in group if c]
    return ordered, dict(counts)
