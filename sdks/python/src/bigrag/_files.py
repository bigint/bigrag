
from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

FileInput = str | Path | bytes | BinaryIO | tuple[str, bytes] | tuple[str, BinaryIO]
"""Accepted file input types for document upload.

- ``str`` / :class:`~pathlib.Path` -- a filesystem path; the file is read
  and the basename is used as the filename.
- ``bytes`` -- raw bytes; the filename defaults to ``"document"``.
- :class:`~typing.BinaryIO` -- a file-like object; the ``.name`` attribute
  is used as the filename when available, otherwise ``"document"``.
- ``tuple[str, bytes]`` or ``tuple[str, BinaryIO]`` -- an explicit
  ``(filename, data)`` pair.
"""


def normalize_file_input(file: FileInput) -> tuple[str, bytes | BinaryIO]:
    # tuple[str, bytes | BinaryIO]
    if isinstance(file, tuple):
        return file

    # str or Path -- read from filesystem
    if isinstance(file, (str, Path)):
        path = Path(file)
        return (path.name, path.read_bytes())

    # bytes
    if isinstance(file, bytes):
        return ("document", file)

    name = getattr(file, "name", None)
    if isinstance(name, str):
        name = os.path.basename(name)
    else:
        name = "document"
    return (name, file)
