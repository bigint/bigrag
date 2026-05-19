from __future__ import annotations

import argparse
import os
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

    os.environ["BIGRAG_WORKER_SEED_PERIODIC"] = "1"
    if args.queues:
        os.environ["BIGRAG_WORKER_PERIODIC_QUEUES"] = ",".join(args.queues)
    else:
        os.environ.pop("BIGRAG_WORKER_PERIODIC_QUEUES", None)

    dramatiq_args = [
        "--processes",
        str(args.processes),
        "--threads",
        str(args.threads),
        "bigrag.services.jobs.actors:broker",
    ]
    if args.queues:
        dramatiq_args.extend(["--queues", *args.queues])
    dramatiq_namespace = dramatiq.cli.make_argument_parser().parse_args(dramatiq_args)
    return int(dramatiq.cli.main(dramatiq_namespace) or 0)


if __name__ == "__main__":
    sys.exit(cli())
