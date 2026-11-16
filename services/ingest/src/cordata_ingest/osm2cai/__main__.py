"""`python -m cordata_ingest.osm2cai sync [--regions C,B] [--sda 3,4] [--max-fetch N]`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from ..config import data_dir
from ..http import PoliteClient
from .sync import Osm2caiStore, sync


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sincronizzazione incrementale OSM2CAI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("sync", help="scarica i sentieri nuovi o modificati")
    run.add_argument("--regions", default="C,B", help="codici regione CAI (C=TAA, B=Veneto)")
    run.add_argument("--sda", default="3,4", help="stati di accatastamento da sincronizzare")
    run.add_argument("--max-fetch", type=int, default=None, help="massimo di dettagli per run")
    run.add_argument("--out", type=Path, default=data_dir() / "osm2cai")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    store = Osm2caiStore(args.out)
    with PoliteClient() as client:
        report = sync(
            client,
            store,
            regions=args.regions.split(","),
            sdas=[int(x) for x in args.sda.split(",")],
            max_fetch=args.max_fetch,
        )
    print(json.dumps(asdict(report), ensure_ascii=False, indent=1))
    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
