"""Shared fixtures for bigRAG SDK tests."""

from __future__ import annotations

import httpx
import pytest


@pytest.fixture()
def base_url() -> str:
    return "http://localhost:6100"
