"""SHAKTI consumer adapter for TANTRA evidence validation."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys
from typing import Any

from runtime_evidence.canonical import CONTRACT_VERSION, ENTRYPOINT_NAME, SCHEMA_VERSION, stable_id
from runtime_evidence.producer import REQUIRED_EVIDENCE_FIELDS, file_hash, read_json, write_json

ADAPTER_NAME = "shakti-consumer-adapter"
ADAPTER_VERSION = "1.0.0"
DECISION_APPROVED = "APPROVED"
DECISION_REJECTED = "REJECTED"


def _check(name: str, passed: bool, expected: Any = None, actual: Any = None, detail: str = "") -> dict[str, Any]:
    result = {
        "name": name,
        "status": "pass" if passed else "fail",
    }
    if expected is not None:
        result["expected"] = expected
    if actual is not None:
        result["actual"] = actual
    if detail:
        result["detail"] = detail
    return result


def _reference_hash_ok(base_dir: Path, reference: Any) -> tuple[bool, str, str]:
    if not isinstance(reference, dict):
        return False, "", "reference is not an object"
    file_reference = reference.get("reference")
    expected_hash = reference.get("sha256")
    if not isinstance(file_reference, str) or not isinstance(expected_hash, str):
        return False, str(file_reference), "reference or sha256 missing"
    reference_path = Path(file_reference)
    if reference_path.is_absolute() or ".." in reference_path.parts:
        return False, file_reference, "reference escapes evidence container"
    artifact_path = base_dir / reference_path
    if not artifact_path.exists():
        return False, file_reference, "artifact is missing"
    actual_hash = file_hash(artifact_path)
    if actual_hash != expected_hash:
        return False, file_reference, f"hash mismatch: expected {expected_hash}, actual {actual_hash}"
    return True, file_reference, "hash verified"


def _artifact_checks(evidence_dir: Path, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    payload_ok, payload_ref, payload_detail = _reference_hash_ok(evidence_dir, evidence.get("payload_reference"))
    checks.append(_check("payload_reference_integrity", payload_ok, actual=payload_ref, detail=payload_detail))

    artifacts = evidence.get("artifacts")
    checks.append(_check("artifact_index_present", isinstance(artifacts, dict), expected="object", actual=type(artifacts).__name__))
    if not isinstance(artifacts, dict):
        return checks

    for artifact_name in ["input", "output", "lineage", "replay", "handover"]:
        artifact_ok, artifact_ref, artifact_detail = _reference_hash_ok(evidence_dir, artifacts.get(artifact_name))
        checks.append(_check(f"artifact_integrity_{artifact_name}", artifact_ok, actual=artifact_ref, detail=artifact_detail))
    return checks


def _schema_checks(evidence: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(evidence, dict):
        return {}, [
            _check(
                "evidence_bundle_object",
                False,
                expected="object",
                actual=type(evidence).__name__,
            )
        ]

    missing_fields = [field for field in REQUIRED_EVIDENCE_FIELDS if field not in evidence]
    checks = [
        _check(
            "schema_required_fields",
            not missing_fields,
            expected=REQUIRED_EVIDENCE_FIELDS,
            actual=missing_fields if missing_fields else "complete",
        )
    ]
    for field in ["execution_id", "trace_id", "artifact_reference", "replay_reference"]:
        value = evidence.get(field)
        checks.append(
            _check(
                f"schema_{field}_present",
                isinstance(value, str) and bool(value.strip()),
                expected="non-empty string",
                actual=value if value is not None else "<missing>",
            )
        )
    return evidence, checks


def _replay_checks(evidence_dir: Path, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    replay_meta = evidence.get("artifacts", {}).get("replay") if isinstance(evidence.get("artifacts"), dict) else None
    replay_reference = replay_meta.get("reference") if isinstance(replay_meta, dict) else "replay_bundle.json"
    if not isinstance(replay_reference, str) or not replay_reference:
        replay_reference = "replay_bundle.json"
    replay_path = evidence_dir / replay_reference
    checks.append(_check("replay_bundle_present", replay_path.exists(), actual=replay_reference))
    if not replay_path.exists():
        return checks

    replay = read_json(replay_path)
    checks.append(
        _check(
            "replay_reference_consistency",
            replay.get("replay_reference") == evidence.get("replay_reference"),
            expected=evidence.get("replay_reference"),
            actual=replay.get("replay_reference"),
        )
    )
    checks.append(
        _check(
            "replay_command_entrypoint",
            isinstance(replay.get("replay_command"), str) and f"{ENTRYPOINT_NAME} run" in replay["replay_command"],
            expected=f"{ENTRYPOINT_NAME} run",
            actual=replay.get("replay_command"),
        )
    )
    runtime_requirements = replay.get("runtime_requirements", {})
    checks.append(
        _check(
            "replay_runtime_entrypoint",
            isinstance(runtime_requirements, dict) and runtime_requirements.get("entrypoint") == ENTRYPOINT_NAME,
            expected=ENTRYPOINT_NAME,
            actual=runtime_requirements.get("entrypoint") if isinstance(runtime_requirements, dict) else None,
        )
    )

    replay_inputs = replay.get("replay_inputs")
    expected_outputs = replay.get("expected_outputs")
    input_meta = replay_inputs[0] if isinstance(replay_inputs, list) and replay_inputs else None
    output_meta = expected_outputs[0] if isinstance(expected_outputs, list) and expected_outputs else None
    input_ok, input_ref, input_detail = _reference_hash_ok(evidence_dir, input_meta)
    output_ok, output_ref, output_detail = _reference_hash_ok(evidence_dir, output_meta)
    checks.append(_check("replay_input_integrity", input_ok, actual=input_ref, detail=input_detail))
    checks.append(_check("replay_expected_output_integrity", output_ok, actual=output_ref, detail=output_detail))
    return checks


def validate_evidence(evidence_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    evidence_raw = read_json(evidence_path)
    evidence, checks = _schema_checks(evidence_raw)
    if not isinstance(evidence_raw, dict):
        return evidence, checks

    evidence_dir = evidence_path.parent
    checks.extend([
        _check("contract_version", evidence.get("contract_version") == CONTRACT_VERSION, expected=CONTRACT_VERSION, actual=evidence.get("contract_version")),
        _check("schema_version", evidence.get("schema_version") == SCHEMA_VERSION, expected=SCHEMA_VERSION, actual=evidence.get("schema_version")),
        _check("execution_status_success", evidence.get("execution_status") == "success", expected="success", actual=evidence.get("execution_status")),
        _check("confidence_available", isinstance(evidence.get("confidence"), (int, float)), expected="number", actual=type(evidence.get("confidence")).__name__),
        _check("confidence_threshold", isinstance(evidence.get("confidence"), (int, float)) and evidence.get("confidence") >= 0.75, expected=">=0.75", actual=evidence.get("confidence")),
        _check("self_contained_consumer_package", evidence.get("consumer_compatibility", {}).get("self_contained") is True, expected=True, actual=evidence.get("consumer_compatibility", {}).get("self_contained")),
    ])
    checks.extend(_artifact_checks(evidence_dir, evidence))
    checks.extend(_replay_checks(evidence_dir, evidence))
    return evidence, checks


def _reason_codes(checks: list[dict[str, Any]]) -> list[str]:
    return [check["name"] for check in checks if check["status"] != "pass"]


def build_validation_decision(evidence_path: Path, evidence: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_hash = file_hash(evidence_path)
    reason_codes = _reason_codes(checks)
    decision = DECISION_APPROVED if not reason_codes else DECISION_REJECTED
    decision_material = {
        "evidence_hash": evidence_hash,
        "execution_id": evidence.get("execution_id"),
        "trace_id": evidence.get("trace_id"),
        "checks": checks,
        "decision": decision,
    }
    return {
        "adapter": {
            "name": ADAPTER_NAME,
            "version": ADAPTER_VERSION,
        },
        "decision": decision,
        "decision_id": stable_id("validation_decision", decision_material),
        "deterministic": True,
        "evidence": {
            "reference": evidence_path.as_posix(),
            "sha256": evidence_hash,
        },
        "execution_id": evidence.get("execution_id"),
        "governance_status": "VALIDATED" if decision == DECISION_APPROVED else "REJECTED",
        "reason_codes": reason_codes,
        "replay_reconstruction": "available" if "replay_bundle_present" not in reason_codes else "unavailable",
        "schema_version": evidence.get("schema_version"),
        "trace_id": evidence.get("trace_id"),
        "validation_checks": checks,
    }


def build_governance_record(evidence: dict[str, Any], validation_decision: dict[str, Any]) -> dict[str, Any]:
    record_material = {
        "decision_id": validation_decision["decision_id"],
        "execution_id": evidence.get("execution_id"),
        "trace_id": evidence.get("trace_id"),
    }
    return {
        "consumer": "SHAKTI",
        "contract_version": evidence.get("contract_version"),
        "decision": validation_decision["decision"],
        "decision_id": validation_decision["decision_id"],
        "deterministic": True,
        "execution_id": evidence.get("execution_id"),
        "governance_record_id": stable_id("governance_record", record_material),
        "input_extraction": evidence.get("input_extraction"),
        "producer": evidence.get("producer"),
        "replay_reference": evidence.get("replay_reference"),
        "schema_version": evidence.get("schema_version"),
        "source_system": evidence.get("source_system"),
        "target_system": evidence.get("target_system"),
        "trace_id": evidence.get("trace_id"),
        "validation_status": validation_decision["governance_status"],
    }


def build_registration_reference(output_root: Path, validation_path: Path, governance_path: Path, governance_record: dict[str, Any], validation_decision: dict[str, Any]) -> dict[str, Any]:
    validation_hash = file_hash(validation_path)
    governance_hash = file_hash(governance_path)
    registration_material = {
        "governance_record_hash": governance_hash,
        "validation_decision_hash": validation_hash,
        "trace_id": governance_record.get("trace_id"),
    }
    return {
        "consumer": "SHAKTI",
        "deterministic": True,
        "execution_id": governance_record.get("execution_id"),
        "governance_record": {
            "reference": governance_path.name,
            "sha256": governance_hash,
        },
        "registration_id": stable_id("shakti_registration", registration_material),
        "registration_status": "REGISTERED" if validation_decision["decision"] == DECISION_APPROVED else "REJECTED",
        "trace_id": governance_record.get("trace_id"),
        "validation_decision": {
            "reference": validation_path.name,
            "sha256": validation_hash,
        },
    }


def consume_evidence(evidence_path: Path, output_root: Path) -> dict[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    evidence, checks = validate_evidence(evidence_path)
    validation_decision = build_validation_decision(evidence_path, evidence, checks)
    governance_record = build_governance_record(evidence, validation_decision)

    validation_path = output_root / "validation_decision.json"
    governance_path = output_root / "governance_record.json"
    registration_path = output_root / "registration_reference.json"
    write_json(validation_path, validation_decision)
    write_json(governance_path, governance_record)
    registration_reference = build_registration_reference(output_root, validation_path, governance_path, governance_record, validation_decision)
    write_json(registration_path, registration_reference)
    return {
        "validation_decision": validation_path,
        "governance_record": governance_path,
        "registration_reference": registration_path,
    }


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Consume a SHAKTI evidence bundle and emit deterministic governance outputs.")
    parser.add_argument("--evidence", required=True, type=Path, help="Path to evidence_bundle.json")
    parser.add_argument("--out", default=Path("."), type=Path, help="Output directory for governance JSON files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = consume_evidence(args.evidence, args.out)
    print({key: path.as_posix() for key, path in paths.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
