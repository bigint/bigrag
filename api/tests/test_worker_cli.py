from __future__ import annotations

import sys
from types import ModuleType

from bigrag import worker


def install_fake_actors(monkeypatch):
    calls = []
    module = ModuleType("bigrag.services.jobs.actors")
    module.seed_periodic_jobs = calls.append
    monkeypatch.setitem(sys.modules, "bigrag.services.jobs.actors", module)
    return calls


def test_worker_cli_passes_parsed_dramatiq_namespace(monkeypatch):
    seeded = install_fake_actors(monkeypatch)
    received = {}

    def main(args):
        received["args"] = args
        return 0

    monkeypatch.setattr(worker.dramatiq.cli, "main", main)

    assert worker.cli(["--processes", "2", "--threads", "3"]) == 0

    args = received["args"]
    assert not isinstance(args, list)
    assert args.broker == "bigrag.services.jobs.actors:broker"
    assert args.processes == 2
    assert args.threads == 3
    assert args.path == "."
    assert args.queues is None
    assert seeded == [None]


def test_worker_cli_keeps_broker_out_of_queue_names(monkeypatch):
    seeded = install_fake_actors(monkeypatch)
    received = {}

    def main(args):
        received["args"] = args
        return 0

    monkeypatch.setattr(worker.dramatiq.cli, "main", main)

    assert worker.cli(["--queues", "ingestion", "connectors"]) == 0

    args = received["args"]
    assert args.broker == "bigrag.services.jobs.actors:broker"
    assert args.queues == ["ingestion", "connectors"]
    assert seeded == [{"ingestion", "connectors"}]
