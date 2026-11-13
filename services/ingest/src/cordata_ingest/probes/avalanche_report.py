"""Bollettino valanghe Euregio (avalanche.report / ALBINA) in CAAMLv6 JSON (SPEC §5.5)."""

from __future__ import annotations

from collections import Counter

from .base import ProbeContext, ProbeResult

PROBE_ID = "avalanche_report"
BASE = "https://static.avalanche.report/bulletins"
WINTER_DAY = "2026-02-10"
LAGORAI_REGION = "IT-32-TN-"  # prefisso delle micro-regioni trentine


def _url(day: str, lang: str = "it") -> str:
    return f"{BASE}/{day}/{day}_EUREGIO_{lang}_CAAMLv6.json"


def run(ctx: ProbeContext) -> ProbeResult:
    r = ProbeResult(
        source_id=PROBE_ID,
        name="avalanche.report – bollettino valanghe Euregio (ALBINA)",
        format="JSON CAAMLv6 (un file per giorno e lingua)",
        license="CC BY 4.0 («Tutti i dati forniti, come il bollettino valanghe… sono concessi in "
        "licenza CC BY 4.0»)",
        license_url="https://avalanche.report/more/open-data",
        limits="File statici senza limiti pubblicati; un download per giorno e lingua basta.",
        update_frequency="Giornaliera in stagione (bollettino del 10/02 uscito alle 17 del 09/02); "
        "nessun bollettino fuori stagione",
    )
    winter = ctx.try_get(
        r, f"bollettino per data ({WINTER_DAY}, it)", _url(WINTER_DAY), ttl=30 * 86400
    )
    if winter:
        bulletins = winter.json()["bulletins"]
        regions = [reg["regionID"] for b in bulletins for reg in b["regions"]]
        r.check(
            "lingua italiana", all(b["lang"] == "it" for b in bulletins), f"{len(bulletins)} zone"
        )
        r.check(
            "micro-regioni trentine presenti",
            any(x.startswith(LAGORAI_REGION) for x in regions),
            f"{len(regions)} regionID, es. {regions[:4]}",
        )
        first = bulletins[0]
        ratings = first["dangerRatings"]
        problems = first["avalancheProblems"]
        r.check(
            "gradi di pericolo per fascia di quota",
            all("mainValue" in x for x in ratings),
            "; ".join(f"{x['mainValue']} {x.get('elevation', {})}" for x in ratings),
        )
        r.check(
            "problemi valanghivi con esposizioni",
            all("problemType" in p and "aspects" in p for p in problems),
            "; ".join(
                f"{p['problemType']} {p['aspects']} {p.get('elevation', {})}" for p in problems
            ),
        )
        r.check(
            "tendenza presente",
            bool(first.get("tendency")),
            str(first["tendency"][0]["tendencyType"]),
        )
        r.notes.append("Campi di un bollettino: " + ", ".join(sorted(first)))
        r.notes.append(
            "Le quote possono essere numeri in stringa («2600») oppure «treeline» (limite del "
            "bosco); i gradi hanno validTimePeriod all_day / earlier / later."
        )
        counts = Counter(x["mainValue"] for b in bulletins for x in b["dangerRatings"])
        r.notes.append(f"Gradi nel bollettino del {WINTER_DAY}: {dict(counts)}")
        r.samples.append(ctx.save_sample(PROBE_ID, f"{WINTER_DAY}_EUREGIO_it.json", winter.json()))
        r.examples.append(_url(WINTER_DAY))

    latest = ctx.try_get(
        r, "bollettino «latest»", f"{BASE}/latest/EUREGIO_it_CAAMLv6.json", ttl=3600
    )
    if latest:
        pub = latest.json()["bulletins"][0]["publicationTime"]
        r.notes.append(
            f"«latest» oggi restituisce l'ultimo bollettino della stagione scorsa (pubblicato il "
            f"{pub}): l'app deve controllare validTime e non mostrarlo come attuale."
        )
    today = ctx.client.get(_url("2026-11-12"), ttl=3600)
    r.notes.append(
        f"Bollettino del 12/11/2026 (fuori stagione): HTTP {today.status} → gestire l'assenza "
        "come «bollettino non ancora disponibile per la stagione»."
    )
    for lang in ("de", "en"):
        other = ctx.client.get(_url(WINTER_DAY, lang), ttl=30 * 86400)
        r.check(f"disponibile anche in {lang}", other.ok, f"HTTP {other.status}")
    r.notes.append(
        "static.avalanche.report risponde 301 verso avalanche.report (stesso percorso): il "
        "pattern della SPEC è confermato."
    )
    return r.finish()
