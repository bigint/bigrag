"""Python version compatibility for typing imports."""

from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from typing import Any, NotRequired, TypedDict
else:
    from typing import Any

    from typing_extensions import NotRequired, TypedDict

__all__ = ["Any", "NotRequired", "TypedDict"]
