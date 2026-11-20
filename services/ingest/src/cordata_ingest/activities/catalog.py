"""Catalogo a lotti (ADR 0015): dalle locandine archiviate alle escursioni pubblicabili.

Per ogni documento non ancora rivisto a mano:

1. campi della locandina con il parser a regole (senza revisione);
2. tipo di attività: si tengono solo le escursioni (niente bici, corsi, serate, programmi
   annuali in questo primo passo);
3. punti del percorso dal parser o, se ne trova meno di tre, dal testo con il gazetteer;
4. ricostruzione della traccia e confronto con la locandina;
5. area del catalogo (Trentino-Alto Adige, Dolomiti e Prealpi venete) decisa dalla traccia;
6. punteggio di affidabilità: da 80 in su l'escursione entra nell'app.

Tutto resta nell'archivio privato (`data/activities/catalogo/`): per ogni documento un record
con l'esito e, se ricostruita, la traccia. La build legge solo le schede pubblicabili.
"""

from __future__ import annotations

import html
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from ..config import data_dir, repo_root
from ..geo.area import in_area
from .itinerary import extract_points
from .parse import calendar_entry, parse, programme_dates
from .reliability import THRESHOLD, score

# scale di difficoltà della mountain bike (cicloescursionismo CAI) e dell'alpinismo
BIKE_GRADE = re.compile(r"^(TC|MC|BC|OC|EC)\b", re.I)
ALPINE_GRADE = re.compile(r"^(F|PD|AD|D|TD|ED)[+-]?$", re.I)
BIKE_WORDS = re.compile(
    r"(?i)\b(ciclo-?escursion\w*|mtb|mountain bike|e-?bike|bicicletta|in bici)\b"
)
NOT_HIKE_WORDS = re.compile(
    r"(?i)\b(corso di|serata|conferenza|proiezione|assemblea|cena sociale|tesseramento|"
    r"convocazione|bilancio|verbale|modulo di iscrizione|informativa privacy|regolamento)\b"
)
DATE_LIKE = re.compile(
    r"(?i)\b(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|"
    r"ottobre|novembre|dicembre)\b"
)
HIKE_GRADES = {"T", "E", "EE", "EEA", "EAI"}

# titoli che sono in realtà righe del regolamento o dell'intestazione
BAD_TITLE = re.compile(
    r"(?i)(iscrizion|tesserat|quota di partecipazione|assicurativ|modulo|versamento|"
    r"nome rimosso|foglio informativo|club alpino italiano|capo ?gita|responsabil|partecipant|"
    r"regolamento|informativa|^\W*$|:\s*$|dislivell|difficolt|durata|lunghezza|ritrovo|"
    r"tempo di percorrenza|quota massima|\bore\s+\d|\.(?:docx?|pdf|odt)\b|scheda tecnica|"
    r"scarica|\bkb\b|\[)"
)
SMALL_WORDS = {
    "de",
    "di",
    "da",
    "del",
    "della",
    "dei",
    "delle",
    "e",
    "al",
    "alla",
    "ai",
    "in",
    "per",
    "con",
    "sul",
    "sulla",
    "a",
    "il",
    "la",
    "lo",
    "le",
    "dal",
    "dalla",
    "d",
    "mt",
    "m",
}
KEEP_UPPER = {"CAI", "SAT", "EE", "EEA", "EAI", "AVS", "II", "III", "IV"}


def _smart_case(title: str) -> str:
    """Titoli tutti maiuscoli («RIFUGIO ANTERMOIA») in maiuscole solo dove servono."""
    letters = [c for c in title if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.8:
        return title
    out = []
    for i, w in enumerate(re.split(r"(\s+|[–—\-/(),:“”\"'’])", title)):
        if w.upper() in KEEP_UPPER or not w.strip() or not w[0].isalpha():
            out.append(w)
        elif i and w.lower() in SMALL_WORDS:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return "".join(out)


def _site_title(raw: str | None) -> str | None:
    """Il nome del documento sul sito della sezione, senza date, «locandina» e simili."""
    if not raw:
        return None
    t = html.unescape(raw)
    t = re.sub(r"[_]+", " ", t)
    t = re.sub(r"\b\d{1,4}[-./ ]\d{1,2}[-./ ]\d{2,4}\b|\b\d{8}\b|\b\d{2}_?\d{8}\b|\(\d+\)", " ", t)
    t = re.sub(
        r"(?i)\b(locandina|locandine|manifesti?|programma|def(?:initivo)?|copia|pdf|cai|sat|"
        r"sezione|gita|escursione|uscita|volantino|scheda)\b",
        " ",
        t,
    )
    t = re.sub(r"\s*[–—-]\s*$|^\s*[–—-]\s*", "", re.sub(r"\s+", " ", t)).strip(" .-–")
    return t if len(re.findall(r"[A-Za-zÀ-ÿ]{3,}", t)) >= 1 and len(t) >= 4 else None


PROSE_WORDS = re.compile(
    r"(?i)\b(?:è|sono|facendo|faremo|saliremo|scenderemo|arriveremo|partiremo|raggiungeremo|"
    r"percorreremo|conducono|questo|questa|nostra|nostro|vi|ci|che)\b"
)
GENERIC_TITLE = re.compile(
    r"(?i)^(?:gruppo\s+(?:escursionism\w*|senior\w*|giovani|alpinismo\w*|famiglie)|"
    r"commissione|sezione|alpinismo giovanile|escursionismo|programma|attivit[àa]|calendario|"
    r"libretto|notiziario|gita sociale|uscita sociale)\b"
)


def _not_a_title(t: str) -> bool:
    """Una frase della descrizione («Riamo fino a Paneveggio; facendo così…») o il nome di un
    gruppo («Gruppo Escursionismo») presi per titolo."""
    # le quote tra parentesi non contano come parole: «Lago di Erdemolo (2036 m) e …»
    words = re.sub(r"\([^)]*\)", " ", t).split()
    return (
        ";" in t
        or bool(re.search(r"[a-zà-ÿ]-\s?[a-zà-ÿ]{3,}", t))  # parola spezzata a capo: «con-ducono»
        or len(words) > 12
        or (len(words) >= 5 and bool(PROSE_WORDS.search(t)))
        or (len(words) >= 4 and t.rstrip().endswith("."))
        or (len(words) <= 3 and bool(GENERIC_TITLE.match(t)))
    )


def _fold(word: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", word.lower()) if not unicodedata.combining(c)
    )


SITE_ABBREV = (
    (r"\bM\.\s?te\b\.?|\bM\.(?=\s?[A-ZÀ-Ý])", "Monte"),
    (r"\bRif\.", "Rifugio"),
    (r"\bF\.\s?lla\b\.?", "Forcella"),
    (r"\bP\.\s?so\b\.?", "Passo"),
    (r"\bM\.\s?ga\b\.?", "Malga"),
    (r"\bBiv\.", "Bivacco"),
)
# parole di tipo: non sono nomi propri, restano anche se il testo non le ripete
TYPE_WORDS = {
    "monte",
    "monti",
    "cima",
    "cime",
    "rifugio",
    "rifugi",
    "lago",
    "laghi",
    "passo",
    "forcella",
    "malga",
    "malghe",
    "bivacco",
    "ferrata",
    "sentiero",
    "anello",
    "giro",
    "traversata",
    "val",
    "valle",
    "croda",
    "col",
    "punta",
    "piz",
    "cresta",
    "sella",
    "ciaspolata",
    "notturna",
    "alta",
    "via",
    "altopiano",
    "gruppo",
    "baita",
    "casera",
    "forte",
}
MONTHS = {
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
}
SMALL = {
    "di",
    "de",
    "da",
    "del",
    "dei",
    "della",
    "delle",
    "degli",
    "e",
    "al",
    "alla",
    "ai",
    "a",
    "ad",
    "in",
    "con",
    "per",
    "sul",
    "sulla",
    "nel",
    "nella",
    "dal",
    "dalla",
    "il",
    "lo",
    "la",
    "le",
}


def _site_words_in_text(title: str, text: str | None) -> str | None:
    """Il nome del documento sul sito, con le sole parole che compaiono anche nel testo pulito
    della locandina (oltre alle parole di tipo: monte, rifugio, anello…). I nomi dei file a
    volte portano i cognomi degli accompagnatori («Rizzotti-Paier Rifugio Papa»): il testo li ha
    già tolti, quindi qui cadono anche dal titolo."""
    if text is None:
        return None
    for pattern, full in SITE_ABBREV:
        title = re.sub(pattern, full + " ", title)
    known = {_fold(w) for w in re.findall(r"[A-Za-zÀ-ÿ'’]+", text)}
    kept = []
    for w in re.split(r"[\s\-–—]+", title):
        f = _fold(w.strip("'’.,"))
        if not f or re.search(r"\d", w) or f in MONTHS:
            continue
        if f in SMALL or f in TYPE_WORDS or f in known:
            kept.append(w.strip(".,"))
    while kept and _fold(kept[0]) in {"escursionismo", "attivita", "gita"}:
        kept.pop(0)
    # «Monte ZERVOI» → «Monte Zervoi» (le sigle corte restano)
    kept = [w.capitalize() if w.isupper() and len(w) > 3 else w for w in kept]
    while kept and _fold(kept[-1]) in SMALL:
        kept.pop()
    # serve almeno un nome proprio, non solo «Monte» o «Ferrata»
    if not any(_fold(w) not in TYPE_WORDS | SMALL for w in kept):
        return None
    out = " ".join(kept)
    return out if re.search(r"[A-Za-zÀ-ÿ]{4}", out) else None


def choose_title(
    parsed: str | None,
    site: str | None,
    track: dict[str, Any] | None,
    text: str | None = None,
) -> str:
    """Titolo della scheda: quello della locandina se è un titolo vero, altrimenti il nome del
    documento sul sito, altrimenti la meta più alta e la partenza della traccia."""
    t = (parsed or "").strip().strip('“”"')
    t = re.sub(r"(?i)^escursione\s*:\s*", "", t)
    # etichette di sezione rimaste attaccate al titolo
    t = re.sub(r"(?i)\s+(breve\s+)?descrizione(\s+del\s+percorso)?\s*$", "", t)
    t = t.strip("“”\"'’ ").replace("“", "«").replace("”", "»")
    if t.count("«") != t.count("»"):
        t = t.replace("«", "").replace("»", "")

    def cap(x: str) -> str:
        return x[:1].upper() + x[1:]

    # un titolo vero ha almeno una parola di quattro lettere
    if (
        t
        and len(t) <= 90
        and not BAD_TITLE.search(t)
        and not _not_a_title(t)
        and re.search(r"[A-Za-zÀ-ÿ]{4}", t)
    ):
        return cap(_smart_case(t))
    st = _site_title(site)
    st = _site_words_in_text(st, text) if st else None
    if st and st.islower():
        st = _smart_case(st.upper())  # «col margherita» → «Col Margherita»
    if (
        st
        and not BAD_TITLE.search(st)
        and not _not_a_title(st)
        and re.search(r"[A-Za-zÀ-ÿ]{4}", st)
    ):
        return cap(_smart_case(st))
    pts = [p for p in (track or {}).get("points") or [] if p.get("lon") is not None]
    if pts:
        top = max(pts, key=lambda p: p.get("quota_osm") or p.get("quota_dem") or 0)
        start = pts[0]
        a, b = top.get("trovato") or top["nome"], start.get("trovato") or start["nome"]
        return a if a == b else f"{a} da {b}"
    return _smart_case(t[:90]) if t else "Escursione"


def catalog_dir() -> Path:
    return data_dir() / "activities" / "catalogo"


def section_names() -> dict[str, str]:
    path = repo_root() / "config" / "sources" / "cai_sections.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = {}
    for s in data["sections"]:
        name = re.sub(r"^CAI Sezione di ", "CAI ", s["name"])
        out[s["slug"]] = re.sub(r"^SAT Sezione di ", "SAT ", name)
    return out


def activity_kind(values: dict[str, Any], text: str) -> tuple[str, str | None]:
    """«escursione» o il motivo per cui il documento resta fuori dal catalogo."""
    grade = (values.get("difficolta") or "").strip()
    if BIKE_GRADE.match(grade) or (BIKE_WORDS.search(text) and grade not in HIKE_GRADES):
        return "bici", "cicloescursionismo"
    if ALPINE_GRADE.match(grade):
        return "alpinismo", f"scala alpinistica {grade}"
    dates = {m.group(0).lower() for m in DATE_LIKE.finditer(text)}
    if len(dates) >= 6:
        return "programma", f"{len(dates)} date: programma o libretto"
    numbers = [values.get(k) for k in ("distanza_km", "salita_m", "durata", "quota_max_m")]
    if NOT_HIKE_WORDS.search(text) and not any(numbers) and grade not in HIKE_GRADES:
        return "altro", "corso, serata o documento amministrativo"
    base = grade.split("-")[0].split("/")[0].upper()
    if grade and base not in HIKE_GRADES and not grade.upper().startswith("EAI"):
        return "altro", f"difficoltà {grade} fuori dalla scala escursionistica"
    if not any(numbers) and not grade:
        return "altro", "nessun dato di percorso"
    return "escursione", None


def activity_from(values: dict[str, Any], text: str, home: str | None) -> dict[str, Any]:
    """Campi per la ricostruzione, come quelli rivisti a mano (`config/activities/reviewed`)."""
    points = [
        {"nome": x["nome"], "quota_m": x.get("quota_m")} for x in values.get("punti_chiave") or []
    ]
    if values.get("partenza_nome"):
        points.insert(0, {"nome": values["partenza_nome"], "quota_m": values["partenza_quota_m"]})
    if home and len(home) >= 4:
        h = home.lower()
        while len(points) > 2 and h in points[0]["nome"].lower():
            points.pop(0)  # «Puos d'Alpago» per il CAI Alpago: il ritrovo, non la partenza
    loop = values.get("tipo_percorso") == "anello"
    from_text = False
    if len({x["nome"] for x in points}) < 3:
        extra = extract_points(text, home=home, title=values.get("titolo"))
        if len(extra["punti"]) >= 2:
            points, from_text = extra["punti"], True
            loop = loop or (extra["anello"] and values.get("tipo_percorso") is None)
    if loop and points:
        points.append(dict(points[0]))
    elif values.get("arrivo_nome") and values.get("tipo_percorso") == "traversata":
        points.append({"nome": values["arrivo_nome"]})
    return {
        "titolo": values.get("titolo"),
        "data": values.get("data"),
        "difficolta": values.get("difficolta"),
        "tipo_percorso": values.get("tipo_percorso") or ("anello" if loop else None),
        "durata": values.get("durata"),
        "distanza_km": values.get("distanza_km"),
        "salita_m": values.get("salita_m"),
        "discesa_m": values.get("discesa_m"),
        "quota_max_m": values.get("quota_max_m"),
        "partenza": {"nome": points[0]["nome"] if points else None, "quota_m": None},
        "ora_ritrovo": values.get("ora_ritrovo"),
        "mezzi": values.get("mezzi"),
        "quota_eur": values.get("quota_eur"),
        "sentieri": values.get("sentieri") or [],
        "punti_chiave": points,
        "punti_dal_testo": from_text,
    }


def process(
    conn: Any, dem: Any, doc_id: str, entry: dict[str, Any], names: dict[str, str]
) -> dict[str, Any]:
    text_doc = json.loads(
        (data_dir() / "activities" / "text" / f"{doc_id}.json").read_text(encoding="utf-8")
    )
    pages = [(p["n"], p["text"]) for p in text_doc["pages"]]
    text = "\n".join(t for _, t in pages)
    hint = "/".join(text_doc["url"].rsplit("/", 3)[-3:])
    fields = parse(pages, hint=hint)
    values = {k: v["value"] for k, v in fields.items()}
    section = names.get(entry["section"], entry["section"])
    record: dict[str, Any] = {
        "id": doc_id,
        "sezione": section,
        "url": entry["url"],
        "pubblicato": entry.get("published"),
        "campi": fields,
    }
    kind, why = activity_kind(values, text)
    record["tipo"] = kind
    if kind == "programma":
        # programmi e libretti: ogni voce di calendario come una locandina a sé
        record["voci"] = process_programme(conn, dem, doc_id, entry, section, pages, text)
        n_ok = sum(1 for v in record["voci"].values() if v == "pubblicabile")
        record["esito"] = f"programma: {len(record['voci'])} voci, {n_ok} pubblicabili"
        return record
    if kind != "escursione":
        record["esito"] = f"escluso: {why}"
        return record
    return _reconstruct_and_score(conn, dem, doc_id, entry, record, fields, values, text)


def _year_of(text: str, url: str) -> int:
    years = re.findall(r"\b(20[12]\d)\b", text)
    if years:
        return int(max(set(years), key=years.count))
    m = re.search(r"/(20[12]\d)/", url)
    return int(m.group(1)) if m else 2026


def process_programme(
    conn: Any,
    dem: Any,
    doc_id: str,
    entry: dict[str, Any],
    section: str,
    pages: list[tuple[int, str]],
    text: str,
) -> dict[str, str]:
    """Voci di un programma: per ogni data la voce ritagliata, i campi, la ricostruzione e il
    punteggio, ciascuna con il suo record (`<documento>--<data>`). Restituisce gli esiti."""
    out: dict[str, str] = {}
    for iso in programme_dates(pages, _year_of(text, entry["url"]))[:120]:
        part = calendar_entry(pages, iso)
        if not part:
            continue
        fields = parse(part, entry_date=iso)
        values = {k: v["value"] for k, v in fields.items()}
        part_text = "\n".join(t for _, t in part)
        rid = f"{doc_id}--{iso}"
        record: dict[str, Any] = {
            "id": rid,
            "documento": doc_id,
            "sezione": section,
            "url": entry["url"],
            "pubblicato": entry.get("published"),
            "campi": fields,
        }
        kind, why = activity_kind(values, part_text)
        record["tipo"] = "voce di programma" if kind in ("escursione", "programma") else kind
        if kind not in ("escursione", "programma"):
            record["esito"] = f"escluso: {why}"
        else:
            # la voce non ha il nome del sito: il titolo viene dalla voce o dalla traccia
            sub = {**entry, "titolo_sito": None}
            record = _reconstruct_and_score(conn, dem, rid, sub, record, fields, values, part_text)
        target = catalog_dir() / "record" / f"{rid}.json"
        target.write_text(json.dumps(record, ensure_ascii=False, indent=1), "utf-8")
        out[iso] = record["esito"].split(":")[0].split(" (")[0]
    return out


def _reconstruct_and_score(
    conn: Any,
    dem: Any,
    doc_id: str,
    entry: dict[str, Any],
    record: dict[str, Any],
    fields: dict[str, Any],
    values: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    from .reconstruct import reconstruct, result_dict

    section = record["sezione"]
    home = re.sub(r"^(CAI|SAT)\s+", "", section).split(" - ")[0].strip() or None
    activity = activity_from(values, text, home)
    activity["sezione"] = section
    record["attivita"] = activity
    t0 = time.perf_counter()
    track = result_dict(reconstruct(conn, dem, doc_id, activity))
    track["seconds"] = round(time.perf_counter() - t0, 1)
    record["ricostruzione"] = {k: track[k] for k in ("status", "reasons", "checks")}
    activity["titolo"] = choose_title(values.get("titolo"), entry.get("titolo_sito"), track, text)
    inside = bool(track.get("coords")) and in_area(track["coords"])
    record["area"] = inside
    s = score(track, fields)
    record["affidabilita"] = s
    if track.get("coords"):
        tracks = catalog_dir() / "tracce"
        tracks.mkdir(parents=True, exist_ok=True)
        (tracks / f"{doc_id}.json").write_text(json.dumps(track, ensure_ascii=False), "utf-8")
    if not inside and track.get("coords"):
        record["esito"] = "fuori area"
    elif s["punteggio"] >= THRESHOLD:
        record["esito"] = "pubblicabile"
    else:
        record["esito"] = f"sotto soglia ({s['punteggio']})"
    return record


def retitle() -> dict[str, int]:
    """Ricalcola i titoli dei record già elaborati (campi della locandina, nome del documento
    sul sito, traccia salvata) senza ricostruire nulla. Restituisce quanti titoli cambiano."""
    index = data_dir() / "activities" / "index.json"
    site_titles = (
        {d["url"]: d.get("title") for d in json.loads(index.read_text("utf-8"))["documents"]}
        if index.exists()
        else {}
    )
    changed = kept = 0
    for path in sorted((catalog_dir() / "record").glob("*.json")):
        record = json.loads(path.read_text("utf-8"))
        activity = record.get("attivita")
        fields = record.get("campi")
        if not activity or not isinstance(fields, dict):
            continue
        track_path = catalog_dir() / "tracce" / f"{record['id']}.json"
        track = json.loads(track_path.read_text("utf-8")) if track_path.exists() else None
        # le voci dei programmi non hanno il nome del sito (è quello del libretto)
        site = None if "--" in record["id"] else site_titles.get(record["url"])
        text_path = data_dir() / "activities" / "text" / f"{record['id'].split('--')[0]}.json"
        text = (
            "\n".join(p["text"] for p in json.loads(text_path.read_text("utf-8"))["pages"])
            if text_path.exists()
            else None
        )
        title = choose_title((fields.get("titolo") or {}).get("value"), site, track, text)
        if title != activity.get("titolo"):
            activity["titolo"] = title
            path.write_text(json.dumps(record, ensure_ascii=False, indent=1), "utf-8")
            changed += 1
        else:
            kept += 1
    return {"cambiati": changed, "uguali": kept}


def run(limit: int | None = None, only_new: bool = True) -> dict[str, int]:
    """Elabora i documenti archiviati con il testo estratto, saltando quelli già elaborati e
    quelli rivisti a mano. Restituisce il conteggio degli esiti."""
    from ..db import connect
    from ..geo.elevation import TerrariumDem
    from ..http import PoliteClient
    from .evaluate import load_reviewed
    from .pilot import blocks_dir

    out = catalog_dir() / "record"
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((data_dir() / "activities" / "raw" / "manifest.json").read_text("utf-8"))
    reviewed = set(load_reviewed()) | set(load_reviewed(blocks_dir()))
    texts = data_dir() / "activities" / "text"
    names = section_names()
    index = data_dir() / "activities" / "index.json"
    site_titles = (
        {d["url"]: d.get("title") for d in json.loads(index.read_text("utf-8"))["documents"]}
        if index.exists()
        else {}
    )
    counts: dict[str, int] = {}
    done = 0
    with PoliteClient(timeout=60) as client, connect() as conn:
        dem = TerrariumDem(data_dir() / "dem" / "mapterhorn", client, zoom=12)
        for doc_id, entry in manifest.items():
            if "path" not in entry or doc_id in reviewed:
                continue
            if not (texts / f"{doc_id}.json").exists():
                continue
            target = out / f"{doc_id}.json"
            if only_new and target.exists():
                continue
            try:
                entry = {**entry, "titolo_sito": site_titles.get(entry["url"])}
                record = process(conn, dem, doc_id, entry, names)
            except Exception as exc:  # un documento storto non ferma il lotto
                conn.rollback()
                record = {"id": doc_id, "esito": f"errore: {type(exc).__name__}: {exc}"[:300]}
            target.write_text(json.dumps(record, ensure_ascii=False, indent=1), "utf-8")
            key = record["esito"].split(":")[0].split(" (")[0]
            counts[key] = counts.get(key, 0) + 1
            done += 1
            if limit and done >= limit:
                break
    return counts
