from __future__ import annotations

import rag_computer._types as compat_types
from rag_computer.types.common import HealthResponse


def test_compat_types_reexports_public_types() -> None:
    assert "HealthResponse" in compat_types.__all__
    assert compat_types.HealthResponse is HealthResponse
