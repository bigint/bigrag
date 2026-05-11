"""Evaluation runner resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rag_computer.types.evaluations import EvalBody, EvalResponse

if TYPE_CHECKING:
    from rag_computer._core import RagComputerCore


class EvaluationsResource:
    """Resource namespace for retrieval evaluation runs."""

    def __init__(self, client: RagComputerCore) -> None:
        self._client = client

    async def run(self, body: EvalBody) -> EvalResponse:
        """Run a golden-set retrieval evaluation."""
        return await self._client._request("POST", "/v1/evaluation", json=body)
