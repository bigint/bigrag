from __future__ import annotations

import httpx2

from bigrag.services.url_security.pin import PinnedOutbound


class _IPPinnedTransport(httpx2.AsyncHTTPTransport):
    def __init__(self, pinned: PinnedOutbound) -> None:
        super().__init__(
            limits=httpx2.Limits(max_connections=100, max_keepalive_connections=20),
        )
        self._hostname = pinned.hostname.lower()
        self._pinned_ip = pinned.pinned_ip

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        request_host = (request.url.host or "").lower()
        if request_host != self._hostname and request_host != self._pinned_ip.lower():
            raise httpx2.ConnectError(
                f"refused to connect to {request_host}: pinned to {self._hostname}"
            )
        new_headers = httpx2.Headers(request.headers)
        if "host" not in new_headers:
            host_value = self._hostname
            if request.url.port:
                host_value = f"{self._hostname}:{request.url.port}"
            new_headers["Host"] = host_value
        new_request = httpx2.Request(
            method=request.method,
            url=request.url.copy_with(host=self._pinned_ip),
            headers=new_headers,
            stream=request.stream,
            extensions={
                **request.extensions,
                "sni_hostname": self._hostname,
            },
        )
        return await super().handle_async_request(new_request)


def pinned_openai_client(pinned: PinnedOutbound, *, timeout: float) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        transport=_IPPinnedTransport(pinned),
        timeout=timeout,
        follow_redirects=False,
    )
