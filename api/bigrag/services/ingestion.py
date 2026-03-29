"""Text chunking utilities for document ingestion."""

from __future__ import annotations


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into chunks on paragraph/sentence boundaries with overlap."""
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
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

    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-chunk_overlap:]
            # Align to word boundary to avoid cutting mid-word
            space_idx = tail.find(" ")
            if space_idx != -1:
                tail = tail[space_idx + 1:]
            overlapped.append(f"{tail} {chunks[i]}")
        chunks = overlapped

    return chunks
