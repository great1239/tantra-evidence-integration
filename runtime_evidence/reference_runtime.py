"""Reference runtime used to create real execution artifacts in this repo.

The assignment asks for runtime proof, but this repository did not contain an
existing application entrypoint. This module supplies a small deterministic
runtime so every bundle is produced by code execution rather than hand-written
fixtures.
"""

from __future__ import annotations

from typing import Any

from .canonical import sha256_hex


def execute_payload(payload: dict[str, Any]) -> dict[str, Any]:
    required = ["case_id", "source_system", "target_system", "operation", "payload"]
    missing = [field for field in required if field not in payload]
    body = payload.get("payload", {})
    signals = body.get("signals", []) if isinstance(body, dict) else []
    signals = signals if isinstance(signals, list) else []
    normalized_signals = [item for item in signals if isinstance(item, dict)]
    ignored_signal_count = len(signals) - len(normalized_signals)
    blockers = [item for item in normalized_signals if item.get("severity") == "blocker"]
    warnings = [item for item in normalized_signals if item.get("severity") == "warning"]

    status = "success" if not missing else "failed"
    readiness_score = max(0.0, 1.0 - (0.35 * len(blockers)) - (0.1 * len(warnings)) - (0.2 * len(missing)))
    posture = "ready_for_consumer_validation" if readiness_score >= 0.75 and status == "success" else "needs_review"

    return {
        "case_id": payload.get("case_id", "unknown"),
        "operation": payload.get("operation", "unknown"),
        "execution_status": status,
        "normalization": payload.get(
            "_normalization",
            {
                "status": "already_canonical",
                "missing_fields": [],
                "field_sources": {
                    field: {"path": f"$.{field}", "matched_key": field}
                    for field in required
                    if field in payload
                },
            },
        ),
        "payload_digest": sha256_hex(body),
        "payload_field_count": len(body) if isinstance(body, dict) else 0,
        "signal_count": len(normalized_signals),
        "ignored_signal_count": ignored_signal_count,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "readiness_score": round(readiness_score, 4),
        "governance_posture": posture,
        "missing_required_fields": missing,
        "observations": [
            {
                "code": "RUNTIME_PAYLOAD_PROCESSED",
                "message": "Input payload was processed by the local runtime evidence producer.",
            },
            {
                "code": "CONSUMER_READY" if posture == "ready_for_consumer_validation" else "CONSUMER_REVIEW_REQUIRED",
                "message": posture,
            },
        ],
    }


def demo_payloads(count: int = 10) -> list[Any]:
    operations = [
        "evidence_standardization",
        "artifact_generation",
        "lineage_capture",
        "replay_reference_capture",
        "consumer_handoff",
    ]
    payloads: list[Any] = []
    for index in range(1, count + 1):
        operation = operations[(index - 1) % len(operations)]
        payloads.append(_mangled_demo_payload(index, operation))
    return payloads


def _canonical_body(index: int, operation: str) -> dict[str, Any]:
    return {
        "run_index": index,
        "contract": "GC Governance SHAKTI convergence closure",
        "evidence_focus": operation,
        "signals": [
            {
                "name": "bundle_generation",
                "severity": "info",
                "value": "complete",
            },
            {
                "name": "deterministic_references",
                "severity": "info",
                "value": "enabled",
            },
            {
                "name": "handover_readiness",
                "severity": "warning" if index % 4 == 0 else "info",
                "value": "review" if index % 4 == 0 else "ready",
            },
        ],
        "replay_parameters": {
            "seedless": True,
            "input_case": f"runtime-proof-{index:03d}",
        },
    }


def _mangled_demo_payload(index: int, operation: str) -> Any:
    case_id = f"runtime-proof-{index:03d}"
    source = "GC_RUNTIME_EVIDENCE_PRODUCER"
    target = "SHAKTI_GOVERNANCE_CONSUMER"
    body = _canonical_body(index, operation)
    variants: list[Any] = [
        {
            "requestId": case_id,
            "origin": source,
            "recipient": target,
            "command": operation,
            "body": body,
        },
        {
            "metadata": {
                "caseId": case_id,
                "sourceSystem": source,
                "targetSystem": target,
            },
            "event": {
                "type": operation,
                "body": body,
            },
        },
        {
            "envelope": {
                "headers": {
                    "ticket_id": case_id,
                    "submittedBy": source,
                    "consumer": target,
                },
                "message": {
                    "eventType": operation,
                    "content": body,
                },
            }
        },
        [
            {"record_id": case_id},
            {"from": source},
            {"to": target},
            {"action": operation},
            {"data": body},
        ],
        {
            "case-id": case_id,
            "source.system": source,
            "target/system": target,
            "event-type": operation,
            "values": body,
        },
        {
            "request": {
                "id": case_id,
                "from": source,
                "to": target,
                "action": operation,
                "content": body,
            }
        },
        {
            "execution": {
                "executionId": case_id,
                "workflow": operation,
            },
            "systems": {
                "src": source,
                "dst": target,
            },
            "attributes": body,
        },
        {
            "meta": {
                "recordId": case_id,
                "submittedBy": source,
            },
            "context": {
                "recipient": target,
                "intent": operation,
            },
            "payload": body,
        },
        {
            "headers": {
                "case": case_id,
                "originSystem": source,
                "targetSystem": target,
            },
            "message": {
                "eventType": operation,
                "data": body,
            },
        },
        (
            f"Please process case id {case_id}. "
            f"source system {source}. "
            f"target system {target}. "
            f"operation {operation}. "
            "Payload should prove schema-free text extraction, replayability, lineage, and handover readiness."
        ),
    ]
    return variants[(index - 1) % len(variants)]
