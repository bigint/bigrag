from __future__ import annotations

import asyncio

from rag_computer.services import queue_conversion
from rag_computer.services.ingestion_job import IngestionJob


class FakeDocument:
    def __init__(self, markdown: str, text: str) -> None:
        self.markdown = markdown
        self.text = text

    def export_to_markdown(self) -> str:
        return self.markdown

    def export_to_text(self) -> str:
        return self.text


class FakeResult:
    def __init__(self, markdown: str, text: str) -> None:
        self.document = FakeDocument(markdown, text)


class FakeStorage:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.paths = []

    async def get(self, path: str) -> bytes:
        self.paths.append(path)
        return self.data


class FakeConverter:
    def __init__(self) -> None:
        self.page_ranges = []

    def convert(self, path, page_range):
        self.page_ranges.append(page_range)
        return FakeResult(f"pages {page_range[0]}-{page_range[1]}", "")


def _job(file_path: str = "docs/a.txt") -> IngestionJob:
    return IngestionJob(
        document_id="11111111-1111-1111-1111-111111111111",
        file_path=file_path,
        collection_name="docs",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        chunk_size=400,
        chunk_overlap=40,
        job_id="job",
    )


def test_docling_result_text_prefers_markdown_and_falls_back_to_text() -> None:
    assert queue_conversion.docling_result_text(FakeResult("# Title", "Title")) == "# Title"
    assert queue_conversion.docling_result_text(FakeResult("   ", "Fallback")) == "Fallback"


def test_convert_document_reads_plain_text_and_emits_extraction(monkeypatch) -> None:
    async def run() -> None:
        storage = FakeStorage(b"hello world")
        events = []

        async def get_values(keys):
            return {"conversion_timeout": 30, "conversion_pdf_ocr_enabled": False}

        monkeypatch.setattr("rag_computer.services.storage.get_storage", lambda: storage)
        monkeypatch.setattr("rag_computer.services.runtime_settings.get_values", get_values)

        text = await queue_conversion.convert_document(
            _job(),
            "prefix",
            emit=lambda *args, **kwargs: events.append((args, kwargs)),
            ensure_job_current=lambda job: None,
        )

        assert text == "hello world"
        assert storage.paths == ["docs/a.txt"]
        assert [event[0][1] for event in events] == ["converting", "text_extracted"]

    asyncio.run(run())


def test_convert_document_rejects_empty_plain_text(monkeypatch) -> None:
    async def run() -> None:
        async def get_values(keys):
            return {"conversion_timeout": 30, "conversion_pdf_ocr_enabled": False}

        monkeypatch.setattr("rag_computer.services.storage.get_storage", lambda: FakeStorage(b"  "))
        monkeypatch.setattr("rag_computer.services.runtime_settings.get_values", get_values)

        try:
            await queue_conversion.convert_document(
                _job(),
                "prefix",
                emit=lambda *args, **kwargs: None,
                ensure_job_current=lambda job: None,
            )
        except ValueError as exc:
            assert str(exc) == "Document produced no extractable text"
        else:
            raise AssertionError("expected empty text failure")

    asyncio.run(run())


def test_ocr_scanned_pdf_chunks_pages_and_emits_progress(monkeypatch) -> None:
    async def run() -> None:
        converter = FakeConverter()
        events = []
        checks = []

        async def get_values(keys):
            return {"conversion_timeout": 30}

        async def ensure_job_current(job):
            checks.append(job.document_id)

        monkeypatch.setattr("rag_computer.services.runtime_settings.get_values", get_values)
        monkeypatch.setattr(queue_conversion, "get_pdf_page_count", lambda path: 12)
        monkeypatch.setattr(
            queue_conversion,
            "_get_docling_converter",
            lambda pdf_ocr_enabled: converter,
        )

        text = await queue_conversion.ocr_scanned_pdf(
            file_data=b"%PDF",
            suffix=".pdf",
            job=_job("docs/a.pdf"),
            prefix="prefix",
            start_time=0.0,
            emit=lambda *args, **kwargs: events.append((args, kwargs)),
            ensure_job_current=ensure_job_current,
        )

        assert text == "pages 1-10\n\npages 11-12"
        assert converter.page_ranges == [(1, 10), (11, 12)]
        assert len(checks) == 2
        assert [event[0][1] for event in events] == [
            "ocr",
            "ocr",
            "ocr",
            "ocr",
            "ocr",
            "converted",
            "text_extracted",
        ]

    asyncio.run(run())


def test_convert_document_maps_isolated_timeout_to_value_error(monkeypatch) -> None:
    async def run() -> None:
        async def get_values(keys):
            return {"conversion_timeout": 30, "conversion_pdf_ocr_enabled": True}

        monkeypatch.setattr(
            "rag_computer.services.storage.get_storage",
            lambda: FakeStorage(b"%PDF"),
        )
        monkeypatch.setattr("rag_computer.services.runtime_settings.get_values", get_values)

        def fail(*args, **kwargs):
            raise TimeoutError("conversion timed out")

        monkeypatch.setattr(queue_conversion, "convert_document_isolated", fail)

        try:
            await queue_conversion.convert_document(
                _job("docs/a.pdf"),
                "prefix",
                emit=lambda *args, **kwargs: None,
                ensure_job_current=lambda job: None,
            )
        except ValueError as exc:
            assert str(exc) == "conversion timed out"
        else:
            raise AssertionError("expected timeout failure")

    asyncio.run(run())
