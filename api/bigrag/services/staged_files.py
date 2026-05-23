from __future__ import annotations

import uuid

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import Document, DocumentElement, UploadSessionItem
from bigrag.logging import get_logger
from bigrag.services.document_elements import element_asset_prefix_for_file_path
from bigrag.services.storage import get_storage

logger = get_logger("bigrag.staged_files")

TERMINAL_DOCUMENT_STATUSES = ("ready", "failed")


class StagedFileCleanupError(RuntimeError):
    pass


async def delete_staged_file_path(file_path: str | None, *, raise_on_failure: bool = False) -> bool:
    if not file_path:
        return True
    storage = get_storage()
    source_deleted = True
    assets_deleted = True
    errors: list[str] = []
    try:
        await storage.delete(file_path)
    except Exception as exc:
        source_deleted = False
        errors.append(f"source: {exc!r}")
        logger.warning("staged file delete failed", path=file_path, error=repr(exc))
    try:
        await storage.delete_prefix(element_asset_prefix_for_file_path(file_path))
    except Exception as exc:
        assets_deleted = False
        errors.append(f"assets: {exc!r}")
        logger.warning("staged asset delete failed", path=file_path, error=repr(exc))
    if source_deleted and assets_deleted:
        logger.info("staged file deleted", path=file_path)
    elif raise_on_failure:
        raise StagedFileCleanupError(
            f"Staged file cleanup failed for {file_path}: {'; '.join(errors)}"
        )
    return source_deleted and assets_deleted


async def delete_staged_collection_prefix(collection_name: str) -> int:
    prefix = f"{collection_name}/"
    try:
        deleted = await get_storage().delete_prefix(prefix)
    except Exception as exc:
        logger.warning(
            "staged collection delete failed",
            collection=collection_name,
            error=repr(exc),
        )
        raise StagedFileCleanupError(
            f"Staged collection cleanup failed for {collection_name}"
        ) from exc
    logger.info("staged collection files deleted", collection=collection_name, count=deleted)
    return deleted


async def delete_staged_asset_path(asset_path: str | None) -> bool:
    if not asset_path:
        return True
    try:
        await get_storage().delete(asset_path)
    except Exception as exc:
        logger.warning("staged asset delete failed", path=asset_path, error=repr(exc))
        return False
    logger.info("staged asset deleted", path=asset_path)
    return True


async def clear_document_staged_file(document_id: uuid.UUID, file_path: str | None) -> bool:
    deleted = await delete_staged_file_path(file_path)
    async with session_factory()() as session:
        await session.execute(
            sa.update(DocumentElement)
            .where(DocumentElement.document_id == document_id)
            .values(asset_path=None)
        )
        await session.execute(
            sa.update(UploadSessionItem)
            .where(UploadSessionItem.document_id == document_id)
            .values(storage_key=None)
        )
        if deleted and file_path:
            await session.execute(
                sa.update(Document)
                .where(Document.id == document_id)
                .where(Document.file_path == file_path)
                .values(file_path="")
            )
        await session.commit()
    return deleted


async def cleanup_terminal_staged_files(limit: int = 500) -> int:
    cleared = 0
    async with session_factory()() as session:
        rows = (
            await session.execute(
                sa.select(Document.id, Document.file_path)
                .where(Document.file_path != "")
                .where(Document.status.in_(TERMINAL_DOCUMENT_STATUSES))
                .order_by(Document.updated_at.asc())
                .limit(limit)
            )
        ).all()
        for document_id, file_path in rows:
            if await delete_staged_file_path(file_path):
                await session.execute(
                    sa.update(Document)
                    .where(Document.id == document_id)
                    .where(Document.file_path == file_path)
                    .values(file_path="")
                )
                await session.execute(
                    sa.update(UploadSessionItem)
                    .where(UploadSessionItem.document_id == document_id)
                    .values(storage_key=None)
                )
                cleared += 1
            await session.execute(
                sa.update(DocumentElement)
                .where(DocumentElement.document_id == document_id)
                .values(asset_path=None)
            )
        asset_rows = (
            await session.execute(
                sa.select(DocumentElement.id, DocumentElement.asset_path)
                .where(DocumentElement.asset_path.is_not(None))
                .order_by(DocumentElement.id.asc())
                .limit(limit)
            )
        ).all()
        for element_id, asset_path in asset_rows:
            if await delete_staged_asset_path(asset_path):
                await session.execute(
                    sa.update(DocumentElement)
                    .where(DocumentElement.id == element_id)
                    .values(asset_path=None)
                )
                cleared += 1
        await session.commit()
    if cleared:
        logger.info("terminal staged files cleaned", count=cleared)
    return cleared
