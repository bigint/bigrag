from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

from bigrag.services.runtime_setting_specs import REGISTRY, SettingSpec


def _coerce_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_parts = value.replace("\n", ",").split(",")
        return [part.strip() for part in raw_parts if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("Expected a list")


def _coerce_int_list(value: Any) -> list[int]:
    items = _coerce_list(value)
    out: list[int] = []
    for item in items:
        try:
            out.append(int(item))
        except (TypeError, ValueError) as exc:
            raise ValueError("Expected integer values") from exc
    return out


def _is_cloudflare_r2_host(hostname: str | None) -> bool:
    host = (hostname or "").lower().rstrip(".")
    return host == "r2.cloudflarestorage.com" or host.endswith(".r2.cloudflarestorage.com")


def _normalize_backup_s3_endpoint_url(raw_url: str) -> str:
    from bigrag.services.url_security import UnsafeOutboundUrlError, normalize_url_root

    try:
        normalized = normalize_url_root(raw_url)
    except UnsafeOutboundUrlError as exc:
        raise ValueError(str(exc)) from exc
    parsed = urlparse(normalized)
    if not parsed.path.strip("/"):
        return normalized
    if _is_cloudflare_r2_host(parsed.hostname):
        return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    raise ValueError(
        "Backup S3 endpoint URL must not include a path. Use bucket and prefix instead."
    )


def validate_setting_value(key: str, value: Any) -> Any:
    spec = REGISTRY.get(key)
    if spec is None:
        raise KeyError(key)
    if spec.kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true"
        raise ValueError("Expected a boolean")
    if spec.kind == "int":
        value = _coerce_none(value)
        if value is None:
            return None if spec.default is None else spec.default
        if isinstance(value, bool):
            raise ValueError("Expected an integer")
        try:
            coerced = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Expected an integer") from exc
        _validate_numeric_bounds(spec, coerced)
        return coerced
    if spec.kind == "float":
        value = _coerce_none(value)
        if value is None:
            return None if spec.default is None else spec.default
        if isinstance(value, bool):
            raise ValueError("Expected a number")
        try:
            coerced = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Expected a number") from exc
        _validate_numeric_bounds(spec, coerced)
        return coerced
    if spec.kind == "string":
        value = _coerce_none(value)
        if value is None:
            return None
        coerced_str = str(value)
        if key == "backup_s3_endpoint_url" and coerced_str.strip():
            return _normalize_backup_s3_endpoint_url(coerced_str.strip())
        url_keys = {"turbopuffer_base_url"}
        if key in url_keys and coerced_str.strip():
            from bigrag.services.url_security import UnsafeOutboundUrlError, normalize_url_root

            try:
                coerced_str = normalize_url_root(coerced_str.strip())
            except UnsafeOutboundUrlError as exc:
                raise ValueError(str(exc)) from exc
        return coerced_str
    if spec.kind == "secret":
        value = _coerce_none(value)
        return None if value is None else str(value)
    if spec.kind == "string_list":
        return _coerce_list(value)
    if spec.kind == "int_list":
        return _coerce_int_list(value)
    if spec.kind == "select":
        value = _coerce_none(value)
        if value is None:
            return None if spec.default is None else spec.default
        selected = str(value)
        if selected not in spec.options:
            raise ValueError(f"Expected one of: {', '.join(spec.options)}")
        return selected
    raise ValueError("Unsupported setting type")


def _validate_numeric_bounds(spec: SettingSpec, value: int | float) -> None:
    if spec.min is not None and value < spec.min:
        raise ValueError(f"Must be at least {spec.min:g}")
    if spec.max is not None and value > spec.max:
        raise ValueError(f"Must be at most {spec.max:g}")
