from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

from bigrag.routers import uuid_or_404
from bigrag.services.documents import (
    SUPPORTED_EXTENSIONS,
    UploadBudget,
    stream_upload_to_temp,
)
from bigrag.services.file_validation import InvalidFileContentError, validate_upload
from bigrag.services.tenant_enforcement import enforce_tenant_metadata

__all__ = [
    "metadata_or_400",
    "upload_extension_or_400",
    "uuid_or_404",
    "validated_upload_to_temp",
]


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


def metadata_or_400(collection: dict, metadata: str, prepare, parse, principal: dict) -> dict:
    try:
        prepared = prepare(collection, parse(metadata))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"metadata: {exc}") from exc
    return enforce_tenant_metadata(collection, prepared, principal, label="metadata")
