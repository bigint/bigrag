from __future__ import annotations

from bigrag.services.ingestion import chunk_document


def test_paragraph_chunks_preserve_offsets_and_join_small_paragraphs() -> None:
    text = "  Alpha beta\n\nGamma delta\n\nEpsilon"

    chunks = chunk_document(text, 20, 0)

    assert [(chunk.text, chunk.char_start, chunk.char_end) for chunk in chunks] == [
        ("Alpha beta", 2, 12),
        ("Gamma delta\n\nEpsilon", 14, 34),
    ]
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.text


def test_paragraph_chunks_split_oversized_sentence_by_size() -> None:
    chunks = chunk_document("abcdefghij", 4, 0)

    assert [(chunk.text, chunk.char_start, chunk.char_end) for chunk in chunks] == [
        ("abcd", 0, 4),
        ("efgh", 4, 8),
        ("ij", 8, 10),
    ]


def test_recursive_chunks_fall_back_through_separators() -> None:
    chunks = chunk_document("alpha beta gamma delta epsilon", 10, 0, strategy="recursive")

    assert [(chunk.text, chunk.char_start, chunk.char_end) for chunk in chunks] == [
        ("alpha", 0, 5),
        ("beta", 6, 10),
        ("gamma", 11, 16),
        ("delta", 17, 22),
        ("epsilon", 23, 30),
    ]


def test_chunk_overlap_carries_previous_tail_without_resizing_first_chunk() -> None:
    chunks = chunk_document("abcdefghij", 4, 2)

    assert [(chunk.text, chunk.char_start, chunk.char_end) for chunk in chunks] == [
        ("abcd", 0, 4),
        ("cd efgh", 1, 8),
        ("gh ij", 5, 10),
    ]


def test_empty_and_invalid_inputs_return_no_chunks() -> None:
    assert chunk_document("   \n\n  ", 10, 2) == []
    assert chunk_document("hello", 0, 0, strategy="recursive") == []
