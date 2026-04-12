"""Content-aware file validation for uploads.

Two checks:

1. **Magic-byte sniffing.** Compare the first few bytes of the uploaded
   blob against the declared extension so an ``evil.exe`` renamed to
   ``report.pdf`` can't slip past. We only enforce for formats with
   stable, well-known magic numbers — plain text, JSON, CSV, etc. are
   allowed to carry any bytes.

2. **Zip-bomb guard.** Zip-based formats (docx, pptx, xlsx, epub) can
   decompress to thousands of times their on-disk size. We open the
   archive, sum ``ZipInfo.file_size`` across entries, and reject if the
   total exceeds :data:`MAX_DECOMPRESSED_BYTES`.

Kept stdlib-only — no libmagic dependency — because covering the
handful of extensions we support doesn't warrant the extra install
friction for self-hosters.
"""

from __future__ import annotations

import io
import zipfile

# Prefixes per extension. A file is considered valid if ANY prefix
# matches. Formats not in this map skip the magic-byte check.
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    # DOCX / PPTX / XLSX / EPUB are ZIP containers.
    ".docx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".pptx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".xlsx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    # Images.
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".bmp": (b"BM",),
    ".tiff": (b"II*\x00", b"MM\x00*"),
}

_ZIP_EXTS = frozenset({".docx", ".pptx", ".xlsx", ".epub"})

# Refuse a zip whose total decompressed size exceeds this. 500 MB is
# well above any legitimate office document yet cheap to detect via
# the central directory.
MAX_DECOMPRESSED_BYTES = 500 * 1024 * 1024


class InvalidFileContent(Exception):
    """Raised when an upload fails content-aware validation."""


def validate_magic_bytes(content: bytes, extension: str) -> None:
    """Raise :class:`InvalidFileContent` if the declared extension has a
    known magic-number prefix and the content doesn't start with any of
    them. Extensions not in the map pass silently.
    """
    prefixes = _MAGIC_BYTES.get(extension.lower())
    if not prefixes:
        return
    head = content[: max(len(p) for p in prefixes)]
    if not any(head.startswith(p) for p in prefixes):
        raise InvalidFileContent(
            f"File content does not match declared extension {extension!r}."
        )


def validate_zip_bomb(content: bytes, extension: str) -> None:
    """Reject zip-based uploads whose decompressed size would exceed
    :data:`MAX_DECOMPRESSED_BYTES`.
    """
    if extension.lower() not in _ZIP_EXTS:
        return
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise InvalidFileContent(
            f"Not a valid {extension} archive."
        ) from exc
    total = sum(info.file_size for info in zf.infolist())
    if total > MAX_DECOMPRESSED_BYTES:
        raise InvalidFileContent(
            f"Archive too large when decompressed "
            f"({total:,} bytes > {MAX_DECOMPRESSED_BYTES:,} limit)."
        )


def validate_upload(content: bytes, extension: str) -> None:
    """Run all content-aware upload checks for ``extension`` against
    ``content``. Raises :class:`InvalidFileContent` on failure.
    """
    validate_magic_bytes(content, extension)
    validate_zip_bomb(content, extension)
