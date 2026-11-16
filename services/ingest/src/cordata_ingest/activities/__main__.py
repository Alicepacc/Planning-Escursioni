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

from ..http import PoliteClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cordata_ingest.activities")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("discover", help="elenca i PDF delle sezioni pilota (solo metadati)")
    sub.add_parser("archive", help="scarica i PDF candidati nell'archivio privato")
    sub.add_parser("extract", help="estrae il testo dei PDF archiviati")
    sub.add_parser("gazetteer", help="carica in PostGIS i luoghi OSM con nome (geocodifica)")
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
            payload = discover(client)
        print(payload["per_section"])
    elif args.cmd == "archive":
        from .archive import archive, load_candidates

        with PoliteClient(timeout=60) as client:
            manifest = archive(client, load_candidates())
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
