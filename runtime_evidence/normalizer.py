"""Normalize loose input JSON into the canonical runtime payload shape."""

from __future__ import annotations

import re
from typing import Any

from .canonical import sha256_hex

REQUIRED_INPUT_FIELDS = ["case_id", "source_system", "target_system", "operation", "payload"]

ALIASES = {
    "case_id": [
        "case_id",
        "caseId",
        "case",
        "id",
        "run_id",
        "runId",
        "request_id",
        "requestId",
        "record_id",
        "recordId",
        "ticket_id",
        "ticketId",
        "execution_id",
        "executionId",
    ],
    "source_system": [
        "source_system",
        "sourceSystem",
        "source",
        "src",
        "from",
        "origin",
        "origin_system",
        "originSystem",
        "producer",
        "submitted_by",
        "submittedBy",
    ],
    "target_system": [
        "target_system",
        "targetSystem",
        "target",
        "destination",
        "dst",
        "to",
        "consumer",
        "sink",
        "recipient",
    ],
    "operation": [
        "operation",
        "op",
        "action",
        "event_type",
        "eventType",
        "type",
        "task",
        "workflow",
        "intent",
        "command",
    ],
    "payload": [
        "payload",
        "data",
        "body",
        "content",
        "request",
        "input",
        "event",
        "record",
        "message",
        "values",
        "attributes",
    ],
}

COMMON_CONTAINERS = {
    "metadata",
    "meta",
    "context",
    "headers",
    "header",
    "envelope",
    "request",
    "event",
    "execution",
    "systems",
}

KNOWN_OPERATIONS = [
    "evidence_standardization",
    "artifact_generation",
    "lineage_capture",
    "replay_reference_capture",
    "consumer_handoff",
]

TEXT_FIELD_LABELS = {
    "case_id": [
        "case id",
        "case",
        "run id",
        "run",
        "request id",
        "request",
        "ticket id",
        "ticket",
        "record id",
        "record",
        "execution id",
        "execution",
    ],
    "source_system": [
        "source system",
        "source",
        "from",
        "origin",
        "producer",
        "submitted by",
        "submitted from",
    ],
    "target_system": [
        "target system",
        "target",
        "to",
        "destination",
        "consumer",
        "recipient",
        "sink",
    ],
    "operation": [
        "operation",
        "action",
        "command",
        "workflow",
        "intent",
        "task",
        "using",
        "for",
    ],
}

TEXT_STOP_WORDS = [
    "from",
    "to",
    "for",
    "using",
    "with",
    "operation",
    "action",
    "command",
    "workflow",
    "intent",
    "task",
    "target",
    "consumer",
    "recipient",
    "destination",
    "source",
    "producer",
    "origin",
    "payload",
    "body",
    "data",
    "case",
    "run",
    "request",
    "ticket",
    "record",
    "execution",
]

TEXT_ID_PATTERN = re.compile(
    r"\b(?:runtime-proof|proof|case|ticket|record|request|run|exec|execution)[-_][A-Za-z0-9][A-Za-z0-9_.:-]*\b",
    re.IGNORECASE,
)


def normalize_input(raw: Any) -> dict[str, Any]:
    """Extract the canonical runtime input fields from canonical or loose JSON."""
    if isinstance(raw, dict) and _is_already_canonical(raw):
        return dict(raw)

    flattened = list(_walk(raw))
    text_candidates = list(_text_candidates(raw))
    normalized: dict[str, Any] = {}
    field_sources: dict[str, dict[str, str]] = {}

    for field in ["case_id", "source_system", "target_system", "operation"]:
        match = _find_best_scalar_match(field, flattened)
        if match is not None:
            path, value, key = match
            normalized[field] = str(value)
            field_sources[field] = {"path": path, "matched_key": key}

    for field in ["case_id", "source_system", "target_system", "operation"]:
        if field in normalized:
            continue
        text_match = _find_text_match(field, text_candidates)
        if text_match is not None:
            path, value, label = text_match
            normalized[field] = value
            field_sources[field] = {"path": path, "matched_key": label}

    payload_match = _find_best_payload_match(flattened)
    if payload_match is not None:
        path, value, key = payload_match
        normalized["payload"] = value
        field_sources["payload"] = {"path": path, "matched_key": key}
    else:
        normalized["payload"] = _payload_from_raw(raw, field_sources)
        field_sources["payload"] = {"path": "$", "matched_key": "<derived_from_raw_input>"}

    missing_fields = [field for field in REQUIRED_INPUT_FIELDS if field not in normalized]
    normalized["_normalization"] = {
        "status": "canonicalized_from_noncanonical_input",
        "raw_input_sha256": sha256_hex(raw),
        "raw_input_type": type(raw).__name__,
        "field_sources": field_sources,
        "missing_fields": missing_fields,
    }
    return normalized


def _is_already_canonical(raw: dict[str, Any]) -> bool:
    return all(field in raw for field in REQUIRED_INPUT_FIELDS)


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _alias_set(field: str) -> set[str]:
    return {_normalize_key(alias) for alias in ALIASES[field]}


def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            yield item_path, key, item
            yield from _walk(item, item_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            yield item_path, str(index), item
            yield from _walk(item, item_path)


def _text_candidates(value: Any, path: str = "$"):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _text_candidates(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _text_candidates(item, f"{path}[{index}]")


def _find_best_scalar_match(field: str, flattened: list[tuple[str, str, Any]]) -> tuple[str, Any, str] | None:
    aliases = _alias_set(field)
    matches = []
    for path, key, value in flattened:
        if isinstance(value, (dict, list)) or value is None:
            continue
        normalized_key = _normalize_key(key)
        if normalized_key not in aliases:
            continue
        matches.append((_score_path(path, field, key), path, value, key))
    if not matches:
        return None
    _, path, value, key = sorted(matches, key=lambda item: item[0])[0]
    return path, value, key


def _find_best_payload_match(flattened: list[tuple[str, str, Any]]) -> tuple[str, Any, str] | None:
    aliases = _alias_set("payload")
    matches = []
    for path, key, value in flattened:
        normalized_key = _normalize_key(key)
        if normalized_key not in aliases:
            continue
        matches.append((_payload_score(path, key), path, value, key))
    if not matches:
        return None
    _, path, value, key = sorted(matches, key=lambda item: item[0])[0]
    return path, value, key


def _find_text_match(field: str, candidates: list[tuple[str, str]]) -> tuple[str, str, str] | None:
    matches = []
    for path, text in candidates:
        extracted = _extract_field_from_text(field, text)
        if extracted is None:
            continue
        value, label = extracted
        matches.append((_text_score(path, field, label), path, value, label))
    if not matches:
        return None
    _, path, value, label = sorted(matches, key=lambda item: item[0])[0]
    return path, value, label


def _extract_field_from_text(field: str, text: str) -> tuple[str, str] | None:
    cleaned = " ".join(text.split())
    if not cleaned:
        return None

    if field == "operation":
        operation = _extract_known_operation(cleaned)
        if operation is not None:
            return operation, "<plain_text:known_operation>"

    if field == "case_id":
        id_match = TEXT_ID_PATTERN.search(cleaned)
        if id_match:
            return _clean_text_value(id_match.group(0)), "<plain_text:id_pattern>"

    for label in TEXT_FIELD_LABELS[field]:
        value = _capture_labeled_text_value(cleaned, label)
        if value is None:
            continue
        if field == "operation":
            operation = _operation_from_value(value)
            return operation, f"<plain_text:{label}>"
        return _clean_text_value(value), f"<plain_text:{label}>"
    return None


def _extract_known_operation(text: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    padded = f"_{normalized}_"
    for operation in KNOWN_OPERATIONS:
        if f"_{operation}_" in padded:
            return operation
    return None


def _operation_from_value(value: str) -> str:
    known_operation = _extract_known_operation(value)
    if known_operation is not None:
        return known_operation
    return _clean_text_value(value).lower().replace("-", "_").replace(" ", "_")


def _capture_labeled_text_value(text: str, label: str) -> str | None:
    label_pattern = re.escape(label).replace(r"\ ", r"\s+")
    quoted = re.search(
        rf"\b{label_pattern}\b\s*(?:is|as|=|:|-)?\s*[\"']([^\"']+)[\"']",
        text,
        re.IGNORECASE,
    )
    if quoted:
        return quoted.group(1)

    stop_pattern = "|".join(re.escape(word).replace(r"\ ", r"\s+") for word in TEXT_STOP_WORDS if word != label)
    bare = re.search(
        rf"\b{label_pattern}\b\s*(?:is|as|=|:|-)?\s+(.+?)(?=\s+(?:{stop_pattern})\b|[.;,\n]|$)",
        text,
        re.IGNORECASE,
    )
    if not bare:
        return None
    value = bare.group(1).strip()
    return value if value else None


def _clean_text_value(value: str) -> str:
    return value.strip().strip("\"'`.,;:()[]{}")


def _text_score(path: str, field: str, label: str) -> tuple[int, int, str]:
    label_rank = 0 if label == f"<plain_text:{field}>" else 1
    if field == "case_id" and label == "<plain_text:id_pattern>":
        label_rank = 0
    if field == "operation" and label == "<plain_text:known_operation>":
        label_rank = 0
    depth = path.count(".") + path.count("[")
    return (label_rank, depth, path)


def _payload_score(path: str, key: str) -> tuple[int, int, int, str]:
    normalized_key = _normalize_key(key)
    precise_payload_keys = {"payload", "body", "data", "content", "input", "request", "values", "attributes"}
    broad_payload_keys = {"event", "record", "message"}
    if normalized_key == "payload":
        key_priority = 0
    elif normalized_key in precise_payload_keys:
        key_priority = 1
    elif normalized_key in broad_payload_keys:
        key_priority = 2
    else:
        key_priority = 3
    exact_score, depth_score, stable_path = _score_path(path, "payload", key)
    return (key_priority, exact_score, depth_score, stable_path)


def _score_path(path: str, field: str, key: str) -> tuple[int, int, str]:
    depth = path.count(".") + path.count("[")
    normalized_key = _normalize_key(key)
    exact = normalized_key == _normalize_key(field)
    container_bonus = 0 if any(f".{name}" in path for name in COMMON_CONTAINERS) else 1
    return (0 if exact else 1, depth + container_bonus, path)


def _payload_from_raw(raw: Any, field_sources: dict[str, dict[str, str]]) -> Any:
    if not isinstance(raw, dict):
        return raw

    used_top_level_keys = {
        source["path"].split(".", 2)[1]
        for source in field_sources.values()
        if source["path"].startswith("$.") and "." not in source["path"][2:] and "[" not in source["path"]
    }
    remaining = {key: value for key, value in raw.items() if key not in used_top_level_keys}
    return remaining if remaining else raw
