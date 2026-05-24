from __future__ import annotations

import time

from bigrag.services.ingestion_job import IngestionJob


def emit_conversion_started(job: IngestionJob, emit) -> None:
    emit(
        job.document_id,
        "converting",
        "processing",
        "Parsing document",
        0.15,
        collection_name=job.collection_name,
    )


def emit_converted(job: IngestionJob, emit, started_at: float) -> float:
    elapsed = time.monotonic() - started_at
    emit(
        job.document_id,
        "converted",
        "processing",
        f"Parsed in {elapsed:.1f}s",
        0.35,
        collection_name=job.collection_name,
        elapsed=round(elapsed, 2),
    )
    return elapsed


def emit_text_extracted(job: IngestionJob, emit, text: str) -> None:
    emit(
        job.document_id,
        "text_extracted",
        "processing",
        f"Extracted {len(text):,} characters",
        0.40,
        collection_name=job.collection_name,
        chars=len(text),
    )
