from __future__ import annotations


def validate_storage_key(key: str) -> str:
    clean = key.lstrip("/")
    if not clean or clean == ".":
        raise ValueError(f"Invalid storage key: {key}")
    if any(part == ".." for part in clean.split("/")):
        raise ValueError(f"Invalid storage key: {key}")
    return clean
