from __future__ import annotations

from bigrag.services.vector_store.turbopuffer.client import _TurbopufferClientMixin
from bigrag.services.vector_store.turbopuffer.delete import _TurbopufferDeleteMixin
from bigrag.services.vector_store.turbopuffer.query import _TurbopufferQueryMixin
from bigrag.services.vector_store.turbopuffer.write import _TurbopufferWriteMixin


class TurbopufferVectorStore(
    _TurbopufferWriteMixin,
    _TurbopufferQueryMixin,
    _TurbopufferDeleteMixin,
    _TurbopufferClientMixin,
):
    pass


__all__ = ["TurbopufferVectorStore"]
