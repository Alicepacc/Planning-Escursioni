"""Parser a regole delle locandine (SPEC §7.3, primo passaggio "Parser + Claude Code").

Estrae i campi dello schema del §2 dal testo già ripulito dei dati personali (`extract.py`).
Ogni campo ha `value`, `confidence` (0-1) e `source` (la riga del documento da cui viene, per
la verifica e per la revisione). I campi a bassa confidenza sono quelli che la revisione
(Claude Code, nella sessione di lavoro) deve controllare: nessuna chiamata a API a pagamento.

Copre i modelli visti nel pilota: locandine CAI Bolzano (campi etichettati), CAI Bressanone
(etichette maiuscole), SAT (testo libero), libretti e calendari annuali (una voce per attività).
"""

from __future__ import annotations

import itertools
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}
WEEKDAYS = r"(?:luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)"
DIFFICULTIES = ("EEA", "EAI", "EE", "E", "T")


@dataclass
class Field:
    value: Any
    confidence: float
    source: str = ""
    page: int | None = None


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _num(s: str) -> float:
    """Numeri all'italiana: "2.414" (migliaia) → 2414, "14,00" → 14.0, "10.550" → 10550."""
    s = s.strip()
    if re.fullmatch(r"\d{1,2}\.\d{3}", s):
        return float(s.replace(".", ""))
    return float(s.replace(",", "."))


def _cite(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    return line if len(line) <= 120 else line[:117] + "…"


class Doc:
    """Testo diviso in righe, con il numero di pagina di ciascuna."""

    def __init__(self, pages: list[tuple[int, str]]):
        self.lines: list[tuple[int, str]] = []
        for n, text in pages:
            for raw in text.splitlines():
                if raw.strip():
                    self.lines.append((n, raw.strip()))
        self.text = "\n".join(t for _, t in self.lines)
        self.folded = _fold(self.text)

    def find(
        self, pattern: str, flags: int = re.IGNORECASE
    ) -> tuple[re.Match[str], int, str] | None:
        """Prima corrispondenza su una riga o su due righe consecutive."""
        rx = re.compile(pattern, flags)
        for i, (page, line) in enumerate(self.lines):
            m = rx.search(line)
            if m:
                return m, page, line
            if i + 1 < len(self.lines):
                joined = f"{line} {self.lines[i + 1][1]}"
                m = rx.search(joined)
                if m and m.start() < len(line):
                    return m, page, joined
        return None

    def after_label(self, label: str, max_lines: int = 2) -> tuple[str, int, str] | None:
        """Valore sulla stessa riga dell'etichetta o nelle righe successive."""
        rx = re.compile(rf"^{label}\s*:?\s*(.*)$", re.IGNORECASE)
        for i, (page, line) in enumerate(self.lines):
            m = rx.match(line)
            if not m:
                continue
            rest = m.group(1).strip()
            if rest:
                return rest, page, line
            values = [t for _, t in self.lines[i + 1 : i + 1 + max_lines]]
            if values:
                return " ".join(values), page, f"{line} {values[0]}"
        return None


# ------------------------------------------------------------------ campi


# data di una lettera («Cavalese, 3 maggio 2018»): non è la data della gita
DEADLINE = re.compile(r"\b(?:entro|iscrizion\w*|prenotazion\w*|scadenz\w*|dalle ore|fino a)\b")
LETTER_DATE = re.compile(r"^[a-z][\w' ]{2,30},\s*\d{1,2}\s+\w+\s+20\d{2}\s*$")


def parse_date(doc: Doc, hint: str = "") -> Field:
    rx = rf"(?:{WEEKDAYS}\s*,?\s*)?(\d{{1,2}})\s+({'|'.join(MONTHS)})\s*(20\d{{2}})"
    letter: Field | None = None
    head = doc.lines[:40]
    for i, (page, line) in enumerate(head):
        nxt = head[i + 1][1].strip() if i + 1 < len(head) else ""
        m = None
        # «Domenica 8 novembre» a capo «2026» (impaginazione delle locandine)
        for text in (line, f"{line} {nxt}") if re.fullmatch(r"20\d{2}", nxt) else (line,):
            m = re.search(rx, _fold(text))
            if m:
                break
        if m and DEADLINE.search(_fold(line)[: m.start()]):
            continue  # «iscrizioni … entro martedì 20 ottobre 2026»: non è la data della gita
        if m:
            day, month, year = int(m.group(1)), MONTHS[m.group(2)], int(m.group(3))
            found = Field(f"{year:04d}-{month:02d}-{day:02d}", 0.9, _cite(line), page)
            if LETTER_DATE.match(_fold(line)):
                letter = letter or Field(found.value, 0.5, found.source, page)
                continue
            return found
    if letter:
        return letter
    # giorno senza anno («Sabato 17 maggio»): anno dalla cartella di caricamento del PDF
    # (…/uploads/2025/05/…); tra più giorni vale quello dell'escursione
    up = re.search(r"(20\d{2})/(\d{2})/", hint)
    if up:
        no_year = re.compile(rf"{WEEKDAYS}\s+(\d{{1,2}})\s+({'|'.join(MONTHS)})\b(?!\s*20\d{{2}})")
        days: list[tuple[int, Field]] = []
        for i, (page, line) in enumerate(doc.lines[:40]):
            m = no_year.search(_fold(line))
            if m:
                year = int(up.group(1)) + (1 if MONTHS[m.group(2)] < int(up.group(2)) - 2 else 0)
                value = f"{year:04d}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
                days.append((i, Field(value, 0.6, _cite(line), page)))
        for i, f in days:
            near = " ".join(t for _, t in doc.lines[i : i + 3])
            if re.search(r"escursion|camminat|gita", near, re.IGNORECASE):
                return f
        if days:
            return days[0][1]
    hint = hint.rsplit("/", 1)[-1]
    m = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", hint) or None
    if m:
        return Field(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", 0.6, f"nome del file: {hint}")
    m = re.search(r"(\d{2})[.-](\d{2})[.-](20\d{2})", hint)
    if m:
        return Field(f"{m.group(3)}-{m.group(2)}-{m.group(1)}", 0.6, f"nome del file: {hint}")
    return Field(None, 0.0)


GRADE_ORDER = ("T", "E", "EE", "EEA")


def _norm_difficulty(raw: str) -> str | None:
    raw = raw.upper().replace(".", "").replace(" ", "")
    if raw in {"E-EE", "EE-E"}:
        return raw
    pair = re.fullmatch(r"(EEA|EE|E|T)[-/](EEA|EE|E|T)", raw)
    if pair:  # «EE-EEA», «T/E»: il grado più alto, per prudenza
        return max(pair.groups(), key=GRADE_ORDER.index)
    for d in DIFFICULTIES:
        if raw.startswith(d):
            return "EAI" if raw.startswith("EAI") else d
    return None


def parse_difficulty(doc: Doc) -> Field:
    # etichetta senza distinzione di maiuscole, valore solo in maiuscolo (scala CAI)
    patterns = [
        (
            r"(?i:difficolt[aà])['’]?\s*:?\s*((?:E\.?){2}A\.?|EAI(?:-F)?|E-EE|EE-E|"
            r"(?:EEA|EE|E|T)\s*[-/]\s*(?:EEA|EE|E|T)|E\.?E\.?|E|T)(?![\w.])",
            0.95,
        ),
        (r"(?i:escursione)\s*:\s*(EAI|EEA|EE|E|T)\b", 0.95),
        (r"(?i:livello)\s*:?\s*(EAI|EEA|EE|E|T)\b", 0.9),
        (r"(?i:md\+)\s*(EAI|EEA|EE|E|T)\b", 0.7),
        (r"\((EEA|EE|EAI|E|T)\)", 0.7),
        (r"^(EAI(?:-F)?|EEA|EE(?:\s*-\s*E)?|E|T)$", 0.6),
    ]
    for pattern, conf in patterns:
        hit = doc.find(pattern, 0)
        if hit:
            m, page, line = hit
            value = _norm_difficulty(m.group(1))
            if value:
                return Field(value, conf, _cite(line), page)
    hit = doc.find(r"difficolt[aà]\s*:\s*([A-Za-zà]+)")
    if hit:  # "Media", "facile": non è la scala CAI
        m, page, line = hit
        return Field(None, 0.3, _cite(line), page)
    return Field(None, 0.0)


def _hm(hours: float) -> str:
    total = round(hours * 60)
    return f"{total // 60}:{total % 60:02d}"


def _hours(token: str) -> float:
    """ "5.30" e "5:30" = 5 h 30'; "1,5" = 1 h 30'; "2.00" = 2 h."""
    token = token.strip()
    m = re.fullmatch(r"(\d{1,2})[.:,](\d{2})", token)
    if m and int(m.group(2)) < 60 and not token.count(","):
        return int(m.group(1)) + int(m.group(2)) / 60
    if m and token.count(",") and m.group(2) in {"00", "15", "30", "45"}:
        return int(m.group(1)) + int(m.group(2)) / 60  # "5,00" "4,30" nei libretti
    return _num(token)


DUR_LABEL = re.compile(
    r"\b(?:tempi\s+di\s+(?:cammino|percorrenza)|ore\s+di\s+cammino(?:\s+totali)?|"
    r"tempo\s+di\s+percorrenza)\b",
    re.IGNORECASE,
)
DUR_TOKEN = re.compile(
    r"(?<![\d.,:])(?:(?P<h>\d{1,2})(?:[:.](?P<m1>\d{2})(?!\d)|\s*(?:h|ore|ora)\b\.?(?:\s*e)?"
    r"(?:\s*(?P<m2>\d{1,2})\s*(?:'|’|\"|″|minuti|min\b))?)|(?P<m3>\d{1,2})\s*minuti)",
    re.IGNORECASE,
)
DUR_TOTAL = re.compile(
    r"(\d{1,2})\s*(?:h|ore)(?:\s*e\s*(\d{1,2})\s*(?:minuti|min|'|’))?\s*(?:circa\s*)?"
    r"(?:complessiv|total)|totale\s*:?\s*(?:ca\.?|circa)?\s*(\d{1,2})\s*(?:h|ore)",
    re.IGNORECASE,
)
SEG_AFTER = re.compile(
    r"^\s*(?:circa\s*)?(?:\(|in\s+|di\s+)(salita|piano|discesa|ritorno)", re.IGNORECASE
)
SEG_BEFORE = re.compile(r"(salita|piano|discesa|ritorno)[^\d]{0,12}$", re.IGNORECASE)


def _labelled_duration(doc: Doc) -> Field | None:
    """Tempi dopo l'etichetta, anche su più righe: il totale dichiarato («4 ore circa totali»,
    «4 ore e 15 minuti complessivi») oppure la somma di salita, piano e discesa («1h 30' in
    salita, 1h 30" in piano, 2h in discesa»; «Salita 3 ore | In piano 1 ora | Discesa 3 ore»)."""
    for i, (page, line) in enumerate(doc.lines):
        label = DUR_LABEL.search(line)
        if not label:
            continue
        window = " ".join([line[label.end() :]] + [t for _, t in doc.lines[i + 1 : i + 3]])
        total = DUR_TOTAL.search(window)
        if total:
            h = int(total.group(1) or total.group(3))
            minutes = int(total.group(2)) if total.group(2) else 0
            return Field(_hm(h + minutes / 60), 0.9, _cite(line), page)
        segments: dict[str, float] = {}
        first: float | None = None
        for t in DUR_TOKEN.finditer(window):
            hours = (
                int(t.group("h") or 0)
                + int(t.group("m1") or t.group("m2") or t.group("m3") or 0) / 60
            )
            kind = SEG_AFTER.match(window[t.end() :]) or SEG_BEFORE.search(window[: t.start()])
            if first is None and t.start() <= 12:
                first = hours
            seg = kind.group(1).lower().replace("ritorno", "discesa") if kind else None
            if seg and seg not in segments:
                segments[seg] = hours
        if len(segments) >= 2 and {"salita", "discesa"} & set(segments):
            return Field(_hm(sum(segments.values())), 0.85, _cite(line), page)
        if first and 0.5 <= first <= 14:
            return Field(_hm(first), 0.85, _cite(line), page)
    return None


def parse_duration(doc: Doc) -> Field:
    num = r"(\d{1,2}(?:[.,:]\d{1,2})?)"
    # salita + discesa: "circa 3 ore in salita e circa 1,5 ore in discesa"
    hit = doc.find(rf"{num}\s*or[ae]\s*in\s*salita\D+{num}\s*or[ae]\s*in\s*discesa")
    if hit:
        m, page, line = hit
        return Field(_hm(_hours(m.group(1)) + _hours(m.group(2))), 0.85, _cite(line), page)
    # formati SAT: «Tempi: salita ore 4:00 - discesa ore 3:00», «Tempi: totale ore 6:30».
    # Vince il primo nel testo: l'eventuale alternativa escursionistica viene dopo.
    sum_rx = re.compile(
        rf"salita\s*(?:ore|h)\s*{num}\D{{0,15}}discesa\s*(?:ore|h)\s*{num}", re.IGNORECASE
    )
    tot_rx = re.compile(rf"totale\s*(?:{num}\s*(?:h|ore)\b|(?:ore|h)\s*{num})", re.IGNORECASE)
    for page, line in doc.lines:
        m = sum_rx.search(line)
        if m:
            return Field(_hm(_hours(m.group(1)) + _hours(m.group(2))), 0.85, _cite(line), page)
        m = tot_rx.search(line)
        if m:
            return Field(_hm(_hours(m.group(1) or m.group(2))), 0.9, _cite(line), page)
    window = _labelled_duration(doc)
    if window:
        return window
    hit = doc.find(r"\btempo\s*:\s*(\d{1,2})\s*(?:h|ore)\b(?:\s*e\s*(\d{1,2}|mezz[ao]))?")
    if hit:
        m, page, line = hit
        extra = m.group(2) or "0"
        minutes = 30 if extra.startswith("mezz") else int(extra)
        if minutes < 60:
            return Field(_hm(int(m.group(1)) + minutes / 60), 0.85, _cite(line), page)
    hit = doc.find(r"(?:andata e ritorno|a/r)[^\d]{0,15}h\s*:?\s*(\d{1,2})\s*e\s*(\d{2})")
    if hit:
        m, page, line = hit
        return Field(_hm(int(m.group(1)) + int(m.group(2)) / 60), 0.8, _cite(line), page)
    # mai "ore N" da solo: è quasi sempre un orario ("ritrovo ore 7", "ore 8 e mezza")
    patterns = [
        rf"ore di cammino(?: effettiv[oei])?\s*:?\s*(?:ca\.?|circa)?\s*{num}\s*(?:h|ore)?",
        rf"{num}\s*ore di cammino",
        rf"ore di cammino\s*:?\s*{num}",
        rf"tempo di percorrenza\s*:?\s*(?:circa)?\s*{num}\s*(?:h|ore)",
        rf"durata(?:\s*a/r)?\s*:?\s*{num}\s*(?:h|ore)",
        rf"durata[^\n\d]{{0,25}}?\bore\s*{num}",
        rf"(?:percorso|cammino|tempi?)\s*:?\s*(?:ore|h)\s*{num}",
        rf"\(ore\s*{num}\)",
        # nei programmi il tempo sta su una riga da solo: «6 ore», «A: 7 ore», «8/9 ore», «h 9:30»
        rf"^(?:[A-Z]\s*:\s*)?{num}(?:\s*/\s*\d{{1,2}})?\s*ore$",
        rf"^h\s*{num}$",
        rf"(?<![\d:.])\b{num}\s*h(?:\s*circa)?\b(?![^\n]*viaggio)",
    ]
    for i, pattern in enumerate(patterns):
        hit = doc.find(pattern)
        if hit:
            m, page, line = hit
            # "5h30’": minuti dopo la h
            tail = re.match(r"\s*h\s*(\d{2})", line[m.end(1) :])
            hours = _hours(m.group(1)) + (int(tail.group(1)) / 60 if tail else 0)
            if 0.5 <= hours <= 14:
                return Field(_hm(hours), 0.9 if i < 5 else 0.6, _cite(line), page)
    return Field(None, 0.0)


def parse_distance(doc: Doc) -> Field:
    patterns = [
        (
            r"(?:sviluppo|distanza|lunghezza|lungezza)[^\d\n]{0,40}?(\d{1,2}(?:[.,]\d{1,2})?)\s*km",
            0.9,
        ),
        (r"(?:sviluppo|distanza)(?:\s+totale)?\s*:?\s*(?:km\.?\s*)(\d{1,2}(?:[.,]\d{1,2})?)", 0.9),
        (r"(\d{1,2}(?:[.,]\d{1,2})?)\s*km\s*(?:di\s*)?(?:distanza|sviluppo)", 0.85),
        # schede CAI Belluno: «km tot.: 11.1 Km», «Km totali: 13 km», «Km e dislivello: 11 km…»
        (r"\bkm\.?\s*(?:tot\.?|totali|complessivi)\s*:?\s*(\d{1,2}(?:[.,]\d{1,2})?)\b", 0.85),
        (r"\bkm e dislivell\w*\s*:?\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*km", 0.9),
        (r"dislivell[^\n]*\bkm\.?\s*(\d{1,2}(?:[.,]\d{1,2})?)\b", 0.8),
        (r"^km\s*:?\s*(\d{1,2}(?:[.,]\d{1,2})?)", 0.9),
        (r"^sviluppo$", 0.0),
        # su una riga da sola, anche «A: 15 km» (non gli intervalli «25-30km»)
        (r"^(?:[A-Z]\s*:\s*)?(\d{1,2}(?:[.,]\d{1,2})?)\s*km$", 0.6),
        (r"(?<!\d)(?<!\d\s)[-–]\s*(\d{1,2}(?:[.,]\d)?)\s*km\b", 0.6),
    ]
    for pattern, conf in patterns:
        if conf == 0.0:
            label = doc.after_label("sviluppo", 1)
            if label:
                m = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*km", label[0], re.IGNORECASE)
                if m:
                    return Field(_num(m.group(1)), 0.85, _cite(label[2]), label[1])
            continue
        hit = doc.find(pattern)
        if hit:
            m, page, line = hit
            return Field(_num(m.group(1)), conf, _cite(line), page)
    return Field(None, 0.0)


def parse_elevation_gain(doc: Doc) -> tuple[Field, Field]:
    m_ = r"(?:m\.?|mt\.?|metri)"
    v = r"(\d{1,2}\.\d{3}|\d{2,4})"
    both = [
        r"(?:in\s+)?salita\s+e\s+(?:in\s+)?discesa\s*:?\s*(?:in salita e in discesa\s*)?"
        rf"{m_}?\s*{v}",
        rf"{v}\s*{m_}?\s*sia in salita che in discesa",
        rf"circa\s*{v}\s*{m_}\s*sia",
        rf"\+\s*-\s*{v}\s*m",
        rf"\+\s*{v}\s*/\s*-\s*\1\b",
    ]
    for pattern in both:
        hit = doc.find(pattern)
        if hit:
            m, page, line = hit
            val = _num(m.group(1))
            return Field(val, 0.9, _cite(line), page), Field(val, 0.9, _cite(line), page)
    up = down = None
    # «Km e dislivello: 11 km, +1300 m» (schede CAI Belluno)
    hit = doc.find(
        rf"\bkm e dislivell\w*\s*:?\s*\d{{1,2}}(?:[.,]\d{{1,2}})?\s*km\s*,?\s*\+?\s*{v}\s*m"
    )
    if hit:
        m, page, line = hit
        return Field(_num(m.group(1)), 0.85, _cite(line), page), Field(None, 0.0)
    # nei programmi: «700 md+», «921 md-», «D+ 2400m», «DISL. m. 900 ca»
    md_up = (
        doc.find(rf"\+?\s*{v}\s*md\+")
        or doc.find(rf"\bD\+\s*{v}\s*m\b")
        or doc.find(rf"(?i:disl\.)\s*(?:m\.?\s*)?{v}")
    )
    if md_up:
        m, page, line = md_up
        up = Field(_num(m.group(1)), 0.75, _cite(line), page)
        md_down = doc.find(rf"{v}\s*md-")
        if md_down:
            m, page, line = md_down
            down = Field(_num(m.group(1)), 0.75, _cite(line), page)
        return up, down or Field(None, 0.0)
    hit = doc.find(rf"\+\s*{v}\s*/\s*-\s*{v}")
    if hit:
        m, page, line = hit
        return (
            Field(_num(m.group(1)), 0.85, _cite(line), page),
            Field(_num(m.group(2)), 0.85, _cite(line), page),
        )
    for pattern in (
        rf"salita\s*:?\s*(?:di\s*)?(?:circa\s*)?{m_}?\s*{v}",
        rf"{v}\s*{m_}?\s*(?:di\s*|in\s*)?salita",
        rf"dislivello positivo(?:\s*itinerario\s*\d+)?\s*:?\s*{v}",
        rf"dislivello in salita\s*:?\s*(?:circa)?\s*{v}",
        rf"positiv[oa]\s*:?\s*{m_}?\s*{v}",
    ):
        hit = doc.find(pattern)
        if hit:
            m, page, line = hit
            up = Field(_num(m.group(1)), 0.85, _cite(line), page)
            break
    for pattern in (
        rf"discesa\s*:?\s*(?:di\s*)?(?:circa\s*)?{m_}?\s*{v}",
        rf"{v}\s*{m_}?\s*(?:di\s*|in\s*)?discesa",
        rf"negativ[oa]\s*:?\s*{m_}?\s*{v}",
    ):
        hit = doc.find(pattern)
        if hit:
            m, page, line = hit
            down = Field(_num(m.group(1)), 0.85, _cite(line), page)
            break
    if up is None:
        hit = doc.find(rf"dislivell[oi][^\d\n]{{0,25}}?(?:\+\s*)?{m_}?\s*{v}\s*{m_}?") or doc.find(
            rf"{v}\s*{m_}\s*(?:di\s+)?dislivell[oi]"
        )
        if hit:
            m, page, line = hit
            up = Field(_num(m.group(1)), 0.7, _cite(line), page)
        else:
            hit = doc.find(rf"\+\s*{v}\s*m\b")
            if hit:
                m, page, line = hit
                up = Field(_num(m.group(1)), 0.6, _cite(line), page)
    return up or Field(None, 0.0), down or Field(None, 0.0)


OPTIONAL_PEAK = re.compile(
    r"possibilit[àa]|facoltativ|eventualmente|sullo sfondo|vediamo|si vede|si scorg|in alternativa",
    re.IGNORECASE,
)


def parse_max_elevation(doc: Doc) -> Field:
    label = doc.after_label(r"(?:quota massima(?: raggiunta)?|punto più alto)", 1)
    if label:
        m = re.search(r"(\d{1,2}\.\d{3}|\d{3,4})", label[0])
        if m:
            return Field(_num(m.group(1)), 0.95, _cite(label[2]), label[1])
    hit = doc.find(
        rf"{QUOTA_ANY}[^.\n]{{0,30}}punto più alto|punto più alto[^.\n]{{0,40}}{QUOTA_ANY}"
    )
    if hit:
        m, page, line = hit
        value = next(g for g in m.groups() if g)
        return Field(_num(value), 0.8, _cite(line), page)
    # altrimenti la quota più alta citata nel testo (escluse le righe di dislivelli e sviluppi)
    best: tuple[float, int, str] | None = None
    previous = ""
    for page, line in doc.lines:
        # mete facoltative e cime viste da lontano non sono il punto più alto del giro
        optional = OPTIONAL_PEAK.search(f"{previous} {line}")
        previous = line
        if optional:
            continue
        if re.search(
            r"dislivell|sviluppo|lunghezza|\bD\+|md[+-]|(?:salita|discesa)\s*:?\s*(?:di\s*)?"
            r"(?:circa\s*)?(?:m\.?|mt\.?)?\s*\d",
            line,
            re.IGNORECASE,
        ):
            continue
        for m in re.finditer(QUOTA_ANY, line):
            value = _num(m.group(1) or m.group(2))
            if 300 <= value <= 4000 and (best is None or value > best[0]):
                best = (value, page, line)
    if best:
        return Field(best[0], 0.5, _cite(best[2]), best[1])
    return Field(None, 0.0)


QUOTA = r"\((?:m\.?\s*|mt\.?\s*)?(\d{1,2}\.\d{3}|\d{3,4})\s*(?:m|mt|m\.s\.l\.m\.?|metri)?\)"
# quota anche senza parentesi: "(m 1792)", "2557 m", "m 2.414", "(2036M)"
QUOTA_ANY = (
    r"(?:\(?\s*(?:m\.?|mt\.?)\s*(\d\.\d{3}|\d{4})\b"
    r"|\b(\d\.\d{3}|\d{4})\s*(?:m|mt|M|metri)\b\.?)"
)
# nome proprio: parole con l'iniziale maiuscola, anche abbreviate («Rif. Zannes», «P.so Rolle»)
NAME = (
    r"((?:[A-ZÀ-Ý][\w'’-]*\.(?=\s+[A-ZÀ-Ý])|[A-ZÀ-Ý][\w'’-]+|S\.)"
    r"(?:\s+(?:[A-ZÀ-Ý][\w'’-]*\.(?=\s+[A-ZÀ-Ý])|[A-ZÀ-Ý][\w'’-]+|S\.|(?:di|de|da|al|alla|del|"
    r"dei|delle|della|dal|dalla)\b))*)"
)


def _place(text: str) -> tuple[str | None, float | None]:
    text = re.sub(r"\s+", " ", text).strip(" :.,")
    m = re.search(r"\(?\s*(?:m\.?|mt\.?)\s*(\d{1,2}\.\d{3}|\d{3,4})\s*\)?", text)
    m = m or re.search(r"\(?\s*(\d{1,2}\.\d{3}|\d{3,4})\s*(?:m|mt)\b\.?\s*\)?", text)
    ele = _num(m.group(1)) if m else None
    name = (text[: m.start()] if m else text).strip(" ,(:-–")
    return (name or None), ele


def parse_start(doc: Doc) -> tuple[Field, Field, Field]:
    """Partenza (nome, quota) e arrivo, dalle etichette o dalle frasi tipiche."""
    start = doc.after_label(r"punto di partenza", 1)
    if start and re.match(r"(?i)(?:di|per|delle|dei)\b", start[0].strip()):
        start = None  # «è punto di partenza di diverse escursioni»: non un'etichetta
    end = doc.after_label(r"punto di arrivo", 1)
    if start:
        name, ele = _place(start[0])
        f_name = Field(name, 0.9, _cite(start[2]), start[1])
        f_ele = Field(ele, 0.9 if ele else 0.0, _cite(start[2]), start[1])
        f_end = Field(_place(end[0])[0], 0.9, _cite(end[2]), end[1]) if end else Field(None, 0.0)
        return f_name, f_ele, f_end
    # la città della sezione («Sezione di Feltre», «CAI FELTRE») è il ritrovo, non la partenza
    home = {
        m.group(1).lower()
        for _, line in doc.lines[:15]
        for m in re.finditer(
            r"(?i:sezione|sez\.|cai)\s+(?:(?i:cai|c\.a\.i\.)\s+)?(?:(?i:di)\s+)?([A-ZÀ-Ý][A-Za-zÀ-ÿ]+)",
            line,
        )
    } - {"cai", "alpino", "giovani", "escursionismo"}
    # parole chiave senza distinzione di maiuscole, nomi propri con l'iniziale maiuscola
    art = r"(?i:il|lo|la|l'|al|alla|ai|del|della|dei)"
    phrases = [
        rf"(?i:raggiung\w+|parcheggio de\w*)\s+(?:{art}\s*)?{NAME}\s*{QUOTA},?\s*"
        r"(?i:punto di partenza)",
        rf"(?i:parcheggio)\s+(?i:in\s+)?(?i:localit\S+|loc\.)\s+{NAME}",
        r"(?i:si sale|si raggiunge|saliamo)\s+(?i:al|alla|a)\s+(?:\w+\s+)?(?i:villaggio|paese|"
        rf"abitato|borgo)\s+(?i:di)\s+{NAME}\s*{QUOTA}",
        r"(?i:ini?zia|parte)\s+(?i:dal|dalla|da|presso)\s+(?:(?i:parcheggio)\s+"
        rf"(?:(?i:presso|del|della|di)\s+)?(?:(?i:il|la)\s+)?)?{NAME}\s*{QUOTA}",
        rf"^(?i:da|dal|dalla|dallo)\s+{NAME}\s*{QUOTA}",
        rf"{NAME}\s*{QUOTA}\s*(?i:dove si lasciano le (?:macchine|auto))",
        r"(?i:iniziamo l.escursione|il percorso inizia|si parte|partenza)\s+"
        r"(?i:da|a|dal|dall.|dalla)\s*(?i:l.?\s*)?(?i:abitato di|paese di|centro di|localit\S+)?"
        rf"\s*{NAME}\s*(?:{QUOTA})?",
        rf"(?i:partenza)[^\n]{{0,25}}?\b(?i:da)\s+(?i:localit\S+\s+)?{NAME}\s*(?:{QUOTA})?",
        r"(?i:l.escursione parte)\s+(?i:da|dal|dall.|dalla)\s*"
        rf"(?i:centro di|paese di|ampio parcheggio\s*\S*)?\s*{NAME}",
        rf"(?i:raggiunge|raggiungiamo)\s+(?:{art}\s*)?(?i:villaggio|paese|abitato)\s+(?i:di)\s+{NAME}[^()]*{QUOTA}",
        rf"(?i:ci dirigiamo|ci portiamo)\s+(?i:al|alla|a|ad)\s+{NAME}\s*{QUOTA}",
        rf"(?i:dal|da)\s+(?i:paese|abitato)\s+(?i:di)\s+{NAME}\s*(?:{QUOTA})?",
        rf"^(?i:dal|dalla|dall.)\s*{NAME}\s+(?i:si sale|si parte|si prende|si segue)",
        rf"(?i:partendo)\s+(?i:da|dal|dalla|dall.)\s*(?i:localit\S+\s+)?{NAME}",
        r"(?i:partire|parte|partenza|si parte)\s+(?i:dalla|dal|da)\s+(?i:piana|localit\S+|frazione)"
        rf"\s+(?i:di)\s+{NAME}",
        rf"(?i:ritrovo|parcheggio)(?![^\n]*(?i:sede))[^.\n]{{0,80}}?\b(?i:di|a)\s+{NAME}(?=[.,;]|\s*$)",
        rf"^{NAME}\s*(?:\([^)]*\))?\s*,?\s*(?i:all.entrata|è il punto di partenza)",
    ]
    for i, pattern in enumerate(phrases):
        hit = doc.find(pattern, 0)
        if hit:
            m, page, line = hit
            name = m.group(1)
            ele = _num(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else None
            transfer = re.match(
                r"\s*(?:con|in)\s+(?:i\s+)?(?:mezzi|bus|pullman|auto|macchin|le nostre)",
                line[m.end() :],
                re.IGNORECASE,
            )
            if transfer:
                continue
            # solo il testo prima del nome: «Partenza con il pullman da X» è il viaggio, mentre
            # «X (m 1334) dove si lasciano le macchine» è proprio la partenza a piedi
            travel = re.search(
                r"(?i)pullman|autobus|\bbus\b|\bauto\b|macchin|mezzi|pulmin",
                m.string[m.start() : m.start(1)],
            )
            if travel or (name or "").lower() in home:
                continue
            if name and name.lower() not in {"bressanone", "bolzano", "trento", "sede"}:
                conf = 0.6 if i < 3 else 0.5
                return (
                    Field(name.strip(), conf, _cite(line), page),
                    Field(ele, conf if ele else 0.0, _cite(line), page),
                    Field(None, 0.0),
                )
    return Field(None, 0.0), Field(None, 0.0), Field(None, 0.0)


def parse_route_type(doc: Doc, start: Field, end: Field, title: str = "") -> Field:
    f = doc.folded
    cues = {
        "andata_ritorno": [
            r"andata\s*=\s*ritorno",
            r"stess[oi] (?:percors|sentier)",
            r"via dell.andata",
            r"(?:lungo|per) (?:l.itinerario|il percorso|la via|lo stesso itinerario) di salita",
            r"a ritroso",
            r"\ba/r\b",
            r"andata e ritorno",
            r"ritorno (?:avverr?a|avviene) lungo lo stesso",
        ],
        "anello": [
            r"\banello\b",
            r"circolare",
            r"chiude(?:re|ndo|remo)? (?:il nostro )?anello",
            r"(?:si )?ritorna(?:re)? al punto di partenza",
        ],
        "traversata": [
            r"traversata",
            r"\bdove termina\b",
            r"\btappa\b",
        ],
    }
    scores: dict[str, int] = {}
    sources: dict[str, str] = {}
    f = re.sub(r"\s+", " ", f)  # le frasi vanno spesso a capo
    for kind, patterns in cues.items():
        for p in patterns:
            m = re.search(p, f, re.MULTILINE)
            if m:
                scores[kind] = scores.get(kind, 0) + 1
                sources.setdefault(kind, f[max(0, m.start() - 40) : m.end() + 40])
    # titolo "da Laion a Ortisei", "Da San Costantino al Monte Cavone"
    if re.search(r"\bda [a-z][\w' ]{2,30} (?:a|al|alla|fino a) [a-z]", _fold(title)):
        scores["traversata"] = scores.get("traversata", 0) + 1
        sources.setdefault("traversata", title)
    if start.value and not end.value:
        # «torniamo a Pregasina», «arrivo a Prè»: si torna alla partenza
        back = re.search(
            rf"(?:torn\w*|rientr\w*|ritorn\w*|arrivo)\s+(?:a|al|alla|ad|in)\s+{re.escape(_fold(start.value))}\b",
            f,
        )
        if back:
            scores["anello"] = scores.get("anello", 0) + 1
            sources.setdefault("anello", f[max(0, back.start() - 30) : back.end() + 10])
    if start.value and end.value:
        same = _fold(start.value).strip() == _fold(end.value).strip()
        scores["anello" if same else "traversata"] = (
            scores.get("anello" if same else "traversata", 0) + 1
        )
        if same and "andata_ritorno" in scores:
            scores["andata_ritorno"] += 1
    if not scores:
        return Field(None, 0.0)
    best = max(scores, key=lambda k: scores[k])
    conf = 0.85 if list(scores.values()).count(scores[best]) == 1 else 0.5
    return Field(best, conf, _cite(sources.get(best, "punto di partenza = punto di arrivo")))


def parse_meeting_time(doc: Doc) -> Field:
    hit = doc.find(r"ore\s*(\d{1,2})\s*e\s*mezza")
    if hit:
        m, page, line = hit
        return Field(f"{int(m.group(1)):02d}:30", 0.7, _cite(line), page)
    # nei programmi «Ore 7:00 Ritrovo …, Ore 17:00 Arrivo»: si cerca riga per riga, perché la
    # riga dopo porta spesso l'orario del rientro
    time_ = r"(\d{1,2})(?:[:.,](\d{2}))?"
    for pattern, conf in (
        (rf"\b(?:ore|h)\s*:?\s*{time_}\s*[-–:]?\s*ritrovo", 0.85),
        (rf"ritrovo[^\n]{{0,70}}?\b(?:ore|h)\s*:?\s*{time_}", 0.85),
        (rf"partenza[^\n]{{0,90}}?\b(?:ore|h)\s*:?\s*{time_}", 0.85),
        (rf"\b(?:ore|h)\s*:?\s*{time_}\s*[-–:]?\s*partenza", 0.75),
    ):
        for page, line in doc.lines:
            m = re.search(pattern, line, re.IGNORECASE)
            if m and 4 <= int(m.group(1)) <= 22:
                hh, mm = int(m.group(1)), int(m.group(2) or 0)
                return Field(f"{hh:02d}:{mm:02d}", conf, _cite(line), page)
    # etichetta e orario su due righe («RITROVO:» a capo «ore 6.30»)
    hit = doc.find(rf"ritrovo[^\n]{{0,70}}?\b(?:ore|h)\s*:?\s*{time_}")
    if hit:
        m, page, line = hit
        hh, mm = int(m.group(1)), int(m.group(2) or 0)
        if 4 <= hh <= 22:
            return Field(f"{hh:02d}:{mm:02d}", 0.7, _cite(line), page)
    return Field(None, 0.0)


def parse_transport(doc: Doc) -> Field:
    f = doc.folded
    public = re.search(
        r"autobus di linea|mezzi pubblici|corriera di linea|in treno|\bil treno\b", f
    )
    if public:
        return Field(
            "mezzi pubblici", 0.7, _cite(f[max(0, public.start() - 40) : public.end() + 20])
        )
    private = re.search(r"(?:automobili|auto|macchine) private|mezzi privati", f)
    if private:
        return Field(
            "mezzi propri", 0.8, _cite(f[max(0, private.start() - 40) : private.end() + 20])
        )
    bus = re.search(r"pullman|\bin bus\b|autobus|\bil bus\b", f)
    own = re.search(r"mezzi propri|nostre macchine|le macchine|posti macchina", f)
    if bus and own and re.search(r"pullman o mezzi propri", f):
        return Field("pullman o mezzi propri", 0.8, "pullman o mezzi propri")
    if own:
        return Field("mezzi propri", 0.8, _cite(f[max(0, own.start() - 40) : own.end() + 20]))
    if bus:
        return Field("pullman", 0.8, _cite(f[max(0, bus.start() - 40) : bus.end() + 20]))
    return Field(None, 0.0)


def parse_fee(doc: Doc) -> Field:
    hit = doc.find(r"(?:gratuito per (?:i )?soci|^soci\s*$|soci\s*:?\s*gratis)")
    if hit:
        m, page, line = hit
        return Field(0.0, 0.6, _cite(line), page)
    hit = doc.find(
        r"quota di partecipazione[^\d]{0,30}?(?:€\s*)?(\d{1,3}(?:,\d{2})?)\s*(?:€|euro)?"
    )
    if hit:
        m, page, line = hit
        if "non soci" in _fold(line):
            return Field(0.0, 0.5, _cite(line), page)
        return Field(_num(m.group(1)), 0.9, _cite(line), page)
    # rimborso del viaggio o quota del trasporto: «rimborso di € 5 a passeggero», «Trasporto:
    # € 10,00 a passeggero», «QUOTA BUS € 15,00», «Quota di viaggio: € 15,00», «Costo: 5€»
    hit = doc.find(
        r"(?:rimborso|trasporto|quota bus|quota di viaggio|^costo)\b[^\d\n]{0,40}?(?:€\s*)?"
        r"(\d{1,3}(?:,\d{2})?)\s*(?:€|euro)?"
    )
    if hit:
        m, page, line = hit
        return Field(_num(m.group(1)), 0.6, _cite(line), page)
    return Field(None, 0.0)


REF = r"(?:SI|[EO]?\d{1,3}(?:/?[A-Za-z])?)"


def _refs(text: str) -> list[str]:
    out: list[str] = []
    for tok in re.findall(rf"(?<![\w.]){REF}(?![\w])", text):
        tok = tok.upper().replace("/", "")
        if tok not in out:
            out.append(tok)
    return out


def parse_trails(doc: Doc) -> Field:
    # etichetta "Sentieri" da sola (valori nella riga dopo) o seguita da soli numeri
    for i, (page, line) in enumerate(doc.lines):
        m = re.match(r"^sentieri\s*:?\s*(.*)$", line, re.IGNORECASE)
        if not m:
            continue
        rest = m.group(1).strip()
        if not rest and i + 1 < len(doc.lines):
            rest = doc.lines[i + 1][1]
        rest = re.sub(r"(?i)numeri|n\.|nr\.?", " ", rest)
        if (
            re.fullmatch(r"[\sA-Za-z]{0,3}[\d\s,;\-–/A-Za-z]*", rest)
            and re.search(r"\d|SI", rest)
            and not re.search(r"[a-z]{4,}", rest)
        ):
            return Field(_refs(rest), 0.9, _cite(f"{line} {rest}"), page)
    found: list[str] = []
    first: tuple[int, str] | None = None
    rx = re.compile(
        r"(?:sentier[oi]|segnavia|marcatura)\s*(?:SAT\s*)?(?:n\.?|nr\.?|n°|numero)?\s*:?\s*"
        # anche «32/A»
        r"([EO]?\d{1,3}(?:/?[A-Za-z])?(?:\s*(?:,|e poi|e|-)\s*[EO]?\d{1,3}(?:/?[A-Za-z])?)*)"
        r"(?![\w])(?![/:.]\d)",
        re.IGNORECASE,
    )
    # anche a cavallo di due righe ("sul sentiero / n.30")
    texts = [(p, line) for p, line in doc.lines]
    texts += [
        (doc.lines[i][0], f"{doc.lines[i][1]} {doc.lines[i + 1][1]}")
        for i in range(len(doc.lines) - 1)
    ]
    for page, line in texts:
        for m in rx.finditer(line):
            for ref in _refs(m.group(1)):
                if ref not in found and ref != "SI" and not re.fullmatch(r"\d{4}", ref):
                    found.append(ref)
                    first = first or (page, line)
    if found:
        return Field(found, 0.6, _cite(first[1]) if first else "", first[0] if first else None)
    return Field([], 0.3)


SKIP_TITLE = re.compile(
    r"club alpino|sezione|^cai\b|^sat\b|piazza|\bvia\b|\btel\b|e-mail|www\.|@|^\[|difficolt|"
    r"programma$|^\d{1,2}\s+\w+\s+20\d{2}|^(?:domenica|sabato)\b|^pec\b",
    re.IGNORECASE,
)


def _uppercase(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 8 and sum(c.isupper() for c in letters) / len(letters) >= 0.7


PROPOSE = re.compile(
    r"^(?:.*?\b)?propone\s+(?:una\s+|un['’]?\s*)?(?:escursione|gita|uscita|ciaspolata|camminata)"
    r"(?:\s+facile)?,?\s*(?:sulle|sulla|sullo|sui|sul|alle|alla|allo|agli|ai|al|ad|a|nella|nel|"
    r"lungo il|il|la|lo|le|gli|i)?\s*",
    re.IGNORECASE,
)


def _join_title(lines: list[str]) -> str:
    first = PROPOSE.sub("", lines[0]).strip()
    # «propone una escursione sulla» / «CIMA VERMOI …»: il titolo è sulla riga dopo
    lines = [first, *lines[1:]] if len(first) > 3 else (lines[1:] or lines)
    title = lines[0]
    for nxt in lines[1:]:
        # continua se la riga finisce con una preposizione ("… Abbazia di" / "Monte Maria")
        if re.search(r"\b(?:di|del|della|e|al|alla|a|da|San|S\.)$", title) or _uppercase(nxt):
            title = f"{title} {nxt}"
        else:
            break
    return re.sub(r"\s+", " ", title).strip()


def parse_title(doc: Doc, date: Field) -> Field:
    """Titolo: blocco in maiuscolo subito prima della data (SAT) o righe dopo la data."""
    lines = [t for _, t in doc.lines]
    d = next((i for i, t in enumerate(lines) if date.source and _cite(t) == date.source), None)
    if d is not None:
        before: list[str] = []
        for t in reversed(lines[max(0, d - 2) : d]):
            if _uppercase(t) and not SKIP_TITLE.search(t):
                before.insert(0, t)
            else:
                break
        if before:
            return Field(_join_title(before), 0.6, _cite(before[0]), doc.lines[d][0])
        after = [t for t in lines[d + 1 : d + 6] if not SKIP_TITLE.search(t) and len(t) > 6]
        if after:
            i = lines.index(after[0])
            return Field(_join_title(lines[i : i + 3]), 0.6, _cite(after[0]), doc.lines[i][0])
    first = [t for t in lines[:8] if not SKIP_TITLE.search(t) and len(t) > 6]
    if first:
        return Field(re.sub(r"\s+", " ", " ".join(first[:2])), 0.4, _cite(first[0]))
    return Field(None, 0.0)


def parse_key_points(doc: Doc) -> Field:
    """Luoghi seguiti dalla quota tra parentesi, nell'ordine del testo."""
    rx = re.compile(rf"{NAME}\s*{QUOTA}")
    out: list[dict[str, Any]] = []
    for _, line in doc.lines:
        if re.search(r"punto di (?:partenza|arrivo)|quota massima", line, re.IGNORECASE):
            continue
        for m in rx.finditer(line):
            name = re.sub(
                r"^(?:il|lo|la|al|ai|alla|del|della|dei|dal|nel|sul|verso)\s+", "", m.group(1)
            )
            name = name.strip()
            if len(name) < 3 or name[0].islower():
                continue
            out.append({"nome": name, "quota_m": _num(m.group(2))})
    return Field(out, 0.5 if out else 0.0)


# ------------------------------------------------------------------ voci di calendario


WRITTEN_DATE = re.compile(rf"(?:{WEEKDAYS}\s+)?(\d{{1,2}})\s+({'|'.join(MONTHS)})\s+(20\d{{2}})")
FIELD_LINE = re.compile(
    r"^(?:tipologia|salita|discesa|sviluppo|tempo|difficolt\w*|dislivell\w*|durata|quota\w*|"
    r"ritrovo|partenza|lunghezza|distanza)\b\s*:"
)


def programme_dates(pages: list[tuple[int, str]], year: int) -> list[str]:
    """Le date delle voci di un programma o libretto (AAAA-MM-GG), con gli stessi inizi di voce
    di `calendar_entry`: «12/04/2026», «12 domenica» sotto il mese, «Domenica 12 aprile 2026».
    Gli elenchi di sole date uno sotto l'altro non sono voci."""
    found: list[str] = []
    for _, text in pages:
        lines = text.splitlines()
        header = _fold(text[:200])
        months = [MONTHS[k] for k in MONTHS if re.search(rf"^{k}\b", header, re.M)]
        starts: list[tuple[int, tuple[int, int, int]]] = []
        for i, line in enumerate(lines):
            s = line.strip()
            m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
            if m:
                starts.append((i, (int(m.group(3)), int(m.group(2)), int(m.group(1)))))
                continue
            m = re.match(rf"^(\d{{1,2}})\s+{WEEKDAYS}\b", _fold(s))
            if m and months:
                starts.append((i, (year, months[0], int(m.group(1)))))
                continue
            m = WRITTEN_DATE.fullmatch(_fold(s))
            if m:
                starts.append((i, (int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))))
        if sum(1 for a, b in itertools.pairwise(starts) if b[0] - a[0] == 1) >= 2:
            continue
        for _, (y, mo, d) in starts:
            if 1 <= mo <= 12 and 1 <= d <= 31:
                iso = f"{y:04d}-{mo:02d}-{d:02d}"
                if iso not in found:
                    found.append(iso)
    return found


def calendar_entry(pages: list[tuple[int, str]], date: str) -> list[tuple[int, str]]:
    """Ritaglia la voce di un calendario o libretto per la data indicata (AAAA-MM-GG)."""
    year, month, day = (int(x) for x in date.split("-"))
    out: list[tuple[int, str]] = []
    for n, text in pages:
        lines = text.splitlines()
        starts = []
        for i, line in enumerate(lines):
            s = line.strip()
            m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
            if m:
                starts.append((i, (int(m.group(3)), int(m.group(2)), int(m.group(1)))))
                continue
            m = re.match(rf"^(\d{{1,2}})\s+{WEEKDAYS}\b", _fold(s))
            if m:
                header = _fold(text[:200])
                months = [MONTHS[k] for k in MONTHS if re.search(rf"^{k}\b", header, re.M)]
                starts.append((i, (year, months[0] if months else month, int(m.group(1)))))
                continue
            # «Domenica 1 marzo 2026» su una riga sola, col titolo nella riga prima (programmi
            # pubblicati come pagina web): la voce comincia dal titolo
            m = WRITTEN_DATE.fullmatch(_fold(s))
            if m:
                first = i
                # il titolo può andare a capo: al più due righe sopra, fino a un campo o a una data
                while first > 0 and i - first < 2:
                    prev = lines[first - 1].strip()
                    if not prev or len(prev) > 120 or FIELD_LINE.match(_fold(prev)):
                        break
                    if WRITTEN_DATE.fullmatch(_fold(prev)):
                        break
                    first -= 1
                ymd = (int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
                starts.append((first, ymd))
        consecutive = sum(1 for a, b in itertools.pairwise(starts) if b[0] - a[0] == 1)
        if consecutive >= 2:
            continue  # «12/01/2026», «18/01/2026», … uno sotto l'altro: non sono voci
        for k, (i, ymd) in enumerate(starts):
            if ymd == (year, month, day):
                end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
                out.append((n, "\n".join(lines[i:end])))
    # un elenco di sole date (es. il calendario dell'alpinismo giovanile) non è la voce
    content = sum(len(re.sub(r"[\d/\s|-]", "", t)) for _, t in out)
    if not out or content < 40:
        return _short_date_entry(pages, month, day) or out
    return out


TITLE_CONTINUES = re.compile(
    r"\b(?:DI|DA|DEL|DELLA|DEI|DELLE|DAL|DALLA|AL|ALLA|AI|A|E|IN|CON|PER|SUL|SULLA|MONTE|CIMA|"
    r"PASSO|LAGO|LAGHI|RIFUGIO|VAL|PUNTA|CORNO|PIZ|[-–])$"
)
TITLE_GOES_ON = re.compile(r"^(?:DI|DEL|DELLA|DEI|DELLE|AL|ALLA|AI|E|[-–])\b")
GENERIC_TITLE = re.compile(
    r"^(?:gita|giro|sentiero|spiedo|pasta|festa|camminata|escursione|trekking|ciaspolata|"
    r"ferrata|traversata|anello|uscita|cena|settimana|manutenzione|pulizia)\b"
)
SHORT_DATE = re.compile(r"^(\d{1,2})(?:-\d{1,2})?/(\d{1,2})(?:-\d{1,2})?\s*(-)?\s*$")
NOT_TITLE = re.compile(
    r"calendario|programma|collaborazione|termine iscrizioni|indice|legenda|scala delle", re.I
)
MINOR = {
    "di",
    "da",
    "del",
    "della",
    "dei",
    "delle",
    "dal",
    "dalla",
    "al",
    "alla",
    "a",
    "e",
    "in",
    "con",
    "per",
    "sul",
    "sulla",
    "il",
    "la",
    "lo",
    "le",
    "gli",
    "i",
}


def _title_case(text: str) -> str:
    words = re.sub(r"\s+", " ", text).strip().lower().split(" ")
    return " ".join(w if (k and w in MINOR) else w[:1].upper() + w[1:] for k, w in enumerate(words))


def _page_titles(lines: list[str]) -> list[str]:
    """Titoli in maiuscolo di una pagina, nell'ordine e senza ripetizioni.

    Due righe maiuscole sono lo stesso titolo solo se la prima resta in sospeso («… GIRO DEI
    LAGHI» / «DEL CEVEDALE») o la seconda comincia con una preposizione.
    """
    titles: list[str] = []
    block: list[str] = []
    for t in [*lines, ""]:
        is_title = (
            bool(t) and _uppercase(t) and not NOT_TITLE.search(t) and not re.search(r"\d{2,}", t)
        )
        if is_title and block and (TITLE_CONTINUES.search(block[-1]) or TITLE_GOES_ON.match(t)):
            block.append(t)
            continue
        if block:
            title = re.sub(r"\s+", " ", " ".join(block))
            if _fold(title) not in {_fold(x) for x in titles}:
                titles.append(title)
        block = [t] if is_title else []
    return titles


def _short_date_entry(pages: list[tuple[int, str]], month: int, day: int) -> list[tuple[int, str]]:
    """Programmi con le date «gg/mm» senza anno, una o due gite per pagina (es. SAT Ledrense).

    La voce è la pagina intera; il titolo è la riga in maiuscolo nella stessa posizione della
    data tra quelle della pagina (date e titoli sono nello stesso ordine) e viene messo in testa.
    """
    found: list[tuple[bool, int, str, list[tuple[int, int]], list[str]]] = []
    for n, text in pages:
        lines = [t.strip() for t in text.splitlines()]
        dates: list[tuple[int, int]] = []
        ranges: set[tuple[int, int]] = set()
        skip_next = False
        for t in lines:
            m = SHORT_DATE.match(t)
            if not m:
                continue
            if skip_next:  # «16/09-» seguito da «30/09»: fine dell'intervallo
                skip_next = False
                continue
            dates.append((int(m.group(1)), int(m.group(2))))
            if m.group(3):
                ranges.add(dates[-1])
            skip_next = bool(m.group(3))
        if (day, month) in dates:
            # un giorno singolo vale più dell'inizio di un intervallo («03/05-10/05»)
            found.append(((day, month) in ranges, n, text, dates, lines))
    for _, n, text, dates, lines in sorted(found, key=lambda x: x[0]):
        titles = _page_titles(lines)
        k = dates.index((day, month))
        title = titles[k] if k < len(titles) else (titles[0] if titles else "")
        head = f"{day:02d}/{month:02d} {_title_case(title)}" if title else ""
        return [(n, f"{head}\n{text}" if head else text)]
    return []


# ------------------------------------------------------------------ insieme


def _calendar_title(doc: Doc) -> Field:
    """Prima riga della voce senza data e giorno: "09 sabato ANELLO DA TISO …". Nei programmi
    pubblicati come pagina web il titolo sta sopra la data scritta per esteso, anche su due
    righe."""
    head = doc.lines[:4]
    dated = [k for k, (_, line) in enumerate(head) if WRITTEN_DATE.fullmatch(_fold(line.strip()))]
    if dated and dated[0] > 0:
        title = " ".join(line.strip() for _, line in head[: dated[0]])
        return Field(re.sub(r"\s+", " ", title), 0.7, _cite(head[0][1]), head[0][0])
    for page, line in doc.lines[:4]:
        t = re.sub(
            rf"^\d{{1,2}}(?:/\d{{1,2}}(?:/\d{{4}})?)?\s*(?:{WEEKDAYS}|gio|dom|sab|ven|mer|mar|lun)?\b\.?",
            "",
            line,
            flags=re.IGNORECASE,
        ).strip()
        if len(t) > 6:
            return Field(re.sub(r"\s+", " ", t), 0.7, _cite(line), page)
    return Field(None, 0.0)


def parse(
    pages: list[tuple[int, str]], hint: str = "", entry_date: str | None = None
) -> dict[str, Any]:
    """Campi di una locandina; con `entry_date` le pagine sono una voce di calendario."""
    doc = Doc(pages)
    if entry_date:
        date = Field(entry_date, 0.8, "data della voce del calendario")
        title = _calendar_title(doc)
    else:
        date = parse_date(doc, hint)
        title = parse_title(doc, date)
    start_name, start_ele, end_name = parse_start(doc)
    sub = doc.find(
        r"\((?i:traversata|escursione)\s+(?i:da|dalla|dal)\s+([^()]+?)\s+(?i:a|al|alla|fino a)\s+"
        r"([^()–-]+)"
    )
    if sub:
        m, page, line = sub
        if start_name.value is None:
            start_name = Field(m.group(1).strip(), 0.6, _cite(line), page)
        if end_name.value is None:
            end_name = Field(m.group(2).strip(" .)"), 0.6, _cite(line), page)
    route_type = parse_route_type(doc, start_name, end_name, title.value or "")
    if entry_date and start_name.value is None and title.value:
        # nei calendari la prima località del titolo è di solito la partenza (non «Gita sociale»,
        # «Giro delle cime», «Spiedo in Nota»: nomi della gita, non luoghi)
        first = re.split(r"\s+[-–]\s*|\s*[-–]\s+", title.value)[0].strip()
        if not GENERIC_TITLE.match(_fold(first)):
            start_name = Field(first.title(), 0.4, title.source, title.page)
    up, down = parse_elevation_gain(doc)
    if (
        down.value is None
        and up.value is not None
        and route_type.value
        in {
            "anello",
            "andata_ritorno",
        }
    ):
        down = Field(up.value, min(up.confidence, route_type.confidence) * 0.8, up.source, up.page)
    if end_name.value is None and route_type.value == "traversata" and title.value:
        m = re.search(
            r"\b[Dd][Aa]\s+(.+?)\s+(?:[Aa]|[Aa][Ll]|[Aa][Ll][Ll][Aa]|fino a)\s+(.+)$", title.value
        )
        if m:
            end_name = Field(m.group(2).strip(" .,"), 0.5, title.source, title.page)
    if end_name.value is None and route_type.value in {"anello", "andata_ritorno"}:
        end_name = Field(start_name.value, start_name.confidence * 0.8, start_name.source)
    fields = {
        "titolo": title,
        "data": date,
        "difficolta": parse_difficulty(doc),
        "tipo_percorso": route_type,
        "durata": parse_duration(doc),
        "distanza_km": parse_distance(doc),
        "salita_m": up,
        "discesa_m": down,
        "quota_max_m": parse_max_elevation(doc),
        "partenza_nome": start_name,
        "partenza_quota_m": start_ele,
        "arrivo_nome": end_name,
        "ora_ritrovo": parse_meeting_time(doc),
        "mezzi": parse_transport(doc),
        "quota_eur": parse_fee(doc),
        "sentieri": parse_trails(doc),
        "punti_chiave": parse_key_points(doc),
    }
    return {k: asdict(v) for k, v in fields.items()}
