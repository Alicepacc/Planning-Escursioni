"""Estrazione del testo dei PDF archiviati (SPEC §7.3).

- Testo e blocchi con coordinate da PyMuPDF; OCR con Tesseract (ita+deu) solo per le pagine
  che sono immagini (quasi nessun carattere di testo).
- **Dati personali rimossi prima di salvare** (SPEC §2 e §7.3): email, numeri di telefono e i
  nomi che seguono le etichette di ruolo (capogita, accompagnatori, referente…). Il testo pulito
  finisce nell'archivio privato `data/activities/text/<id>.json`; il PDF originale resta solo
  nell'archivio grezzo.
- Indicatori di layout (pagine OCR, colonne, blocchi) per riconoscere i PDF "difficili".
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pymupdf

from ..config import data_dir
from .archive import raw_dir

OCR_MIN_CHARS = 40  # sotto questa soglia una pagina con immagini è considerata una scansione
OCR_DPI = 300
OCR_LANGS = "ita+deu"

# ---------------------------------------------------------------- dati personali

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# cellulari: 3xx + 7 cifre (separatori singoli ammessi); così "332 360 326" (sentieri) non è
# un telefono. Fissi e numeri con prefisso solo nelle righe con parole di contatto.
MOBILE = re.compile(r"(?<![\d])(?:\+39[\s.]?)?3\d{2}(?:[\s./-]?\d){7}(?![\d])")
ANY_PHONE = re.compile(r"(?<![\d])(?:\+39[\s.]?)?0\d{1,3}(?:[\s./-]?\d){5,8}(?![\d])")
DATE_LIKE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}$")
CONTACT_WORDS = re.compile(
    r"\b(tel|tel\.|telefono|cell|cell\.|cellulare|whatsapp|contatt|info|informazioni|"
    r"iscrizion|prenotazion|anmeldung)",
    re.IGNORECASE,
)
ROLE_LABEL = re.compile(
    r"\b(capo\s?gita|capigita|capogruppo|accompagnator[ei]|accompagnatrice|"
    r"accompagnano|referent[ei]|coordinator[ei]|coordinatrice|direttor[ei] di escursione|"
    r"organizzator[ei] (?:della gita|tecnic\w+)|"
    r"responsabil[ei](?: dell[a'’]\s?| di )?\s?(?:gita|escursione|uscita)|"
    r"tourenleiter\w*|begleit\w*|in collaborazione con gli accompagnatori)\b",
    re.IGNORECASE,
)
PERSON_LINE = re.compile(r"^(?:[A-ZÀ-Ý][a-zà-ÿ']+\.?\s+){1,3}[A-ZÀ-Ý][a-zà-ÿ']+\.?$")
PLACEHOLDER = re.compile(r"\[(?:telefono|email) rimoss[oa]\]")
CAPITALIZED = re.compile(r"\b[A-ZÀ-Ý][A-Za-zÀ-ÿ']+\b")
# parole con iniziale maiuscola che nelle righe di contatto non sono nomi di persona
NOT_NAMES = {
    w.lower()
    for w in [
        "Info",
        "Informazioni",
        "Iscrizioni",
        "Iscrizione",
        "Adesioni",
        "Prenotazioni",
        "Prenotazione",
        "Contatti",
        "Tel",
        "Telefono",
        "Cell",
        "Cellulare",
        "WhatsApp",
        "Whatsapp",
        "Sms",
        "Mail",
        "Email",
        "E-mail",
        "Fax",
        "Pec",
        "Segreteria",
        "Sezione",
        "Sede",
        "CAI",
        "SAT",
        "SOSAT",
        "Club",
        "Alpino",
        "Italiano",
        "Commissione",
        "Escursionismo",
        "Via",
        "Piazza",
        "Corso",
        "Viale",
        "Largo",
        "Entro",
        "Chiusura",
        "Quota",
        "Soci",
        "Socio",
        "Non",
        "Per",
        "Presso",
        "Orari",
        "Lunedì",
        "Martedì",
        "Mercoledì",
        "Giovedì",
        "Venerdì",
        "Sabato",
        "Domenica",
        "Gennaio",
        "Febbraio",
        "Marzo",
        "Aprile",
        "Maggio",
        "Giugno",
        "Luglio",
        "Agosto",
        "Settembre",
        "Ottobre",
        "Novembre",
        "Dicembre",
        "Il",
        "La",
        "Le",
        "Lo",
        "Gli",
        "I",
        "Un",
        "Una",
        "Al",
        "Alla",
        "Ai",
        "Dal",
        "Dalla",
        "Del",
        "Della",
        "Da",
        "Di",
        "In",
        "Con",
        "Su",
        "Ore",
        "Vi",
        "Ci",
        "Si",
        "E",
        "Ed",
        "O",
        "Anmeldung",
        "Info-Tel",
        "Tourenleiter",
        "Bei",
        "Bis",
        "Uhr",
    ]
}


def _redact_phones(line: str, contact: bool) -> tuple[str, int]:
    count = 0

    def sub(m: re.Match[str]) -> str:
        nonlocal count
        if DATE_LIKE.match(m.group(0).strip()):
            return m.group(0)
        count += 1
        return "[telefono rimosso]"

    line = MOBILE.sub(sub, line)
    if contact or "+39" in line:
        line = ANY_PHONE.sub(sub, line)
    return line, count


def _redact_contact_names(line: str) -> tuple[str, int]:
    count = 0

    def sub(m: re.Match[str]) -> str:
        nonlocal count
        if m.group(0).lower() in NOT_NAMES:
            return m.group(0)
        count += 1
        return "[nome rimosso]"

    line = CAPITALIZED.sub(sub, line)
    line = re.sub(r"\[nome rimosso\](?:[\s,]+\[nome rimosso\])+", "[nome rimosso]", line)
    return line, count


# tabelle dei calendari con una colonna di referenti: "Cognome I." (anche più nomi uniti)
TABLE_ROLE_HEADER = re.compile(
    # intestazione di colonna, da sola sulla riga ("Referente", "Categoria Tipologia Referente");
    # "refer\w{0,3}nt" tollera refusi come "Referernte" (calendario SAT Rovereto 2021)
    r"^\s*(?:(?:categoria|tipologia|data|destinazione|difficolt\S*|dislivello)\s+)*"
    r"(?:refer\w{0,3}nt[ei]|capo\s?gita|capigita|accompagnator[ei]|tourenleiter)\s*/?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
# "Passo S. Pellegrino", "Monte S. Vigilio": luoghi, non "Cognome I."
PLACE_WORDS = (
    "passo|monte|rifugio|malga|lago|val|valle|cima|forcella|chiesa|chiesetta|borgo|ponte|"
    "colle|croda|sasso|piazza|via|santuario|località|localita|maso|castel|castello|baita|pian"
)
SURNAME_INITIAL = re.compile(
    rf"\b(?!(?i:{PLACE_WORDS})\b)[A-ZÀ-Ý][a-zà-ÿ']+(?:[-–][A-ZÀ-Ý][a-zà-ÿ']+)*[ \t]+[A-ZÀ-Ý]\."
    r"(?![A-Za-z])(?:[ \t]*(?:-[ \t]*)?[A-ZÀ-Ý][a-zà-ÿ']+(?:[ \t]+[A-ZÀ-Ý]\.(?![A-Za-z]))?)*"
)
SURNAME_CHAIN = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ']+(?:-[A-ZÀ-Ý][a-zà-ÿ']+){2,}\b")


# titoli degli accompagnatori e istruttori CAI: la riga vicina con un nome è una persona
QUALIFICATION = re.compile(
    r"^(?:(?:AE|ASE|AAG|ASAG|ASC|ONC|ONCN|ORTAM|INA|IA|ISA|IS|IAL|ISFE|AC|OSM|EAI|EEA|ANE|"
    r"INSA|ISBA|IAG|ISSI)(?:[\s–/-]+|$))+$"
)


def _is_person_line(line: str) -> bool:
    words = line.split()
    return bool(PERSON_LINE.match(line)) and not re.match(
        rf"(?i:{PLACE_WORDS})\b", words[0] if words else ""
    )


def _redact_rosters(text: str, table: bool) -> tuple[str, int]:
    """Righe "Nome Cognome" accanto a un titolo (AE, ASC…) o in una tabella di referenti."""
    lines = text.splitlines()
    removed = 0
    for i, line in enumerate(lines):
        s = line.strip()
        bare = re.sub(rf"\s+{QUALIFICATION.pattern[1:-1]}$", "", s) if s else s
        if not s or not _is_person_line(bare):
            continue
        near = [lines[j].strip() for j in (i - 1, i + 1) if 0 <= j < len(lines)]
        if table or bare != s or any(QUALIFICATION.match(n) for n in near if n):
            lines[i] = "[nome rimosso]"
            removed += 1
    return "\n".join(lines), removed


def sanitize(text: str, table: bool = False) -> tuple[str, int]:
    """Rimuove email, telefoni e nomi dopo le etichette di ruolo. Restituisce (testo, n).

    `table=True` per i documenti con una tabella di referenti (anche nelle pagine successive
    a quella con l'intestazione): lì ogni riga "Nome Cognome" è una persona.
    """
    out: list[str] = []
    removed = 0
    table = table or bool(TABLE_ROLE_HEADER.search(text))
    if table:
        text, n1 = SURNAME_INITIAL.subn("[nome rimosso]", text)
        text, n2 = SURNAME_CHAIN.subn("[nome rimosso]", text)
        removed += n1 + n2
    text, n3 = _redact_rosters(text, table)
    removed += n3
    redact_next = 0
    for raw in text.splitlines():
        line = raw
        line, n = EMAIL.subn("[email rimossa]", line)
        removed += n
        line, n = _redact_phones(line, bool(CONTACT_WORDS.search(line)))
        removed += n
        if PLACEHOLDER.search(line):
            # riga di contatto: le parole maiuscole che non sono termini comuni sono nomi
            line, n = _redact_contact_names(line)
            removed += n
        stripped = line.strip()
        if redact_next and stripped:
            # righe successive a un'etichetta di ruolo: nomi propri (o resti di contatti)
            if PERSON_LINE.match(stripped) or "rimoss" in stripped:
                out.append("[nome rimosso]")
                removed += 1
                redact_next -= 1
                continue
            redact_next = 0
        m = ROLE_LABEL.search(line)
        if m:
            head, tail = line[: m.end()], line[m.end() :]
            if re.search(r"[A-Za-zÀ-ÿ]{2,}", tail):
                line = head + ": [nome rimosso]"
                removed += 1
            else:
                redact_next = 3  # etichetta da sola: i nomi sono nelle righe seguenti
        out.append(line)
    return "\n".join(out), removed


# ---------------------------------------------------------------- estrazione


def _ocr(page: pymupdf.Page) -> str:
    if not shutil.which("tesseract"):
        return ""
    pix = page.get_pixmap(dpi=OCR_DPI)
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "pagina.png"
        pix.save(img)
        res = subprocess.run(
            ["tesseract", str(img), "stdout", "-l", OCR_LANGS, "--psm", "3"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    return res.stdout


def _columns(blocks: list[tuple[float, ...]], width: float) -> int:
    """Stima del numero di colonne: blocchi affiancati che si sovrappongono in verticale."""
    texty = [b for b in blocks if b[6] == 0 and str(b[4]).strip()]
    left = [b for b in texty if b[2] <= width * 0.55]
    right = [b for b in texty if b[0] >= width * 0.45]
    side_by_side = sum(1 for a in left for b in right if a[1] < b[3] and b[1] < a[3])
    return 2 if side_by_side >= 3 else 1


def extract_pdf(path: Path) -> dict[str, Any]:
    doc = pymupdf.open(path)
    pages: list[dict[str, Any]] = []
    removed = 0
    table = any(TABLE_ROLE_HEADER.search(page.get_text("text")) for page in doc)
    for page in doc:
        text = page.get_text("text")
        blocks = page.get_text("blocks")
        images = len(page.get_images(full=True))
        ocr = False
        if len(text.strip()) < OCR_MIN_CHARS and images:
            text = _ocr(page)
            ocr = True
            blocks = []
        clean, n = sanitize(text, table)
        removed += n
        pages.append(
            {
                "n": page.number + 1,
                "width": page.rect.width,
                "height": page.rect.height,
                "ocr": ocr,
                "images": images,
                "columns": _columns(blocks, page.rect.width) if blocks else 1,
                "text": clean,
                "blocks": [
                    [*(round(v, 1) for v in b[:4]), sanitize(str(b[4]), table)[0]]
                    for b in blocks
                    if b[6] == 0 and str(b[4]).strip()
                ],
            }
        )
    meta = doc.metadata or {}
    return {
        "pages": pages,
        "n_pages": len(pages),
        "chars": sum(len(p["text"]) for p in pages),
        "ocr_pages": [p["n"] for p in pages if p["ocr"]],
        "max_columns": max((p["columns"] for p in pages), default=1),
        "producer": meta.get("producer", ""),
        "creator": meta.get("creator", ""),
        "personal_data_removed": removed,
    }


def text_dir() -> Path:
    return data_dir() / "activities" / "text"


def load_text(doc_id: str) -> dict[str, Any]:
    return json.loads((text_dir() / f"{doc_id}.json").read_text(encoding="utf-8"))


def extract_all(base: Path | None = None, out: Path | None = None) -> list[dict[str, Any]]:
    base = base or raw_dir()
    out = out or text_dir()
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    results = []
    for doc_id, entry in manifest.items():
        if "path" not in entry:
            continue
        data = {"id": doc_id, "section": entry["section"], "url": entry["url"]}
        data.update(extract_pdf(base / entry["path"]))
        (out / f"{doc_id}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        results.append({k: v for k, v in data.items() if k != "pages"})
    return results
