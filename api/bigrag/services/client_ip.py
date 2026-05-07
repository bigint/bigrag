from __future__ import annotations

import ipaddress

from starlette.requests import Request
from starlette.types import Scope

from bigrag.config import settings
from bigrag.services import runtime_settings


def _trusted_networks() -> tuple[ipaddress._BaseNetwork, ...]:
    nets: list[ipaddress._BaseNetwork] = []
    raw_proxies = runtime_settings.sync_value("trusted_proxies") or settings.trusted_proxies
    for raw in raw_proxies:
        try:
            nets.append(ipaddress.ip_network(raw, strict=False))
        except ValueError:
            continue
    return tuple(nets)


def _is_trusted(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in net for net in _trusted_networks())


def _resolve(immediate: str | None, forwarded: str | None) -> str | None:
    if immediate is None:
        return None
    if not forwarded or not _is_trusted(immediate):
        return immediate
    chain = [c.strip() for c in forwarded.split(",") if c.strip()]
    for candidate in reversed(chain):
        if not _is_trusted(candidate):
            return candidate
    return immediate


def client_ip(request: Request) -> str | None:
    immediate = request.client[0] if request.client else None
    return _resolve(immediate, request.headers.get("x-forwarded-for"))


def client_ip_from_scope(scope: Scope) -> str | None:
    client = scope.get("client")
    immediate = client[0] if client else None
    forwarded: str | None = None
    for name, value in scope.get("headers", []):
        if name.lower() == b"x-forwarded-for":
            forwarded = value.decode("latin-1")
            break
    return _resolve(immediate, forwarded)
