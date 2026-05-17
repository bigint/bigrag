from __future__ import annotations

import asyncio
import io
import zipfile
import zlib
from pathlib import Path

_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".docx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".pptx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".xlsx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".bmp": (b"BM",),
    ".tiff": (b"II*\x00", b"MM\x00*"),
}

_ZIP_EXTS = frozenset({".docx", ".pptx", ".xlsx", ".epub"})
_OOXML_EXTS = frozenset({".docx", ".pptx", ".xlsx"})

MAX_DECOMPRESSED_BYTES = 500 * 1024 * 1024
_MAGIC_HEAD_BYTES = 16


class InvalidFileContentError(Exception):
    pass


def _read_head(source: bytes | Path, n: int) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source[:n])
    with Path(source).open("rb") as fh:
        return fh.read(n)


def validate_magic_bytes(content: bytes | Path, extension: str) -> None:

    prefixes = _MAGIC_BYTES.get(extension.lower())
    if not prefixes:
        return
    head = _read_head(content, max(len(p) for p in prefixes))
    if not any(head.startswith(p) for p in prefixes):
        raise InvalidFileContentError(
            f"File content does not match declared extension {extension!r}."
        )


def _validate_zip_bomb_sync(source: bytes | Path, extension: str) -> None:
    if isinstance(source, (bytes, bytearray)) and len(source) > MAX_DECOMPRESSED_BYTES:
        raise InvalidFileContentError(
            f"Archive too large ({len(source):,} bytes > {MAX_DECOMPRESSED_BYTES:,} limit)."
        )
    try:
        if isinstance(source, (bytes, bytearray)):
            zf = zipfile.ZipFile(io.BytesIO(source))
        else:
            zf = zipfile.ZipFile(Path(source))
    except zipfile.BadZipFile as exc:
        raise InvalidFileContentError(f"Not a valid {extension} archive.") from exc
    try:
        if extension.lower() in _OOXML_EXTS and "[Content_Types].xml" not in zf.namelist():
            raise InvalidFileContentError(
                f"{extension} archive missing required [Content_Types].xml."
            )
        total = 0
        for info in zf.infolist():
            if info.is_dir():
                continue
            with zf.open(info) as member:
                while chunk := member.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_DECOMPRESSED_BYTES:
                        raise InvalidFileContentError(
                            f"Archive too large when decompressed "
                            f"({total:,} bytes > {MAX_DECOMPRESSED_BYTES:,} limit)."
                        )
    except (zipfile.BadZipFile, RuntimeError, EOFError, OSError, zlib.error) as exc:
        raise InvalidFileContentError(
            f"Invalid compressed content in {extension} archive."
        ) from exc
    finally:
        zf.close()


async def validate_zip_bomb(content: bytes | Path, extension: str) -> None:

    if extension.lower() not in _ZIP_EXTS:
        return
    await asyncio.to_thread(_validate_zip_bomb_sync, content, extension)


async def validate_upload(content: bytes | Path, extension: str) -> None:

    validate_magic_bytes(content, extension)
    await validate_zip_bomb(content, extension)
