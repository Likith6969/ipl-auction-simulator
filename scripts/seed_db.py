#!/usr/bin/env python3
"""CLI entry point for database initialization and CSV seeding."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize SQLite schema and import teams/players from CSV.",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Create tables only; do not import CSV data.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-import CSV data even when the database is already seeded.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()
    _configure_logging(args.verbose)

    try:
        from app.database import init_db

        init_db(seed=not args.no_seed, force_seed=args.force)
    except Exception:
        logging.exception("Database initialization failed")
        return 1

    logging.info("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
