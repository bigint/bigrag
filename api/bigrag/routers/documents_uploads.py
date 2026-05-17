from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from bigrag.db.models import Document
from bigrag.routers import uuid_or_404
from bigrag.routers._documents import (
    SUPPORTED_EXTENSIONS,
    UploadBudget,
    stream_upload_to_temp,
)
from bigrag.services.file_validation import InvalidFileContentError, validate_upload

__all__ = [
    "CONTENT_TYPE_BY_EXTENSION",
    "document_file_response",
    "metadata_or_400",
    "upload_extension_or_400",
    "uuid_or_404",
    "validated_upload_to_temp",
]

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


def upload_extension_or_400(filename: str | None, *, batch: bool = False) -> str:
    file_ext = Path(filename or "").suffix.lower()
    if file_ext in SUPPORTED_EXTENSIONS:
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


async def validated_upload_to_temp(
    file: UploadFile,
    file_ext: str,
    *,
    max_size: int,
    budget: UploadBudget | None = None,
    batch: bool = False,
) -> tuple[Path, str, int]:
    try:
        tmp_path, content_hash, size = await stream_upload_to_temp(
            file, max_size=max_size, budget=budget
        )
    except HTTPException as exc:
        if not batch:
            raise
        raise HTTPException(
            status_code=exc.status_code,
            detail=f"File '{file.filename}': {exc.detail}",
        ) from exc
    if size == 0:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        detail = f"File '{file.filename}' is empty" if batch else "File is empty"
        raise HTTPException(status_code=400, detail=detail)
    try:
        await validate_upload(tmp_path, file_ext)
    except InvalidFileContentError as exc:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        detail = f"File '{file.filename}': {exc}" if batch else str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc
    return tmp_path, content_hash, size


def metadata_or_400(collection: dict, metadata: str, prepare, parse) -> dict:
    try:
        return prepare(collection, parse(metadata))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"metadata: {exc}") from exc


async def document_file_response(doc: Document, storage) -> Response:
    if not await storage.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found in storage")

    ext = doc.file_type.lower()
    content_type = CONTENT_TYPE_BY_EXTENSION.get(ext, "application/octet-stream")
    safe_ascii = re.sub(r"[\x00-\x1f\x7f\"\\]", "_", doc.filename)
    encoded = quote(doc.filename, safe="")
    return StreamingResponse(
        storage.get_stream(doc.file_path),
        media_type=content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{encoded}"
            )
        },
    )
