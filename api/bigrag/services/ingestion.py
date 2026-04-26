from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    char_start: int
    char_end: int


def _paragraph_chunks(text: str, chunk_size: int) -> list[Chunk]:

    if not text.strip():
        return []

    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []

    cursor = 0
    current_text = ""
    current_start = 0

    def _flush(current: str, start: int) -> None:
        if current.strip():
            stripped = current.strip()
            leading = len(current) - len(current.lstrip())
            chunks.append(
                Chunk(
                    text=stripped,
                    char_start=start + leading,
                    char_end=start + leading + len(stripped),
                )
            )

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
            _flush(current_text, current_start)
            current_text = ""
            if len(para) > chunk_size:
                sentences = para.replace(". ", ".\n").split("\n")
                sub_cursor = para_start
                for sentence in sentences:
                    sent_start = text.find(sentence, sub_cursor)
                    if sent_start < 0:
                        sent_start = sub_cursor
                    sub_cursor = sent_start + len(sentence)
                    if len(current_text) + len(sentence) + 1 <= chunk_size:
                        if current_text:
                            current_text = f"{current_text} {sentence}"
                        else:
                            current_text = sentence
                            current_start = sent_start
                    else:
                        _flush(current_text, current_start)
                        current_text = ""
                        if len(sentence) > chunk_size:
                            for pos in range(0, len(sentence), chunk_size):
                                part = sentence[pos : pos + chunk_size]
                                part_start = sent_start + pos
                                if pos + chunk_size < len(sentence):
                                    chunks.append(
                                        Chunk(
                                            text=part.strip(),
                                            char_start=part_start,
                                            char_end=part_start + len(part),
                                        )
                                    )
                                else:
                                    current_text = part
                                    current_start = part_start
                        else:
                            current_text = sentence
                            current_start = sent_start
            else:
                current_text = para
                current_start = para_start

    _flush(current_text, current_start)
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
        space_idx = tail.find(" ")
        if space_idx != -1:
            tail = tail[space_idx + 1 :]
        tail_len = len(tail)
        merged_text = f"{tail} {chunks[i].text}" if tail else chunks[i].text
        start = max(0, chunks[i].char_start - tail_len - (1 if tail_len else 0))
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


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:

    return [c.text for c in chunk_document(text, chunk_size, chunk_overlap, strategy="paragraph")]
