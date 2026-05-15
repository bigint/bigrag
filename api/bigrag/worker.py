from __future__ import annotations

import argparse
import sys

import dramatiq.cli

from bigrag import config as config_module
from bigrag.config import Settings
from bigrag.logging import configure_logging


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bigrag-worker")
    parser.add_argument("--config")
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--queues", nargs="*")
    args = parser.parse_args(argv)

    if args.config:
        config_module.settings = Settings.from_toml(args.config)

    configure_logging(
        log_level=config_module.settings.log_level,
        log_format=config_module.settings.log_format,
    )

    from bigrag.services.jobs.actors import seed_periodic_jobs

    seed_periodic_jobs(set(args.queues) if args.queues else None)

    dramatiq_args = [
        "--processes",
        str(args.processes),
        "--threads",
        str(args.threads),
    ]
    if args.queues:
        dramatiq_args.extend(["--queues", *args.queues])
    dramatiq_args.append("bigrag.services.jobs.actors:broker")
    return int(dramatiq.cli.main(dramatiq_args) or 0)


if __name__ == "__main__":
    sys.exit(cli())
