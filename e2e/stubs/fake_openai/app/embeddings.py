from __future__ import annotations

import hashlib

import numpy as np


def deterministic_vector(text: str, dim: int) -> list[float]:
    """Return a deterministic L2-normalized embedding for ``text``.

    The same input always returns the same vector — this lets tests reason
    about ranking, dedup, and cache hits without spending real OpenAI
    credits.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big", signed=False)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim).astype(np.float64)
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        vec[0] = 1.0
        norm = 1.0
    return (vec / norm).tolist()


def count_tokens(text: str) -> int:
    """Cheap whitespace token counter — good enough for fake usage stats."""
    return max(1, len(text.split()))
