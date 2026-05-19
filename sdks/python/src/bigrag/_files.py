from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

FileInput = str | Path | bytes | BinaryIO | tuple[str, bytes] | tuple[str, BinaryIO]


def normalize_file_input(file: FileInput) -> tuple[str, bytes | BinaryIO]:
    if isinstance(file, tuple):
        return file

    if isinstance(file, (str, Path)):
        path = Path(file)
        return (path.name, path.read_bytes())

    if isinstance(file, bytes):
        return ("document", file)

    name = getattr(file, "name", None)
    if isinstance(name, str):
        name = os.path.basename(name)
    else:
        name = "document"
    return (name, file)
