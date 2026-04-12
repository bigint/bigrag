"""Tests for content-aware upload validation (magic bytes, zip bombs)."""

from __future__ import annotations

import io
import zipfile

import pytest

from bigrag.services.file_validation import (
    MAX_DECOMPRESSED_BYTES,
    InvalidFileContent,
    validate_magic_bytes,
    validate_upload,
    validate_zip_bomb,
)


class TestMagicBytes:
    def test_valid_pdf_prefix_passes(self):
        validate_magic_bytes(b"%PDF-1.7\n...", ".pdf")

    def test_executable_renamed_as_pdf_rejected(self):
        # Windows PE / ELF / Mach-O headers don't start with %PDF-
        exe_content = b"MZ\x90\x00\x03\x00...."
        with pytest.raises(InvalidFileContent, match="does not match declared extension"):
            validate_magic_bytes(exe_content, ".pdf")

    def test_png_header_required_for_png(self):
        validate_magic_bytes(b"\x89PNG\r\n\x1a\npayload", ".png")
        with pytest.raises(InvalidFileContent):
            validate_magic_bytes(b"plain text", ".png")

    def test_jpeg_magic_allowed(self):
        validate_magic_bytes(b"\xff\xd8\xff\xe0...", ".jpeg")
        validate_magic_bytes(b"\xff\xd8\xff\xe0...", ".jpg")

    def test_docx_accepts_zip_magic(self):
        validate_magic_bytes(b"PK\x03\x04 ...", ".docx")
        with pytest.raises(InvalidFileContent):
            validate_magic_bytes(b"Not a zip", ".docx")

    def test_extensions_without_rules_pass(self):
        # Plain text, CSV, MD, JSON — no stable magic, anything goes.
        validate_magic_bytes(b"anything at all", ".txt")
        validate_magic_bytes(b"col1,col2\n1,2", ".csv")


class TestZipBomb:
    def test_small_archive_passes(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("doc.xml", "<xml>small</xml>")
        validate_zip_bomb(buf.getvalue(), ".docx")

    def test_oversized_archive_rejected(self):
        # Build a valid zip central directory that advertises a huge
        # uncompressed size, without actually paying the memory cost of
        # producing one. We do this by manually tweaking ZipInfo.file_size
        # after adding a small entry.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("big.bin", b"x")
            # Lie about decompressed size: claim it's larger than the cap.
            zf.infolist()[0].file_size = MAX_DECOMPRESSED_BYTES + 1
        with pytest.raises(InvalidFileContent, match="decompressed"):
            validate_zip_bomb(buf.getvalue(), ".docx")

    def test_non_zip_ext_ignored(self):
        validate_zip_bomb(b"not a zip at all", ".pdf")

    def test_corrupt_zip_for_zip_ext_rejected(self):
        with pytest.raises(InvalidFileContent, match="valid"):
            validate_zip_bomb(b"PK\x03\x04garbage", ".docx")


def test_validate_upload_composes_both_checks():
    # Evil file: PK\x03\x04 prefix (docx magic passes) but zipfile can't
    # open it → zip-bomb check catches it.
    with pytest.raises(InvalidFileContent):
        validate_upload(b"PK\x03\x04truncated", ".docx")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document/>")
    validate_upload(buf.getvalue(), ".docx")
