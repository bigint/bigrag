from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    char_start: int
    char_end: int


def _stripped_chunk(segment: str, start: int) -> Chunk:
    stripped = segment.strip()
    leading = len(segment) - len(segment.lstrip())
    return Chunk(
        text=stripped,
        char_start=start + leading,
        char_end=start + leading + len(stripped),
    )


def _flush_chunk(current: str, start: int) -> Chunk | None:
    if current.strip():
        return _stripped_chunk(current, start)
    return None


def _split_oversized_sentence(
    sentence: str, sent_start: int, chunk_size: int
) -> tuple[list[Chunk], str, int]:
    chunks: list[Chunk] = []
    carry_text = ""
    carry_start = 0
    for pos in range(0, len(sentence), chunk_size):
        part = sentence[pos : pos + chunk_size]
        part_start = sent_start + pos
        if pos + chunk_size < len(sentence):
            chunks.append(_stripped_chunk(part, part_start))
        else:
            carry_text = part
            carry_start = part_start
    return chunks, carry_text, carry_start


def _split_oversized_paragraph(
    para: str, para_start: int, chunk_size: int
) -> tuple[list[Chunk], str, int]:
    chunks: list[Chunk] = []
    carry_text = ""
    carry_start = 0
    sentences = para.replace(". ", ".\n").split("\n")
    sub_cursor = para_start
    for sentence in sentences:
        slice_start = sub_cursor - para_start
        rel_idx = para.find(sentence, slice_start)
        sent_start = sub_cursor if rel_idx < 0 else para_start + rel_idx
        sub_cursor = sent_start + len(sentence)
        if len(carry_text) + len(sentence) + 1 <= chunk_size:
            if carry_text:
                carry_text = f"{carry_text} {sentence}"
            else:
                carry_text = sentence
                carry_start = sent_start
        else:
            flushed = _flush_chunk(carry_text, carry_start)
            if flushed is not None:
                chunks.append(flushed)
            carry_text = ""
            if len(sentence) > chunk_size:
                sub_chunks, carry_text, carry_start = _split_oversized_sentence(
                    sentence, sent_start, chunk_size
                )
                chunks.extend(sub_chunks)
            else:
                carry_text = sentence
                carry_start = sent_start
    return chunks, carry_text, carry_start


def _paragraph_chunks(text: str, chunk_size: int) -> list[Chunk]:
    if not text.strip():
        return []

    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []

    cursor = 0
    current_text = ""
    current_start = 0

    for raw_para in paragraphs:
        para = raw_para.strip()
        if not para:
            continue
        idx = text.find(raw_para, cursor)
        if idx < 0:
            idx = cursor
        para_start = idx + (len(raw_para) - len(raw_para.lstrip()))
        cursor = idx + len(raw_para)

        if len(current_text) + len(para) + 2 <= chunk_size:
            if current_text:
                current_text = f"{current_text}\n\n{para}"
            else:
                current_text = para
                current_start = para_start
        else:
            flushed = _flush_chunk(current_text, current_start)
            if flushed is not None:
                chunks.append(flushed)
            current_text = ""
            if len(para) > chunk_size:
                sub_chunks, current_text, current_start = _split_oversized_paragraph(
                    para, para_start, chunk_size
                )
                chunks.extend(sub_chunks)
            else:
                current_text = para
                current_start = para_start

    final = _flush_chunk(current_text, current_start)
    if final is not None:
        chunks.append(final)
    return chunks


def _recursive_chunks(text: str, chunk_size: int) -> list[Chunk]:

    if not text.strip() or chunk_size <= 0:
        return []

    separators = ["\n\n", "\n", ". ", " ", ""]

    def split(s: str, start_offset: int, seps: list[str]) -> list[Chunk]:
        if len(s) <= chunk_size or not seps:
            stripped = s.strip()
            if not stripped:
                return []
            leading = len(s) - len(s.lstrip())
            return [
                Chunk(
                    text=stripped,
                    char_start=start_offset + leading,
                    char_end=start_offset + leading + len(stripped),
                )
            ]

        sep, *rest = seps
        if not sep:
            out: list[Chunk] = []
            for i in range(0, len(s), chunk_size):
                part = s[i : i + chunk_size]
                stripped = part.strip()
                if stripped:
                    leading = len(part) - len(part.lstrip())
                    out.append(
                        Chunk(
                            text=stripped,
                            char_start=start_offset + i + leading,
                            char_end=start_offset + i + leading + len(stripped),
                        )
                    )
            return out

        out: list[Chunk] = []
        current = ""
        current_start = start_offset
        cursor = start_offset
        parts = s.split(sep)
        for i, part in enumerate(parts):
            piece = part + (sep if i < len(parts) - 1 else "")
            if len(current) + len(piece) <= chunk_size:
                if not current:
                    current_start = cursor
                current += piece
            else:
                if current:
                    out.extend(split(current, current_start, rest))
                current = piece
                current_start = cursor
            cursor += len(piece)
        if current:
            out.extend(split(current, current_start, rest))
        return out

    return split(text, 0, separators)


def _apply_overlap(chunks: list[Chunk], overlap: int) -> list[Chunk]:

    if overlap <= 0 or len(chunks) <= 1:
        return chunks
    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        tail = prev.text[-overlap:]
        original_tail_len = len(tail)
        space_idx = tail.find(" ")
        if space_idx != -1:
            tail = tail[space_idx + 1 :]
        tail_len = len(tail)
        merged_text = f"{tail} {chunks[i].text}" if tail else chunks[i].text
        start = max(0, chunks[i].char_start - original_tail_len - (1 if tail_len else 0))
        result.append(
            Chunk(
                text=merged_text,
                char_start=start,
                char_end=chunks[i].char_end,
            )
        )
    return result


def chunk_document(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    strategy: str = "paragraph",
) -> list[Chunk]:

    if strategy == "recursive":
        chunks = _recursive_chunks(text, chunk_size)
    else:
        chunks = _paragraph_chunks(text, chunk_size)
    return _apply_overlap(chunks, chunk_overlap)
