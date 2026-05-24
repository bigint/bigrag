from __future__ import annotations

import ipaddress

import httpx

from bigrag.services.url_security.pin import PinnedOutbound

_DEFAULT_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20)


def _bracket_ipv6(ip_str: str) -> str:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return ip_str
    if isinstance(addr, ipaddress.IPv6Address) and not ip_str.startswith("["):
        return f"[{ip_str}]"
    return ip_str


class _IPPinnedTransport(httpx.AsyncHTTPTransport):
    def __init__(self, hostname: str, pinned_ip: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._hostname = hostname.lower()
        self._pinned_ip = pinned_ip

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request_host = (request.url.host or "").lower()
        if request_host != self._hostname and request_host != self._pinned_ip.lower():
            raise httpx.ConnectError(
                f"refused to connect to {request_host}: pinned to {self._hostname}"
            )
        new_url = request.url.copy_with(host=_bracket_ipv6(self._pinned_ip))
        new_headers = httpx.Headers(request.headers)
        if "host" not in {k.lower() for k in new_headers}:
            host_value = self._hostname
            if request.url.port:
                host_value = f"{self._hostname}:{request.url.port}"
            new_headers["Host"] = host_value
        extensions = {
            **(request.extensions or {}),
            "sni_hostname": self._hostname,
        }
        new_request = httpx.Request(
            method=request.method,
            url=new_url,
            headers=new_headers,
            stream=request.stream,
            extensions=extensions,
        )
        return await super().handle_async_request(new_request)


def pinned_async_client(
    pinned: PinnedOutbound,
    *,
    timeout: float | None = None,
    follow_redirects: bool = False,
    http2: bool = False,
    verify: bool = True,
) -> httpx.AsyncClient:
    transport = _IPPinnedTransport(
        hostname=pinned.hostname,
        pinned_ip=pinned.pinned_ip,
        verify=verify,
        http2=http2,
        limits=_DEFAULT_LIMITS,
    )
    return httpx.AsyncClient(
        transport=transport,
        timeout=timeout,
        follow_redirects=follow_redirects,
    )
