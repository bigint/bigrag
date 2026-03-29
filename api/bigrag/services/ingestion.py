from __future__ import annotations

import logging
import uuid
from pathlib import Path

from bigrag.database import db
from bigrag.services.embedding import EmbeddingModel
from bigrag.services.vector_store import vector_store

logger = logging.getLogger("bigrag.ingestion")

# Batch size for embedding + insertion
EMBED_BATCH_SIZE = 64


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Simple token-approximate chunker splitting on paragraph/sentence boundaries."""
    if not text.strip():
        return []

    # Split into paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # If paragraph itself exceeds chunk_size, split by sentences
            if len(para) > chunk_size:
                sentences = para.replace(". ", ".\n").split("\n")
                current_chunk = ""
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                        current_chunk = f"{current_chunk} {sentence}" if current_chunk else sentence
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence
            else:
                current_chunk = para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Apply overlap by prepending tail of previous chunk
    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-chunk_overlap:]
            overlapped.append(f"{prev_tail} {chunks[i]}")
        chunks = overlapped

    return chunks


async def ingest_document(
    document_id: str,
    file_path: str,
    collection_name: str,
    embedding_model: EmbeddingModel,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> int:
    """Process a document: convert with Docling, chunk, embed, store in Milvus."""
    from docling.document_converter import DocumentConverter

    try:
        # Update status to processing
        await db.execute(
            "UPDATE documents SET status = 'processing', updated_at = now() WHERE id = $1",
            uuid.UUID(document_id),
        )

        logger.info(f"Ingesting document {document_id} from {file_path}")

        # Convert document with Docling
        converter = DocumentConverter()
        result = converter.convert(file_path)

        # Export to markdown for structured text
        text = result.document.export_to_markdown()
        if not text.strip():
            # Fallback to plain text
            text = result.document.export_to_text()

        if not text.strip():
            raise ValueError("Document produced no extractable text")

        # Chunk the text
        chunks = _chunk_text(text, chunk_size, chunk_overlap)
        if not chunks:
            raise ValueError("Document produced no chunks after processing")

        logger.info(f"Document {document_id}: {len(chunks)} chunks from {len(text)} chars")

        # Embed and insert in batches
        total_inserted = 0
        for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch_end = min(batch_start + EMBED_BATCH_SIZE, len(chunks))
            batch_texts = chunks[batch_start:batch_end]

            # Generate embeddings
            embeddings = await embedding_model.embed(batch_texts)

            # Prepare IDs
            ids = [f"{document_id}_{i}" for i in range(batch_start, batch_end)]
            doc_ids = [document_id] * len(batch_texts)
            indices = list(range(batch_start, batch_end))

            # Insert into Milvus
            count = vector_store.insert(
                collection=collection_name,
                ids=ids,
                document_ids=doc_ids,
                chunk_indices=indices,
                texts=batch_texts,
                embeddings=embeddings,
            )
            total_inserted += count

        # Update document status
        await db.execute(
            """
            UPDATE documents SET status = 'ready', chunk_count = $1, updated_at = now()
            WHERE id = $2
            """,
            total_inserted, uuid.UUID(document_id),
        )

        # Update collection document count
        await db.execute(
            """
            UPDATE collections SET
                document_count = (SELECT COUNT(*) FROM documents WHERE collection_id = collections.id AND status = 'ready'),
                updated_at = now()
            WHERE name = $1
            """,
            collection_name,
        )

        logger.info(f"Document {document_id} ingested: {total_inserted} chunks stored")
        return total_inserted

    except Exception as e:
        logger.error(f"Failed to ingest document {document_id}: {e}")
        await db.execute(
            "UPDATE documents SET status = 'failed', error_message = $1, updated_at = now() WHERE id = $2",
            str(e), uuid.UUID(document_id),
        )
        raise
