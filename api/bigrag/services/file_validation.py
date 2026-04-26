from __future__ import annotations

import io
import zipfile

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

MAX_DECOMPRESSED_BYTES = 500 * 1024 * 1024


class InvalidFileContentError(Exception):
    pass


def validate_magic_bytes(content: bytes, extension: str) -> None:

    prefixes = _MAGIC_BYTES.get(extension.lower())
    if not prefixes:
        return
    head = content[: max(len(p) for p in prefixes)]
    if not any(head.startswith(p) for p in prefixes):
        raise InvalidFileContentError(
            f"File content does not match declared extension {extension!r}."
        )


def validate_zip_bomb(content: bytes, extension: str) -> None:

    if extension.lower() not in _ZIP_EXTS:
        return
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise InvalidFileContentError(f"Not a valid {extension} archive.") from exc
    total = sum(info.file_size for info in zf.infolist())
    if total > MAX_DECOMPRESSED_BYTES:
        raise InvalidFileContentError(
            f"Archive too large when decompressed "
            f"({total:,} bytes > {MAX_DECOMPRESSED_BYTES:,} limit)."
        )


def validate_upload(content: bytes, extension: str) -> None:

    validate_magic_bytes(content, extension)
    validate_zip_bomb(content, extension)
