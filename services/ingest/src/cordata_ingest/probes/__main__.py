"""Runner: `python -m cordata_ingest.probes [id ...] [--out DIR] [--list]`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path

from ..config import repo_root
from . import discover
from .base import STATUS_BLOCKED, ProbeResult, default_context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica delle fonti dati (SPEC §6)")
    parser.add_argument("ids", nargs="*", help="fonti da verificare (default: tutte)")
    parser.add_argument("--out", type=Path, default=repo_root() / "reports" / "phase0" / "sources")
    parser.add_argument("--list", action="store_true", help="elenca le fonti disponibili")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    probes = discover()
    if args.list:
        print("\n".join(probes))
        return 0
    unknown = [i for i in args.ids if i not in probes]
    if unknown:
        parser.error(f"fonti sconosciute: {', '.join(unknown)} (disponibili: {', '.join(probes)})")
    selected = args.ids or list(probes)

    args.out.mkdir(parents=True, exist_ok=True)
    ctx = default_context()
    failed = 0
    for probe_id in selected:
        try:
            result = probes[probe_id](ctx)
        except Exception as exc:  # una fonte rotta non deve fermare le altre
            traceback.print_exc()
            result = ProbeResult(source_id=probe_id, name=probe_id, status=STATUS_BLOCKED)
            result.check("esecuzione dello script", False, f"{type(exc).__name__}: {exc}")
        out_file = args.out / f"{probe_id}.json"
        out_file.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        passed = sum(c.ok for c in result.checks)
        print(f"{probe_id:<22} {result.status:<18} controlli {passed}/{len(result.checks)}")
        for chk in result.checks:
            if not chk.ok:
                failed += 1
                print(f"    ✗ {chk.name}: {chk.detail}")
    ctx.client.close()
    print(f"\nRichieste HTTP effettuate: {ctx.client.requests_made}; risultati in {args.out}")
    return 0  # i controlli falliti sono un esito da documentare, non un errore del runner


if __name__ == "__main__":
    sys.exit(main())
