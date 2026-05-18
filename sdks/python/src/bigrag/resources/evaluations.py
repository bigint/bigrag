from __future__ import annotations

from typing import TYPE_CHECKING

from bigrag.types.evaluations import EvalBody, EvalResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class EvaluationsResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def run(self, body: EvalBody) -> EvalResponse:
        return await self._client._request("POST", "/v1/evaluation", json=body)
