"""Riga di comando della pipeline attività (SPEC §7).

python -m cordata_ingest.activities discover   # metadati dei PDF delle sezioni pilota
python -m cordata_ingest.activities archive    # scarica i candidati del pilota
python -m cordata_ingest.activities extract    # testo (OCR se serve), dati personali rimossi
python -m cordata_ingest.activities gazetteer  # luoghi OSM con nome per la geocodifica
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ..http import PoliteClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cordata_ingest.activities")
    sub = parser.add_subparsers(dest="cmd", required=True)
    dis = sub.add_parser("discover", help="elenca i PDF delle sezioni pilota (solo metadati)")
    dis.add_argument(
        "--sezioni", help="solo queste sezioni (slug separati da virgola), aggiunte all'indice"
    )
    arc = sub.add_parser("archive", help="scarica i PDF candidati nell'archivio privato")
    arc.add_argument("--candidati", type=Path, help="file YAML dei candidati (default: pilota)")
    sub.add_parser("extract", help="estrae il testo dei PDF archiviati")
    sub.add_parser("gazetteer", help="carica in PostGIS i luoghi OSM con nome (geocodifica)")
    sub.add_parser("sat-siti", help="cerca i siti delle sezioni SAT (solo la home di ciascuno)")
    sub.add_parser("cai-veneto-siti", help="cerca i siti delle sezioni CAI del Veneto (solo home)")
    rec = sub.add_parser("reconstruct", help="ricostruisce le tracce delle attività del pilota")
    rec.add_argument("ids", nargs="*", help="solo queste attività (default: tutte)")
    rec.add_argument("--solo-parser", action="store_true", help="campi del parser, senza revisione")
    rep = sub.add_parser("report", help="genera reports/pilot-<data>/pilot.html")
    rep.add_argument("--data", default="2026-11-16", help="data del pilota (AAAA-MM-GG)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.cmd == "discover":
        from .discover import discover

        with PoliteClient(timeout=60) as client:
            only = [x.strip() for x in args.sezioni.split(",")] if args.sezioni else None
            payload = discover(client, only=only)
        print(payload["per_section"])
    elif args.cmd == "archive":
        from .archive import archive, load_candidates

        with PoliteClient(timeout=60) as client:
            manifest = archive(client, load_candidates(args.candidati))
        errors = {k: v["error"] for k, v in manifest.items() if "error" in v}
        print(f"{len(manifest)} documenti, {len(errors)} errori", errors or "")
    elif args.cmd == "extract":
        from .extract import extract_all

        results = extract_all()
        ocr = [r["id"] for r in results if r["ocr_pages"]]
        print(f"{len(results)} documenti estratti; OCR su: {ocr}")
    elif args.cmd == "gazetteer":
        from ..config import data_dir
        from ..db import connect
        from .gazetteer import build_extract, load

        seq = build_extract(data_dir() / "osm" / "pilot.osm.pbf")
        with connect() as conn:
            print(f"{load(conn, seq)} luoghi caricati")
    elif args.cmd == "sat-siti":
        from .sat_sites import find_sites

        with PoliteClient(timeout=20, max_retries=0) as client:
            payload = find_sites(client)
        for slug, r in payload["sezioni"].items():
            line = f"{slug:28} {r.get('status')} {r.get('host')} wp={r.get('wordpress')}"
            print(f"{line} pdf={r.get('pdf_pubblici')} {r.get('title', '')[:50]}")
        print(f"domini provati: {payload['domini_provati']}")
    elif args.cmd == "cai-veneto-siti":
        from .veneto_sites import find_sites as find_veneto

        with PoliteClient(timeout=20, max_retries=0) as client:
            payload = find_veneto(client)
        for slug, results in payload["sezioni"].items():
            for r in results:
                print(f"{slug:32} wp={r.get('wordpress')} pdf={r.get('pdf_pubblici')} {r['url']}")
        print(f"indirizzi provati: {payload['indirizzi_provati']}")
    elif args.cmd == "reconstruct":
        from .pilot import run_reconstruction

        source = "parser" if args.solo_parser else "rivista"
        for row in run_reconstruction(args.ids or None, source):
            print(f"{row['status']:12} {row['id'][:48]:48} {row['seconds']:5}s", row["reasons"])
    elif args.cmd == "report":
        from ..config import repo_root
        from .evaluate import evaluate_all
        from .report import build

        evaluate_all()  # aggiorna i campi del parser in data/activities/parsed
        out = build(repo_root() / "reports" / f"pilot-{args.data}", args.data)
        print(f"rapporto: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
