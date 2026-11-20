"""Punti del percorso dal testo della locandina (ADR 0015).

Il parser a regole trova bene date, difficoltà e numeri, ma spesso non i punti del percorso,
che le locandine raccontano in prosa («partendo da località Giralba… arriveremo al lago di
Misurina… al rifugio Carpi presso la forcella Maraia»). Qui si cercano, nella sola parte che
descrive il percorso, i nomi di luoghi con una parola che ne dice il tipo (rifugio, passo,
forcella, malga, lago, cima…) o, per paesi e località, preceduti da un movimento («da», «a»,
«fino a»). Si scartano le cime solo guardate («vista sulle Marmarole», «ai piedi del Sorapis»)
e i luoghi del viaggio («ritrovo a Feltre», «3 km dopo Auronzo»). L'ordine è quello del testo;
la partenza è il luogo che segue «partendo da», «si parte da»…; per gli anelli si torna alla
partenza. La geocodifica (reconstruct.geocode) sceglie poi i luoghi giusti per vicinanza.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# parole che dicono il tipo di luogo; il nome segue con l'iniziale maiuscola (anche in minuscolo
# nel testo: «rifugio Carpi», «forcella Maraia»)
KIND = (
    r"rifugio|rif\.|bivacco|biv\.|capanna|baita|passo|p\.so|forcella|forc\.|sella|colle|"
    r"malga|malghe|casera|maso|lago|laghi|laghetto|monte|m\.te|mt\.|cima|cime|col|piz|pizzo|"
    r"punta|croda|sasso|pala|torre|dosso|corno|becco|località|loc\.|frazione|fraz\.|"
    r"chiesetta|chiesa|santuario|eremo|capitello|forte|ponte|pian|piana|prati|alpe"
)
_CONNECT = (
    r"(?:d[ei]|del|dell[ao']?|della|dei|degli|delle|di|d'|d’|al|alla|ai|sul|sulla|la|le|lo|il|"
    r"san|santa|s\.)"
)
_WORD = r"[A-ZÀ-Ý][\wÀ-ÿ'’\-]+"
# solo la parola di tipo ignora maiuscole e minuscole; il nome deve iniziare con la maiuscola
NAME_AFTER_KIND = re.compile(
    rf"\b(?P<kind>(?i:{KIND}))\s+"
    rf"(?P<name>(?:{_CONNECT}\s+|d['’])?{_WORD}(?:\s+(?:{_CONNECT}\s+)?{_WORD}){{0,3}})"
)
# un paese o una località senza parola di tipo: solo dopo un movimento
MOVE = re.compile(
    r"\b(?i:partendo da|si parte da|partenza da|parte da|da|dal|dalla|a|al|alla|fino a|sino a|"
    r"fino al|verso|per|raggiung\w+|arriv\w+ a|scend\w+ a|rientr\w+ a)\s+"
    rf"(?P<name>{_WORD}(?:\s+{_WORD}){{0,2}})"
)
ELEVATION = re.compile(
    r"^\s*[,(]?\s*(?:a\s+)?(?:quota\s+)?(?:m\.?|mt\.?|metri)?\s*(\d{1,2}[.\s]?\d{3}|\d{3,4})\s*"
    r"(?:m\b|mt\b|metri|m\.?\s*s\.?\s*l\.?\s*m\.?)?"
)
START = re.compile(
    r"(?:partendo|si parte|partenza|parte|si inizia|inizia|lasciate le auto|dal parcheggio)\s+"
    r"(?:\w+\s+){0,3}?(?:da|dal|dalla|dai|a|al|in)?\s*$",
    re.IGNORECASE,
)
# frasi che guardano lontano: i luoghi che seguono sono panorama, non percorso
VIEW = re.compile(
    r"\b(vista|ammir\w+|panoram\w+|sguardo|scorg\w+|osserv\w+|si vede\w*|cospetto|ai piedi d\w*|"
    r"sotto le pareti|dominat\w+|affaccia\w*|di fronte|all'?orizzonte|spaziare|spazia)\b",
    re.IGNORECASE,
)
# righe del viaggio, del ritrovo e delle regole: non descrivono il percorso
NOT_ROUTE_LINE = re.compile(
    r"^\s*(?:ore\s+\d|ritrovo|tragitto|viaggio|trasferimento|partenza\s+(?:in\s+)?(?:pullman|bus|auto)|"
    r"iscrizion|quota|costo|equipaggiamento|attrezzatura|abbigliamento|carta|cartografia|"
    r"note|n\.b|info|accompagnator|capogita|capi gita|responsabil|pranzo|cena|rientro previsto|"
    r"difficolt|dislivell|lunghezza|tempo|durata|mezzi|trasporto)",
    re.IGNORECASE,
)
SECTION_START = re.compile(
    r"^\s*(?:breve\s+)?(?:descrizione|itinerario|percorso|il percorso|programma(?: della gita)?|"
    r"relazione|descrizione del percorso)\b",
    re.IGNORECASE,
)
SECTION_STOP = re.compile(
    r"^\s*(?:programma e note|note ai partecipanti|note|equipaggiamento|attrezzatura|iscrizioni|"
    r"informazioni|regolamento|quota|costi?|accompagnator|capogita|difficolt[aà]['’]?\s*:)",
    re.IGNORECASE,
)
LOOP = re.compile(
    r"\b(anello|ad anello|circolare|punto di partenza|rientro (?:al|alla) partenza)\b", re.I
)

# parole con l'iniziale maiuscola che non sono luoghi
NOT_PLACE = {
    "sezione",
    "club",
    "alpino",
    "italiano",
    "cai",
    "sat",
    "gruppo",
    "ore",
    "domenica",
    "sabato",
    "lunedì",
    "martedì",
    "mercoledì",
    "giovedì",
    "venerdì",
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
    "difficoltà",
    "dislivello",
    "equipaggiamento",
    "foto",
    "quindi",
    "dopo",
    "dalla",
    "da",
    "qui",
    "il",
    "la",
    "le",
    "lo",
    "un",
    "una",
    "si",
    "e",
    "ed",
    "per",
    "con",
    "partenza",
    "arrivo",
    "rientro",
    "pranzo",
    "sosta",
    "itinerario",
    "percorso",
    "programma",
    "note",
    "costo",
    "quota",
    "iscrizioni",
    "escursione",
    "gita",
    "ritrovo",
    "tragitto",
    "questa",
    "questo",
    "queste",
    "questi",
    "poi",
    "infine",
    "arrivati",
    "giunti",
    "raggiunto",
    "raggiunta",
    "proseguendo",
    "proseguiamo",
    "saliamo",
    "scendiamo",
    "lungo",
    "attraverso",
    "commissione",
    "coordinatore",
    "coordinatori",
    "accompagnatore",
    "accompagnatori",
    "info",
    "centrale",
    "regionale",
    "nazionale",
    "provincia",
    "comune",
    "parco",
    "riserva",
    "pullman",
    "bus",
    "auto",
    "treno",
    "partecipanti",
    "soci",
    "socio",
    "presidente",
    "direttore",
    "proponiamo",
    "est",
    "ovest",
    "nord",
    "sud",
    "escursioni",
    "eventualmente",
    "in",
    "via",
    "viale",
    "piazza",
    "piazzale",
    "corso",
    "largo",
    "sede",
    "stazione",
    "chiesa",
    "ristorante",
    "albergo",
    "hotel",
}
# confronto senza accenti: «venerdì» e «venerdi» sono la stessa parola
NOT_PLACE_N = {
    unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode() for w in NOT_PLACE
}
MAX_POINTS = 9


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


def route_text(text: str) -> str:
    """La parte del testo che racconta il percorso, in un solo paragrafo per riga logica."""
    lines = [ln.strip() for ln in text.splitlines()]
    start = next((i for i, ln in enumerate(lines) if SECTION_START.match(ln)), None)
    chosen: list[str] = []
    if start is not None:
        for ln in lines[start + 1 :]:
            if SECTION_STOP.match(ln) and chosen:
                break
            chosen.append(ln)
    if not chosen or sum(len(x) for x in chosen) < 80:
        # senza un titolo di sezione: si salta l'intestazione (titolo, data, sezione), cioè le
        # righe brevi prima della prima riga di prosa
        first_prose = next(
            (
                i
                for i, ln in enumerate(lines)
                if len(ln.split()) >= 6 and re.search(r"[a-zà-ÿ]{3}", ln)
            ),
            0,
        )
        chosen = [ln for ln in lines[first_prose:] if ln and not NOT_ROUTE_LINE.match(ln)]
    # righe spezzate dall'impaginazione: si riuniscono; il trattino a fine riga si toglie
    joined = " ".join(chosen)
    joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
    return re.sub(r"\s+", " ", joined)


def _clean_name(kind: str | None, name: str) -> str | None:
    words = name.split()
    # il nome si ferma alla prima parola comune (con la maiuscola solo a inizio frase)
    out: list[str] = []
    for w in words:
        if _norm(w.strip("'’")) in NOT_PLACE_N and out:
            break
        out.append(w)
    while out and _norm(out[-1]) in {"di", "de", "del", "della", "dei", "al", "alla", "sul", "san"}:
        out.pop()
    if not out or _norm(out[0]) in NOT_PLACE_N:
        return None
    # sigle e parole tutte maiuscole senza parola di tipo: intestazioni, non luoghi
    if not kind and all(w.isupper() for w in out):
        return None
    core = " ".join(out)
    if kind:
        k = kind.lower().rstrip(".")
        k = {
            "rif": "rifugio",
            "biv": "bivacco",
            "forc": "forcella",
            "m.te": "monte",
            "mt": "monte",
            "p.so": "passo",
            "loc": "località",
            "fraz": "frazione",
        }.get(k, k)
        if k in {"località", "frazione"}:
            return core
        return f"{k.capitalize()} {core}"
    return core


def _elevation(after: str) -> int | None:
    m = ELEVATION.match(after[:24])
    if not m:
        return None
    value = int(re.sub(r"[.\s]", "", m.group(1)))
    return value if 200 <= value <= 4000 else None


START_ANYWHERE = re.compile(
    r"(?i:partenza(?:\s+dell'escursione)?|si parte|partendo|inizio (?:dell'escursione|del percorso|"
    r"del giro)|lasciate le auto|lasciata l'auto|parcheggio|parcheggiat\w+)\b"
)
MEETING = re.compile(r"(?i:\britrov\w*|appuntamento|\bore\s+\d)")
# arrivo con un mezzo: il luogo raggiunto in auto o in pullman è la partenza a piedi
TRANSPORT = re.compile(
    r"(?i:\b(?:bus|pullman|corriera|auto|macchin\w+|mezzi propri|treno|navetta)\b)"
)
ARRIVAL = re.compile(
    r"(?i:si raggiunge|raggiungeremo|raggiungiamo|arrivo(?:\s+indicativo)?(?:\s+ore\s+[\d.,:]+)?|"
    r"arriveremo|arrivati|fino)\s+(?:(?:a|al|alla|ai|in|presso|loc\.?|località)\s+)?"
)


def _first_name(tail: str, home: str | None) -> str | None:
    """Il primo nome di luogo in un pezzo di testo (con o senza parola di tipo)."""
    candidates = []
    km = NAME_AFTER_KIND.search(tail)
    if km:
        candidates.append((km.start(), _clean_name(km.group("kind"), km.group("name"))))
    for wm in re.finditer(rf"(?P<name>{_WORD}(?:\s+{_WORD}){{0,2}})", tail):
        name = _clean_name(None, wm.group("name"))
        if name:
            candidates.append((wm.start(), name))
            break
    for _, name in sorted(candidates):
        if name and not (home and _norm(name) == _norm(home)):
            return name
    return None


def declared_start(text: str, home: str | None = None) -> str | None:
    """La partenza detta in chiaro («Partenza dal parcheggio della loc. Giralba»), o il luogo
    raggiunto con un mezzo («col bus si raggiunge Passo Furcia»), se c'è."""
    flat = re.sub(r"\s+", " ", text)
    for sentence in re.split(r"(?<=[.;!?])\s+|\s+(?=(?i:ore)\s+\d)", flat):
        # il ritrovo in paese non è la partenza a piedi
        if MEETING.search(sentence):
            continue
        for m in START_ANYWHERE.finditer(sentence):
            name = _first_name(sentence[m.end() : m.end() + 70], home)
            if name:
                return name
    for sentence in re.split(r"(?<=[.;!?])\s+", flat):
        if not TRANSPORT.search(sentence):
            continue
        for a in ARRIVAL.finditer(sentence):
            name = _first_name(sentence[a.end() : a.end() + 50], home)
            if name:
                return name
    return None


def title_points(title: str | None, home: str | None = None) -> list[str]:
    """Le tappe nel titolo: «Chiusa – Albions – Gudon», «Traversata da Favogna al Rifugio Sores»."""
    if not title:
        return []
    t = re.sub(r"\s+", " ", title)
    m = re.search(r"(?i:\bda)\s+(.+?)\s+(?i:a|al|alla|ai|fino a)\s+(.+)$", t)
    parts = [m.group(1), m.group(2)] if m else re.split(r"\s+[–—-]\s+|\s*[–—]\s*", t)
    out = []
    for part in parts:
        part = part.strip(" .,:")
        km = NAME_AFTER_KIND.match(part)
        name = _clean_name(km.group("kind"), km.group("name")) if km else _clean_name(None, part)
        if name and len(name) >= 3 and not (home and _norm(name) == _norm(home)):
            out.append(name)
    return out if len(out) >= 2 else []


def extract_points(text: str, home: str | None = None, title: str | None = None) -> dict[str, Any]:
    """Punti del percorso in ordine, con la quota se il testo la dà, e se è un anello."""
    body = route_text(text)
    mentions: list[tuple[int, str, int | None, bool]] = []  # (posizione, nome, quota, partenza)
    for clause_m in re.finditer(r"[^.;:!?]+[.;:!?]?", body):
        clause = clause_m.group(0)
        base = clause_m.start()
        view = VIEW.search(clause)
        cut = view.start() if view else len(clause)
        found: list[tuple[int, int, str | None, str]] = []
        for m in NAME_AFTER_KIND.finditer(clause):
            found.append((m.start(), m.end(), m.group("kind"), m.group("name")))
        for m in MOVE.finditer(clause):
            s, e = m.start("name"), m.end("name")
            if any(fs <= s < fe for fs, fe, _, _ in found):
                continue
            found.append((s, e, None, m.group("name")))
        for s, e, kind, raw in sorted(found):
            if s >= cut:
                continue  # panorama, non percorso
            name = _clean_name(kind, raw)
            if not name:
                continue
            if home and _norm(name) == _norm(home):
                continue  # la sede della sezione è il ritrovo, non il percorso
            before = clause[max(0, s - 40) : s]
            is_start = bool(START.search(before))
            mentions.append((base + s, name, _elevation(clause[e:]), is_start))
    # in ordine di testo, senza ripetizioni consecutive; la partenza dichiarata va in testa
    points: list[dict[str, Any]] = []
    seen: set[str] = set()
    start_idx = next((i for i, m in enumerate(mentions) if m[3]), None)
    ordered = (
        mentions
        if start_idx is None
        else [mentions[start_idx]]
        + [m for i, m in enumerate(mentions) if i != start_idx and m[0] > mentions[start_idx][0]]
    )
    # partenza: detta in chiaro, poi raggiunta con un mezzo, poi la prima tappa del titolo
    declared = declared_start(text, home) or next(iter(title_points(title, home)), None)
    if declared:
        hit = next((m for m in ordered if _norm(m[1]) == _norm(declared)), None)
        if hit:
            ordered = [hit] + [m for m in ordered if m is not hit]
        else:
            ordered = [(-1, declared, None, True), *ordered]
    for _, name, ele, _ in ordered:
        key = _norm(name)
        if key in seen:
            continue
        seen.add(key)
        points.append({"nome": name, "quota_m": ele})
        if len(points) >= MAX_POINTS:
            break
    loop = bool(LOOP.search(body))
    return {"punti": points, "anello": loop, "testo": body}
