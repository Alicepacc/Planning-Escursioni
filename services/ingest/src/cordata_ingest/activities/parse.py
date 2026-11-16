"""Parser a regole delle locandine (SPEC §7.3, primo passaggio "Parser + Claude Code").

Estrae i campi dello schema del §2 dal testo già ripulito dei dati personali (`extract.py`).
Ogni campo ha `value`, `confidence` (0-1) e `source` (la riga del documento da cui viene, per
la verifica e per la revisione). I campi a bassa confidenza sono quelli che la revisione
(Claude Code, nella sessione di lavoro) deve controllare: nessuna chiamata a API a pagamento.

Copre i modelli visti nel pilota: locandine CAI Bolzano (campi etichettati), CAI Bressanone
(etichette maiuscole), SAT (testo libero), libretti e calendari annuali (una voce per attività).
"""

from __future__ import annotations

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


def parse_date(doc: Doc, hint: str = "") -> Field:
    rx = rf"(?:{WEEKDAYS}\s*,?\s*)?(\d{{1,2}})\s+({'|'.join(MONTHS)})\s*(20\d{{2}})"
    for page, line in doc.lines[:40]:
        m = re.search(rx, _fold(line))
        if m:
            day, month, year = int(m.group(1)), MONTHS[m.group(2)], int(m.group(3))
            return Field(f"{year:04d}-{month:02d}-{day:02d}", 0.9, _cite(line), page)
    m = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", hint) or None
    if m:
        return Field(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", 0.6, f"nome del file: {hint}")
    m = re.search(r"(\d{2})[.-](\d{2})[.-](20\d{2})", hint)
    if m:
        return Field(f"{m.group(3)}-{m.group(2)}-{m.group(1)}", 0.6, f"nome del file: {hint}")
    return Field(None, 0.0)


def _norm_difficulty(raw: str) -> str | None:
    raw = raw.upper().replace(".", "").replace(" ", "")
    if raw in {"E-EE", "EE-E"}:
        return raw
    for d in DIFFICULTIES:
        if raw.startswith(d):
            return "EAI" if raw.startswith("EAI") else d
    return None


def parse_difficulty(doc: Doc) -> Field:
    # etichetta senza distinzione di maiuscole, valore solo in maiuscolo (scala CAI)
    patterns = [
        (
            r"(?i:difficolt[aà])\s*:?\s*((?:E\.?){2}A\.?|EAI(?:-F)?|E-EE|EE-E|E\.?E\.?|E|T)(?![\w.])",
            0.95,
        ),
        (r"(?i:escursione)\s*:\s*(EAI|EEA|EE|E|T)\b", 0.95),
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


def parse_duration(doc: Doc) -> Field:
    num = r"(\d{1,2}(?:[.,:]\d{1,2})?)"
    # salita + discesa: "circa 3 ore in salita e circa 1,5 ore in discesa"
    hit = doc.find(rf"{num}\s*or[ae]\s*in\s*salita\D+{num}\s*or[ae]\s*in\s*discesa")
    if hit:
        m, page, line = hit
        return Field(_hm(_hours(m.group(1)) + _hours(m.group(2))), 0.85, _cite(line), page)
    hit = doc.find(rf"totale\s*{num}\s*(?:h|ore)\b")
    if hit:
        m, page, line = hit
        return Field(_hm(_hours(m.group(1))), 0.9, _cite(line), page)
    hit = doc.find(r"(?:andata e ritorno|a/r)[^\d]{0,15}h\s*:?\s*(\d{1,2})\s*e\s*(\d{2})")
    if hit:
        m, page, line = hit
        return Field(_hm(int(m.group(1)) + int(m.group(2)) / 60), 0.8, _cite(line), page)
    # mai "ore N" da solo: è quasi sempre un orario ("ritrovo ore 7", "ore 8 e mezza")
    patterns = [
        rf"ore di cammino(?: effettiv[oei])?\s*:?\s*(?:ca\.?|circa)?\s*{num}\s*(?:h|ore)?",
        rf"ore di cammino\s*:?\s*{num}",
        rf"tempo di percorrenza\s*:?\s*(?:circa)?\s*{num}\s*(?:h|ore)",
        rf"durata(?:\s*a/r)?\s*:?\s*{num}\s*(?:h|ore)",
        rf"(?:percorso|cammino|tempi?)\s*:?\s*(?:ore|h)\s*{num}",
        rf"\(ore\s*{num}\)",
        rf"(?<![\d:.])\b{num}\s*h(?:\s*circa)?\b",
    ]
    for i, pattern in enumerate(patterns):
        hit = doc.find(pattern)
        if hit:
            m, page, line = hit
            # "5h30’": minuti dopo la h
            tail = re.match(r"\s*h\s*(\d{2})", line[m.end(1) :])
            hours = _hours(m.group(1)) + (int(tail.group(1)) / 60 if tail else 0)
            if 0.5 <= hours <= 14:
                return Field(_hm(hours), 0.9 if i < 4 else 0.6, _cite(line), page)
    return Field(None, 0.0)


def parse_distance(doc: Doc) -> Field:
    patterns = [
        (r"(?:sviluppo|distanza|lunghezza)[^\d\n]{0,40}?(\d{1,2}(?:[.,]\d{1,2})?)\s*km", 0.9),
        (r"(?:sviluppo|distanza)\s*:?\s*(?:km\.?\s*)(\d{1,2}(?:[.,]\d{1,2})?)", 0.9),
        (r"^km\s*:?\s*(\d{1,2}(?:[.,]\d{1,2})?)", 0.9),
        (r"^sviluppo$", 0.0),
        (r"[-–]\s*(\d{1,2}(?:[.,]\d)?)\s*km\b", 0.6),
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
        rf"(?:in )?salita e (?:in )?discesa\s*:?\s*(?:in salita e in discesa\s*)?{m_}?\s*{v}",
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
    hit = doc.find(rf"\+\s*{v}\s*/\s*-\s*{v}")
    if hit:
        m, page, line = hit
        return (
            Field(_num(m.group(1)), 0.85, _cite(line), page),
            Field(_num(m.group(2)), 0.85, _cite(line), page),
        )
    for pattern in (
        rf"salita\s*:?\s*(?:di\s*)?(?:circa\s*)?{m_}?\s*{v}",
        rf"{v}\s*{m_}?\s*(?:di\s*)?salita",
        rf"dislivello positivo(?:\s*itinerario\s*\d+)?\s*:?\s*{v}",
        rf"dislivello in salita\s*:?\s*(?:circa)?\s*{v}",
    ):
        hit = doc.find(pattern)
        if hit:
            m, page, line = hit
            up = Field(_num(m.group(1)), 0.85, _cite(line), page)
            break
    for pattern in (
        rf"discesa\s*:?\s*(?:di\s*)?(?:circa\s*)?{m_}?\s*{v}",
        rf"{v}\s*{m_}?\s*(?:di\s*)?discesa",
    ):
        hit = doc.find(pattern)
        if hit:
            m, page, line = hit
            down = Field(_num(m.group(1)), 0.85, _cite(line), page)
            break
    if up is None:
        hit = doc.find(rf"dislivell[oi][^\d\n]{{0,25}}?(?:\+\s*)?{m_}?\s*{v}\s*{m_}?")
        if hit:
            m, page, line = hit
            up = Field(_num(m.group(1)), 0.7, _cite(line), page)
        else:
            hit = doc.find(rf"\+\s*{v}\s*m\b")
            if hit:
                m, page, line = hit
                up = Field(_num(m.group(1)), 0.6, _cite(line), page)
    return up or Field(None, 0.0), down or Field(None, 0.0)


def parse_max_elevation(doc: Doc) -> Field:
    label = doc.after_label(r"quota massima(?: raggiunta)?", 1)
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
    for page, line in doc.lines:
        if re.search(
            r"dislivell|sviluppo|lunghezza|(?:salita|discesa)\s*:?\s*(?:di\s*)?(?:circa\s*)?"
            r"(?:m\.?|mt\.?)?\s*\d",
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
QUOTA_ANY = r"(?:\(?\s*(?:m\.?|mt\.?)\s*(\d\.\d{3}|\d{4})\b|\b(\d\.\d{3}|\d{4})\s*(?:m|mt|M)\b\.?)"
NAME = (
    r"((?:[A-ZÀ-Ý][\w'’-]+|S\.)(?:\s+(?:[A-ZÀ-Ý][\w'’-]+|S\.|di|de|da|al|alla|del|dei|delle|"
    r"della|dal|dalla))*)"
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
    end = doc.after_label(r"punto di arrivo", 1)
    if start:
        name, ele = _place(start[0])
        f_name = Field(name, 0.9, _cite(start[2]), start[1])
        f_ele = Field(ele, 0.9 if ele else 0.0, _cite(start[2]), start[1])
        f_end = Field(_place(end[0])[0], 0.9, _cite(end[2]), end[1]) if end else Field(None, 0.0)
        return f_name, f_ele, f_end
    # parole chiave senza distinzione di maiuscole, nomi propri con l'iniziale maiuscola
    art = r"(?i:il|lo|la|l'|al|alla|ai|del|della|dei)"
    phrases = [
        rf"(?i:raggiung\w+|parcheggio de\w*)\s+(?:{art}\s*)?{NAME}\s*{QUOTA},?\s*"
        r"(?i:punto di partenza)",
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
            r"a ritroso",
            r"\ba/r\b",
            r"andata e ritorno",
            r"ritorno (?:avverr?a|avviene) lungo lo stesso",
        ],
        "anello": [r"\banello\b", r"circolare", r"chiude(?:re|ndo|remo)? (?:il nostro )?anello"],
        "traversata": [
            r"traversata",
            r"\bdove termina\b",
            r"\btappa\b",
        ],
    }
    scores: dict[str, int] = {}
    sources: dict[str, str] = {}
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
    for pattern, conf in (
        (r"ritrovo[^\n]{0,70}?(?:ore|h)\s*:?\s*(\d{1,2})(?:[:.,](\d{2}))?", 0.85),
        (r"partenza[^\n]{0,30}?(?:ore|h)\s*:?\s*(\d{1,2})(?:[:.,](\d{2}))?", 0.85),
    ):
        hit = doc.find(pattern)
        if hit:
            m, page, line = hit
            hh, mm = int(m.group(1)), int(m.group(2) or 0)
            if 4 <= hh <= 22:
                return Field(f"{hh:02d}:{mm:02d}", conf, _cite(line), page)
    return Field(None, 0.0)


def parse_transport(doc: Doc) -> Field:
    f = doc.folded
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
    return Field(None, 0.0)


REF = r"(?:SI|[EO]?\d{1,3}[A-Za-z]?)"


def _refs(text: str) -> list[str]:
    out: list[str] = []
    for tok in re.findall(rf"(?<![\w.]){REF}(?![\w])", text):
        tok = tok.upper()
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
        r"([EO]?\d{1,3}[A-Za-z]?(?:\s*(?:,|e poi|e|-)\s*[EO]?\d{1,3}[A-Za-z]?)*)"
        r"(?![\w])",
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


def _join_title(lines: list[str]) -> str:
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
        for k, (i, ymd) in enumerate(starts):
            if ymd == (year, month, day):
                end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
                out.append((n, "\n".join(lines[i:end])))
    return out


# ------------------------------------------------------------------ insieme


def _calendar_title(doc: Doc) -> Field:
    """Prima riga della voce senza data e giorno: "09 sabato ANELLO DA TISO …"."""
    for page, line in doc.lines[:4]:
        t = re.sub(
            rf"^\d{{1,2}}(?:/\d{{1,2}}/\d{{4}})?\s*(?:{WEEKDAYS}|gio|dom|sab|ven|mer|mar|lun)?\b\.?",
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
    route_type = parse_route_type(doc, start_name, end_name, title.value or "")
    if entry_date and start_name.value is None and title.value:
        # nei calendari la prima località del titolo è di solito la partenza
        first = re.split(r"\s+[-–]\s*|\s*[-–]\s+", title.value)[0].strip()
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
