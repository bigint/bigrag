from __future__ import annotations

import io

from bigrag._files import normalize_file_input


def test_normalize_file_input_reads_paths(tmp_path) -> None:
    path = tmp_path / "note.txt"
    path.write_bytes(b"hello")

    assert normalize_file_input(path) == ("note.txt", b"hello")
    assert normalize_file_input(str(path)) == ("note.txt", b"hello")


def test_normalize_file_input_accepts_bytes_and_tuples() -> None:
    stream = io.BytesIO(b"hello")

    assert normalize_file_input(b"hello") == ("document", b"hello")
    assert normalize_file_input(("named.txt", b"hello")) == ("named.txt", b"hello")
    assert normalize_file_input(("stream.txt", stream)) == ("stream.txt", stream)


def test_normalize_file_input_uses_file_object_name() -> None:
    stream = io.BytesIO(b"hello")
    stream.name = "/tmp/report.pdf"

    assert normalize_file_input(stream) == ("report.pdf", stream)


def test_normalize_file_input_defaults_file_object_name() -> None:
    stream = io.BytesIO(b"hello")

    assert normalize_file_input(stream) == ("document", stream)
