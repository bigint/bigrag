from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import signal
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from uuid import uuid4

from bigrag import APIError, BigRAG

PAYLOAD_BYTES = 1 * 1024
PAYLOAD_BODY_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789 "
UPLOAD_STATUS_CODE = 201


@dataclass(frozen=True)
class Config:
    rps: float
    base_url: str
    api_key: str
    collection: str
    metadata: dict[str, Any]
    max_in_flight: int
    report_interval: float


@dataclass
class Stats:
    started_at: float
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    in_flight: int = 0
    status_counts: Counter[int] = field(default_factory=Counter)
    error_counts: Counter[str] = field(default_factory=Counter)
    latencies: list[float] = field(default_factory=list)

    def record_response(self, status_code: int, latency: float) -> None:
        self.status_counts[status_code] += 1
        self.latencies.append(latency)
        if 200 <= status_code < 300:
            self.succeeded += 1
        else:
            self.failed += 1

    def record_error(self, name: str, latency: float) -> None:
        self.failed += 1
        self.error_counts[name] += 1
        self.latencies.append(latency)


def write_line(message: str, *, stream=sys.stdout) -> None:
    stream.write(f"{message}\n")
    stream.flush()


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("rps must be a positive number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("rps must be a positive number")
    return parsed


def env_int(name: str, default: int, *, min_value: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < min_value:
        raise ValueError(f"{name} must be at least {min_value}")
    return parsed


def env_float(name: str, default: float, *, min_value: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        parsed = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(parsed) or parsed < min_value:
        raise ValueError(f"{name} must be at least {min_value:g}")
    return parsed


def metadata_from_env() -> dict[str, Any]:
    raw = os.environ.get("BIGRAG_METADATA_JSON") or '{"source":"tests-load-streaming"}'
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("BIGRAG_METADATA_JSON must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("BIGRAG_METADATA_JSON must be a JSON object")
    return parsed


def read_config(rps: float) -> Config:
    api_key = os.environ.get("BIGRAG_API_KEY") or ""
    if not api_key:
        raise ValueError("BIGRAG_API_KEY is required")
    return Config(
        rps=rps,
        base_url=(os.environ.get("BIGRAG_URL") or "http://localhost:4000").rstrip("/"),
        api_key=api_key,
        collection=os.environ.get("BIGRAG_COLLECTION") or "docs",
        metadata=metadata_from_env(),
        max_in_flight=env_int(
            "BIGRAG_STREAMING_MAX_IN_FLIGHT",
            max(1, math.ceil(rps * 2)),
            min_value=1,
        ),
        report_interval=env_float(
            "BIGRAG_STREAMING_REPORT_INTERVAL", 5.0, min_value=0.5
        ),
    )


def build_payload(sequence: int) -> bytes:
    now = time.time_ns()
    payload = {
        "id": uuid4().hex,
        "sequence": sequence,
        "title": f"Streaming load document {sequence}",
        "created_at_ns": now,
        "target_size_bytes": PAYLOAD_BYTES,
        "tags": ["load", "streaming", uuid4().hex[:12]],
        "measurements": [
            {"name": "alpha", "value": sequence % 997},
            {"name": "beta", "value": now % 1000003},
        ],
        "body": "",
    }
    base = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload["body"] = "".join(
        random.choices(PAYLOAD_BODY_ALPHABET, k=max(0, PAYLOAD_BYTES - len(base)))
    )
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def percentile(values: list[float], percentage: float) -> str:
    if not values:
        return "-"
    ordered = sorted(values)
    index = max(
        0, min(len(ordered) - 1, math.ceil((percentage / 100) * len(ordered)) - 1)
    )
    return f"{ordered[index] * 1000:.1f}ms"


def count_text(counter: Counter) -> str:
    if not counter:
        return "-"
    return ",".join(f"{key}:{counter[key]}" for key in sorted(counter))


def report(stats: Stats, *, final: bool) -> None:
    elapsed = max(perf_counter() - stats.started_at, 0.001)
    label = "final" if final else "report"
    attempted_rps = stats.attempted / elapsed
    success_rps = stats.succeeded / elapsed
    write_line(
        " ".join(
            [
                label,
                f"elapsed={elapsed:.1f}s",
                f"attempted={stats.attempted}",
                f"succeeded={stats.succeeded}",
                f"failed={stats.failed}",
                f"in_flight={stats.in_flight}",
                f"attempted_rps={attempted_rps:.2f}",
                f"success_rps={success_rps:.2f}",
                f"latency_p50={percentile(stats.latencies, 50)}",
                f"latency_p95={percentile(stats.latencies, 95)}",
                f"statuses={count_text(stats.status_counts)}",
                f"errors={count_text(stats.error_counts)}",
            ]
        )
    )


async def upload_one(
    client: BigRAG,
    config: Config,
    stats: Stats,
    semaphore: asyncio.Semaphore,
    sequence: int,
) -> None:
    stats.in_flight += 1
    started_at = perf_counter()
    try:
        filename = f"streaming-{int(time.time() * 1000)}-{sequence}-{uuid4().hex}.json"
        await client.documents.upload(
            config.collection,
            (filename, build_payload(sequence)),
            metadata=config.metadata,
        )
        stats.record_response(UPLOAD_STATUS_CODE, perf_counter() - started_at)
    except APIError as exc:
        stats.record_response(exc.status, perf_counter() - started_at)
    except Exception as exc:
        stats.record_error(type(exc).__name__, perf_counter() - started_at)
    finally:
        stats.in_flight -= 1
        semaphore.release()


async def report_loop(stats: Stats, stop: asyncio.Event, interval: float) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            report(stats, final=False)


async def run(config: Config) -> int:
    stats = Stats(started_at=perf_counter())
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        if not stop.is_set():
            write_line("stopping after in-flight uploads finish...", stream=sys.stderr)
            stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except (NotImplementedError, RuntimeError):
            pass

    write_line(
        " ".join(
            [
                "starting",
                f"url={config.base_url}",
                f"collection={config.collection}",
                f"rps={config.rps:g}",
                f"max_in_flight={config.max_in_flight}",
                f"payload_bytes={PAYLOAD_BYTES}",
            ]
        )
    )

    semaphore = asyncio.Semaphore(config.max_in_flight)
    tasks: set[asyncio.Task[None]] = set()
    reporter = asyncio.create_task(report_loop(stats, stop, config.report_interval))
    interval = 1 / config.rps
    next_at = loop.time()
    sequence = 0

    async with BigRAG(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=60.0,
        max_retries=0,
    ) as client:
        while not stop.is_set():
            delay = next_at - loop.time()
            if delay > 0:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                except TimeoutError:
                    pass
                if stop.is_set():
                    break

            await semaphore.acquire()
            if stop.is_set():
                semaphore.release()
                break

            sequence += 1
            stats.attempted += 1
            task = asyncio.create_task(
                upload_one(client, config, stats, semaphore, sequence)
            )
            tasks.add(task)
            task.add_done_callback(tasks.discard)

            next_at += interval
            if next_at < loop.time() - interval:
                next_at = loop.time()

        if tasks:
            await asyncio.gather(*tasks)

    stop.set()
    reporter.cancel()
    try:
        await reporter
    except asyncio.CancelledError:
        pass
    report(stats, final=True)
    return 0 if stats.failed == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="streaming.py",
        description="Upload unique JSON documents to a bigRAG collection at a target RPS.",
    )
    parser.add_argument("rps", type=positive_float, help="Target uploads per second")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        config = read_config(args.rps)
    except ValueError as exc:
        parser.error(str(exc))
    return asyncio.run(run(config))


if __name__ == "__main__":
    raise SystemExit(main())
