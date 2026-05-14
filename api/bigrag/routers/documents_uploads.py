from __future__ import annotations

import re
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response

from bigrag.db.models import Document
from bigrag.routers._documents import (
    SUPPORTED_EXTENSIONS,
    UploadBudget,
    read_upload_content,
)
from bigrag.services.file_validation import InvalidFileContentError, validate_upload

CONTENT_TYPE_BY_EXTENSION = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "html": "application/octet-stream",
    "htm": "application/octet-stream",
    "md": "text/markdown",
    "txt": "text/plain",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "xml": "application/xml",
    "json": "application/json",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
}


def uuid_or_404(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"{label} not found") from exc


def upload_extension_or_400(filename: str | None, *, batch: bool = False) -> str:
    file_ext = Path(filename or "").suffix.lower()
    if not file_ext or file_ext in SUPPORTED_EXTENSIONS:
        return file_ext
    if batch:
        detail = (
            f"Unsupported file type '{file_ext}' for file '{filename}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    else:
        detail = (
            f"Unsupported file type '{file_ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    raise HTTPException(status_code=400, detail=detail)


async def validated_upload_content(
    file: UploadFile,
    file_ext: str,
    *,
    max_size: int,
    budget: UploadBudget | None = None,
    batch: bool = False,
) -> bytes:
    try:
        content = await read_upload_content(file, max_size=max_size, budget=budget)
    except HTTPException as exc:
        if not batch:
            raise
        raise HTTPException(
            status_code=exc.status_code,
            detail=f"File '{file.filename}': {exc.detail}",
        ) from exc
    if len(content) == 0:
        detail = f"File '{file.filename}' is empty" if batch else "File is empty"
        raise HTTPException(status_code=400, detail=detail)
    try:
        validate_upload(content, file_ext)
    except InvalidFileContentError as exc:
        detail = f"File '{file.filename}': {exc}" if batch else str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc
    return content


def metadata_or_400(collection: dict, metadata: str, prepare, parse) -> dict:
    try:
        return prepare(collection, parse(metadata))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"metadata: {exc}") from exc


async def document_file_response(doc: Document, storage) -> Response:
    if not await storage.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found in storage")

    data = await storage.get(doc.file_path)
    ext = doc.file_type.lower()
    content_type = CONTENT_TYPE_BY_EXTENSION.get(ext, "application/octet-stream")
    safe_ascii = re.sub(r"[\x00-\x1f\x7f\"\\]", "_", doc.filename)
    encoded = quote(doc.filename, safe="")
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{encoded}"
            )
        },
    )
