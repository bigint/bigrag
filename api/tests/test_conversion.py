from __future__ import annotations

import sys
from types import SimpleNamespace

from rag_computer.services import conversion


class FakeTextPage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.closed = False

    def get_text_range(self) -> str:
        return self.text

    def close(self) -> None:
        self.closed = True


class FakePage:
    def __init__(self, text: str) -> None:
        self.text_page = FakeTextPage(text)
        self.closed = False

    def get_textpage(self) -> FakeTextPage:
        return self.text_page

    def close(self) -> None:
        self.closed = True


class FakePdfDocument:
    instances: list[FakePdfDocument] = []

    def __init__(self, _path: str) -> None:
        self.pages = [FakePage("First page"), FakePage(""), FakePage("Third page")]
        self.closed = False
        self.instances.append(self)

    def __len__(self) -> int:
        return len(self.pages)

    def __getitem__(self, index: int) -> FakePage:
        return self.pages[index]

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.sent = []
        self.closed = False

    def send(self, value) -> None:
        self.sent.append(value)

    def close(self) -> None:
        self.closed = True


def test_extract_pdf_text_reads_pages_and_closes_handles(monkeypatch) -> None:
    FakePdfDocument.instances.clear()
    monkeypatch.setitem(
        sys.modules,
        "pypdfium2",
        SimpleNamespace(PdfDocument=FakePdfDocument),
    )

    text = conversion.extract_pdf_text("paper.pdf")

    pdf = FakePdfDocument.instances[0]
    assert text == "First page\n\nThird page"
    assert pdf.closed is True
    assert all(page.closed for page in pdf.pages)
    assert all(page.text_page.closed for page in pdf.pages)


def test_convert_file_path_uses_pdf_text_without_docling(monkeypatch) -> None:
    monkeypatch.setattr(conversion, "extract_pdf_text", lambda _path: "embedded text")

    def fail_docling(**_kwargs):
        raise AssertionError("docling should not load")

    monkeypatch.setattr(conversion, "_get_docling_converter", fail_docling)

    assert conversion._convert_file_path("paper.pdf", ".pdf", True) == "embedded text"


def test_convert_file_path_falls_back_to_docling_for_scanned_pdf(monkeypatch) -> None:
    class FakeConverter:
        def convert(self, path: str):
            assert path == "scan.pdf"
            return SimpleNamespace(document=SimpleNamespace(export_to_markdown=lambda: "OCR text"))

    monkeypatch.setattr(conversion, "extract_pdf_text", lambda _path: "")
    monkeypatch.setattr(
        conversion,
        "_get_docling_converter",
        lambda *, pdf_ocr_enabled: FakeConverter(),
    )

    assert conversion._convert_file_path("scan.pdf", ".pdf", True) == "OCR text"


def test_convert_file_path_returns_empty_pdf_text_when_ocr_disabled(monkeypatch) -> None:
    monkeypatch.setattr(conversion, "extract_pdf_text", lambda _path: "")

    def fail_docling(**_kwargs):
        raise AssertionError("docling should not load")

    monkeypatch.setattr(conversion, "_get_docling_converter", fail_docling)

    assert conversion._convert_file_path("scan.pdf", ".pdf", False) == ""


def test_docling_result_text_uses_first_working_export() -> None:
    class FakeDocument:
        def export_to_markdown(self) -> str:
            raise RuntimeError("bad markdown")

        def export_to_text(self) -> str:
            return "plain text"

    assert conversion._docling_result_text(SimpleNamespace(document=FakeDocument())) == "plain text"
    assert conversion._docling_result_text(SimpleNamespace(document=None)) == (
        "namespace(document=None)"
    )


def test_conversion_worker_sends_success_and_errors(monkeypatch) -> None:
    ok_conn = FakeConnection()
    monkeypatch.setattr(conversion, "_convert_file_path", lambda *_args: "converted")

    conversion._conversion_worker(ok_conn, "doc.txt", ".txt", True)

    assert ok_conn.sent == [("ok", "converted")]
    assert ok_conn.closed is True

    error_conn = FakeConnection()

    def fail_convert(*_args):
        raise RuntimeError("cannot parse")

    monkeypatch.setattr(conversion, "_convert_file_path", fail_convert)

    conversion._conversion_worker(error_conn, "doc.txt", ".txt", True)

    assert error_conn.sent == [("error", "RuntimeError: cannot parse")]
    assert error_conn.closed is True
