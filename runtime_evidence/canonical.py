"""Canonical serialization and deterministic identifier helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

CONTRACT_VERSION = "shakti-runtime-evidence/v1"
SCHEMA_VERSION = "1.0.0"
PRODUCER_NAME = "runtime-evidence-producer"
ENTRYPOINT_NAME = "runtime_evidence_producer.py"


def canonical_json(value: Any) -> str:
    """Return stable JSON for hashing and deterministic references."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(value: Any) -> str:
    """Return stable, human-readable JSON for generated artifact files."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def sha256_hex(value: Any) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = canonical_json(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stable_id(prefix: str, *parts: Any, length: int = 20) -> str:
    material = {"prefix": prefix, "parts": parts}
    return f"{prefix}_{sha256_hex(material)[:length]}"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
