"""Classificazione dei documenti delle sezioni (SPEC §7.3).

Due livelli: dal **nome** (titolo e file, segnale debole, usato per scegliere cosa scaricare) e
dal **testo** del PDF (decisivo). Categorie: escursionismo, ciaspolata (EAI), cicloescursionismo,
alpinismo, corso, culturale, programma (calendario o libretto con più gite), amministrativo,
altro. Nella v1 si importano solo escursionismo, ciaspolata e programma; il resto viene scartato
con il motivo.
"""

from __future__ import annotations

import re
import unicodedata

IMPORTED = {"escursionismo", "ciaspolata", "programma"}

# parole chiave per categoria, in ordine di priorità (la prima che corrisponde vince)
NAME_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "amministrativo",
        (
            "modulo",
            "domanda di iscrizione",
            "rinnovo",
            "gdpr",
            "informativa",
            "privacy",
            "assemblea",
            "bilancio",
            "verbale",
            "statuto",
            "regolamento",
            "convocazione",
            "assicurazion",
            "massimali",
            "circolare",
            "funzioni incarichi",
            "quote sociali",
            "guida al rinnovo",
            "guida alla prima iscrizione",
            "comunicato stampa",
            "tesseramento",
        ),
    ),
    ("corso", ("corso", "corsi", "scuola", "lezione", "date corso", "formazione")),
    ("cicloescursionismo", ("ciclo", "mtb", "bici", "e-bike", "ebike", "mountain bike")),
    ("ciaspolata", ("ciaspol", "ciaspole", "racchette da neve", "schneeschuh", "eai")),
    (
        "alpinismo",
        (
            "alpinismo",
            "ferrata",
            "arrampicata",
            "scialpinismo",
            "sci alpinismo",
            "skitour",
            "ghiacciaio",
            "cascate di ghiaccio",
        ),
    ),
    (
        "culturale",
        (
            "serata",
            "conferenza",
            "proiezione",
            "presentazione",
            "mostra",
            "concerto",
            "castagnata",
            "festa",
            "cena",
            "pranzo sociale",
            "film",
            "libro",
            "coro",
        ),
    ),
    (
        "programma",
        (
            "programma",
            "calendario",
            "libretto",
            "attività 20",
            "attivita 20",
            "gite 20",
            "escursioni 20",
            "tourenprogramm",
            "jahresprogramm",
        ),
    ),
    (
        "escursionismo",
        (
            "escursione",
            "gita",
            "locandina",
            "anello",
            "traversata",
            "sentiero",
            "rifugio",
            "malga",
            "lago",
            "laghi",
            "monte",
            "cima",
            "passo",
            "forcella",
            "val ",
            "valle",
            "trekking",
            "tappa",
            "giro",
            "wanderung",
            "tour",
        ),
    ),
]

# nome file con data: NN_YYYYMMDD-Titolo, YYYY_MM_DD-Titolo, YYYY-MM-DD Titolo (Bolzano)
DATED_NAME = re.compile(
    r"(^|[^\d])(\d{1,2}[a-z]?_)?(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", re.IGNORECASE
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[_\-–]+", " ", text)


def classify_name(name: str) -> str:
    """Categoria preliminare dal titolo e dal nome del file (segnale debole)."""
    norm = normalize(name)
    for category, words in NAME_RULES:
        if any(w in norm for w in words):
            return category
    if DATED_NAME.search(name):
        return "escursionismo?"  # data nel nome ma nessuna parola chiave: da verificare
    return "altro"


TEXT_SIGNALS: dict[str, tuple[str, ...]] = {
    "escursionismo": (
        "difficolta",
        "dislivello",
        "tempo di percorrenza",
        "ore di cammino",
        "durata",
        "partenza",
        "rientro",
        "capogita",
        "accompagnator",
        "escursione",
        "sentiero",
        "segnavia",
    ),
    "ciaspolata": ("ciaspol", "racchette da neve", "eai", "arva", "pala", "sonda"),
    "cicloescursionismo": ("bici", "mtb", "casco", "ciclo", "km in sella"),
    "corso": ("lezione", "corso", "iscrizione al corso", "istruttor", "programma del corso"),
}


def classify_text(text: str, name: str = "") -> tuple[str, str]:
    """Categoria e motivo, dal testo del PDF (e dal nome come spareggio)."""
    norm = normalize(text)
    scores = {cat: sum(norm.count(w) for w in words) for cat, words in TEXT_SIGNALS.items()}
    gite = len(re.findall(r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b", text))
    by_name = classify_name(name)
    if by_name in {"amministrativo", "culturale"} and scores["escursionismo"] < 4:
        return by_name, f"nome «{by_name}» e pochi indizi di escursione nel testo"
    if gite >= 12 and scores["escursionismo"] >= 4 and len(text) > 6000:
        return "programma", f"{gite} date nel testo: calendario o libretto con più attività"
    if (
        scores["cicloescursionismo"] >= 3
        and scores["cicloescursionismo"] > scores["escursionismo"] / 2
    ):
        return "cicloescursionismo", "lessico ciclistico prevalente"
    if scores["ciaspolata"] >= 2 and ("ciaspol" in norm or "eai" in norm.split()):
        return "ciaspolata", "ciaspole o difficoltà EAI nel testo"
    if scores["corso"] >= 3 and scores["corso"] >= scores["escursionismo"]:
        return "corso", "lessico da corso prevalente"
    if scores["escursionismo"] >= 3:
        return "escursionismo", "difficoltà, dislivello, tempi o partenza nel testo"
    return by_name if by_name != "escursionismo?" else "altro", "pochi indizi nel testo"
