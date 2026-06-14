"""Příkazová řádka pro plašič kun."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional

from . import __version__
from .config import load_config
from .runner import Runner


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="marten_deterrent",
        description="Akustický plašič kun pro Raspberry Pi "
                    "(procedurální, slyšitelný, proti habituaci).",
    )
    p.add_argument("--config", metavar="PATH", default=None,
                   help="cesta ke konfiguračnímu INI souboru")
    p.add_argument("--once", "--test", dest="once", action="store_true",
                   help="přehraj pár prvků a skonči (rychlý test)")
    p.add_argument("--list-devices", dest="list_devices", action="store_true",
                   help="vypiš dostupná audio zařízení a skonči")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="podrobnější logování (DEBUG)")
    p.add_argument("--version", action="version",
                   version=f"%(prog)s {__version__}")
    return p


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def _list_devices() -> int:
    try:
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - prostředí bez PortAudio
        print(f"Nelze načíst sounddevice/PortAudio: {exc}", file=sys.stderr)
        return 1
    print(sd.query_devices())
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    log = logging.getLogger("marten")

    if args.list_devices:
        return _list_devices()

    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        log.error("Chyba konfigurace: %s", exc)
        return 2

    runner = Runner(cfg)
    try:
        if args.once:
            runner.run_once()
        else:
            runner.run()
    except KeyboardInterrupt:  # pragma: no cover
        log.info("Přerušeno uživatelem.")
    except Exception as exc:  # pragma: no cover
        log.error("Neočekávaná chyba: %s", exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
