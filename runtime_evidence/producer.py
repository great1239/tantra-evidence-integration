"""Evidence bundle generation and validation."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from .canonical import (
    CONTRACT_VERSION,
    PRODUCER_NAME,
    SCHEMA_VERSION,
    pretty_json,
    sha256_hex,
    stable_id,
    utc_timestamp,
)
from .normalizer import normalize_input
from .reference_runtime import execute_payload

REQUIRED_EVIDENCE_FIELDS = [
    "execution_id",
    "trace_id",
    "contract_version",
    "schema_version",
    "timestamp",
    "source_system",
    "target_system",
    "payload_reference",
    "artifact_reference",
    "replay_reference",
    "execution_status",
    "confidence",
]

REQUIRED_FILES = [
    "input.json",
    "output.json",
    "evidence_bundle.json",
    "lineage_bundle.json",
    "replay_bundle.json",
    "handover_bundle.json",
    "execution.log",
]

REQUIRED_BUNDLE_FILES = [
    "evidence_bundle.json",
    "lineage_bundle.json",
    "replay_bundle.json",
    "handover_bundle.json",
]

REQUIRED_EXECUTION_CONTEXT_FIELDS = [
    "what_happened",
    "where_it_happened",
    "when_it_happened",
    "what_produced_it",
    "what_consumed_it",
    "what_can_be_replayed",
]

REQUIRED_INPUT_EXTRACTION_FIELDS = [
    "input_reference",
    "input_shape",
    "raw_input_sha256",
    "raw_input_type",
    "canonical_fields",
    "field_sources",
    "missing_fields",
]

REQUIRED_CANONICAL_FIELDS = [
    "case_id",
    "source_system",
    "target_system",
    "operation",
    "payload_type",
    "payload_sha256",
]

REQUIRED_ARTIFACT_KEYS = ["input", "output", "lineage", "replay", "handover"]

EXPECTED_LINEAGE_NODES = {
    "input_payload",
    "runtime_processor",
    "runtime_output",
    "governance_consumer",
}

EXPECTED_LINEAGE_EDGES = {
    ("input_payload", "runtime_processor", "consumed_by"),
    ("runtime_processor", "runtime_output", "produced"),
    ("runtime_output", "governance_consumer", "available_to"),
}

EXPECTED_PROVENANCE_ACTIONS = [
    "submitted_payload",
    "executed_payload",
    "generated_evidence_bundles",
]

PROPAGATED_TRACE_FIELDS = [
    "execution_id",
    "trace_id",
    "contract_version",
    "schema_version",
    "timestamp",
    "source_system",
    "target_system",
]

REQUIRED_LOG_KEYS = [
    "timestamp",
    "execution_id",
    "trace_id",
    "input_sha256",
    "output_sha256",
    "status",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(value) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return sha256_hex(path.read_bytes())


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _missing_fields(value: dict[str, Any], required: list[str]) -> list[str]:
    return [field for field in required if field not in value]


def _execution_context(payload: dict[str, Any], result: dict[str, Any], timestamp: str) -> dict[str, str]:
    return {
        "what_happened": f"{payload.get('operation', 'unknown')} executed with status {result['execution_status']}.",
        "where_it_happened": PRODUCER_NAME,
        "when_it_happened": timestamp,
        "what_produced_it": "operational_drift_monitor.py",
        "what_consumed_it": payload.get("target_system", "unknown"),
        "what_can_be_replayed": "input.json can be rerun through replay_bundle.json.replay_command and compared to output.json.",
    }


def _input_extraction(payload: dict[str, Any], raw_payload: Any) -> dict[str, Any]:
    normalization = payload.get("_normalization")
    canonical_fields = {
        "case_id": payload.get("case_id"),
        "source_system": payload.get("source_system"),
        "target_system": payload.get("target_system"),
        "operation": payload.get("operation"),
        "payload_type": type(payload.get("payload")).__name__,
        "payload_sha256": sha256_hex(payload.get("payload")),
    }
    if normalization:
        return {
            "input_reference": "input.json",
            "input_shape": "noncanonical_extracted",
            "raw_input_sha256": normalization["raw_input_sha256"],
            "raw_input_type": normalization["raw_input_type"],
            "canonical_fields": canonical_fields,
            "field_sources": normalization["field_sources"],
            "missing_fields": normalization["missing_fields"],
        }
    return {
        "input_reference": "input.json",
        "input_shape": "already_canonical",
        "raw_input_sha256": sha256_hex(raw_payload),
        "raw_input_type": type(raw_payload).__name__,
        "canonical_fields": canonical_fields,
        "field_sources": {
            field: {"path": f"$.{field}", "matched_key": field}
            for field in ["case_id", "source_system", "target_system", "operation", "payload"]
            if field in payload
        },
        "missing_fields": [],
    }


def produce_evidence_run(input_path: Path, output_root: Path) -> Path:
    raw_payload = read_json(input_path)
    payload = normalize_input(raw_payload)
    result = execute_payload(payload)
    timestamp = utc_timestamp()
    execution_context = _execution_context(payload, result, timestamp)
    input_extraction = _input_extraction(payload, raw_payload)

    payload_hash = sha256_hex(payload)
    output_hash = sha256_hex(result)
    execution_id = stable_id("exec", CONTRACT_VERSION, SCHEMA_VERSION, payload_hash)
    trace_id = stable_id("trace", payload.get("case_id", "unknown"), payload_hash)
    replay_reference = stable_id("replay", execution_id, output_hash)
    run_dir = output_root / execution_id
    run_dir.mkdir(parents=True, exist_ok=True)

    run_input_path = run_dir / "input.json"
    run_output_path = run_dir / "output.json"
    lineage_path = run_dir / "lineage_bundle.json"
    replay_path = run_dir / "replay_bundle.json"
    handover_path = run_dir / "handover_bundle.json"
    evidence_path = run_dir / "evidence_bundle.json"
    log_path = run_dir / "execution.log"

    write_json(run_input_path, raw_payload)
    write_json(run_output_path, result)

    common_refs = {
        "execution_id": execution_id,
        "trace_id": trace_id,
        "contract_version": CONTRACT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "timestamp": timestamp,
        "source_system": payload.get("source_system", "unknown"),
        "target_system": payload.get("target_system", "unknown"),
    }

    lineage_bundle = {
        **common_refs,
        "execution_context": execution_context,
        "input_extraction": input_extraction,
        "lineage_reference": stable_id("lineage", execution_id, payload_hash, output_hash),
        "nodes": [
            {
                "id": "input_payload",
                "type": "payload",
                "reference": "input.json",
                "sha256": file_hash(run_input_path),
            },
            {
                "id": "runtime_processor",
                "type": "producer",
                "name": PRODUCER_NAME,
                "version": SCHEMA_VERSION,
            },
            {
                "id": "runtime_output",
                "type": "artifact",
                "reference": "output.json",
                "sha256": file_hash(run_output_path),
            },
            {
                "id": "governance_consumer",
                "type": "consumer",
                "name": payload.get("target_system", "unknown"),
            },
        ],
        "edges": [
            {"from": "input_payload", "to": "runtime_processor", "relationship": "consumed_by"},
            {"from": "runtime_processor", "to": "runtime_output", "relationship": "produced"},
            {"from": "runtime_output", "to": "governance_consumer", "relationship": "available_to"},
        ],
        "provenance_chain": [
            {
                "step": 1,
                "actor": payload.get("source_system", "unknown"),
                "action": "submitted_payload",
                "artifact": "input.json",
            },
            {
                "step": 2,
                "actor": PRODUCER_NAME,
                "action": "executed_payload",
                "artifact": "output.json",
            },
            {
                "step": 3,
                "actor": PRODUCER_NAME,
                "action": "generated_evidence_bundles",
                "artifact": "evidence_bundle.json",
            },
        ],
    }
    write_json(lineage_path, lineage_bundle)

    replay_bundle = {
        **common_refs,
        "execution_context": execution_context,
        "input_extraction": input_extraction,
        "replay_reference": replay_reference,
        "replay_command": f"python operational_drift_monitor.py run --input {run_input_path.as_posix()} --out {output_root.as_posix()}",
        "replay_inputs": [
            {
                "reference": "input.json",
                "sha256": file_hash(run_input_path),
            }
        ],
        "expected_outputs": [
            {
                "reference": "output.json",
                "sha256": file_hash(run_output_path),
            }
        ],
        "determinism": {
            "random_generation": "not_used",
            "execution_id_basis": "sha256(contract_version + schema_version + extracted_canonical_input_payload)",
            "trace_id_basis": "sha256(case_id + extracted_canonical_input_payload)",
        },
        "runtime_requirements": {
            "language": "python",
            "stdlib_only": True,
            "entrypoint": "operational_drift_monitor.py",
        },
    }
    write_json(replay_path, replay_bundle)

    handover_bundle = {
        **common_refs,
        "execution_context": execution_context,
        "input_extraction": input_extraction,
        "handover_reference": stable_id("handover", execution_id, replay_reference),
        "bundle_index": {
            "evidence": "evidence_bundle.json",
            "lineage": "lineage_bundle.json",
            "replay": "replay_bundle.json",
            "input": "input.json",
            "output": "output.json",
            "log": "execution.log",
        },
        "consumer_instructions": [
            "Read evidence_bundle.json first for the canonical execution summary.",
            "Use lineage_bundle.json to reconstruct producer, artifact, and consumer relationships.",
            "Use replay_bundle.json to rerun the input and compare output hashes.",
        ],
        "known_limitations": [
            "This repository contained no upstream SHAKTI runtime, so the local reference runtime is the execution source.",
            "Timestamps record actual execution time and are not part of deterministic identifier generation.",
        ],
        "integration_readiness": "ready_for_consumer_validation" if result["execution_status"] == "success" else "blocked",
    }
    write_json(handover_path, handover_bundle)

    artifact_hashes = {
        "input": {"reference": "input.json", "sha256": file_hash(run_input_path)},
        "output": {"reference": "output.json", "sha256": file_hash(run_output_path)},
        "lineage": {"reference": "lineage_bundle.json", "sha256": file_hash(lineage_path)},
        "replay": {"reference": "replay_bundle.json", "sha256": file_hash(replay_path)},
        "handover": {"reference": "handover_bundle.json", "sha256": file_hash(handover_path)},
    }

    evidence_bundle = {
        **common_refs,
        "payload_reference": {
            "reference": "input.json",
            "sha256": file_hash(run_input_path),
        },
        "artifact_reference": _relative(run_dir, output_root),
        "replay_reference": replay_reference,
        "execution_status": result["execution_status"],
        "confidence": result["readiness_score"],
        "producer": {
            "name": PRODUCER_NAME,
            "version": SCHEMA_VERSION,
            "entrypoint": "operational_drift_monitor.py",
        },
        "consumer_compatibility": {
            "primary_consumer": payload.get("target_system", "unknown"),
            "contract": CONTRACT_VERSION,
            "self_contained": True,
        },
        "artifacts": artifact_hashes,
        "execution_context": execution_context,
        "input_extraction": input_extraction,
        "summary": execution_context,
    }
    write_json(evidence_path, evidence_bundle)

    log_path.write_text(
        "\n".join(
            [
                f"timestamp={timestamp}",
                f"execution_id={execution_id}",
                f"trace_id={trace_id}",
                f"input_sha256={file_hash(run_input_path)}",
                f"output_sha256={file_hash(run_output_path)}",
                f"status={result['execution_status']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return run_dir


def _load_json_for_validation(run_dir: Path, name: str, errors: list[str]) -> Any | None:
    path = run_dir / name
    if not path.exists():
        return None
    try:
        return read_json(path)
    except json.JSONDecodeError as exc:
        errors.append(f"{run_dir}: {name} is not valid JSON: {exc.msg}")
    except OSError as exc:
        errors.append(f"{run_dir}: {name} could not be read: {exc}")
    return None


def _validate_reference_hash(run_dir: Path, meta: Any, label: str, errors: list[str]) -> None:
    if not isinstance(meta, dict):
        errors.append(f"{run_dir}: {label} must be an object with reference and sha256")
        return

    reference = meta.get("reference")
    expected_hash = meta.get("sha256")
    if not isinstance(reference, str) or not reference:
        errors.append(f"{run_dir}: {label} missing reference")
        return
    if not isinstance(expected_hash, str) or not expected_hash:
        errors.append(f"{run_dir}: {label} missing sha256")
        return

    reference_path = Path(reference)
    if reference_path.is_absolute() or ".." in reference_path.parts:
        errors.append(f"{run_dir}: {label} reference must stay inside the run container")
        return

    artifact_path = run_dir / reference_path
    if not artifact_path.exists():
        errors.append(f"{run_dir}: {label} missing at {reference}")
        return

    actual_hash = file_hash(artifact_path)
    if actual_hash != expected_hash:
        errors.append(f"{run_dir}: {label} hash mismatch")


def _validate_execution_context(run_dir: Path, bundle_name: str, bundle: dict[str, Any], errors: list[str]) -> None:
    context = bundle.get("execution_context")
    if not isinstance(context, dict):
        errors.append(f"{run_dir}: {bundle_name} missing execution_context")
        return
    for field in _missing_fields(context, REQUIRED_EXECUTION_CONTEXT_FIELDS):
        errors.append(f"{run_dir}: {bundle_name} execution_context missing {field}")


def _validate_input_extraction(run_dir: Path, bundle_name: str, bundle: dict[str, Any], errors: list[str]) -> None:
    extraction = bundle.get("input_extraction")
    if not isinstance(extraction, dict):
        errors.append(f"{run_dir}: {bundle_name} missing input_extraction")
        return
    for field in _missing_fields(extraction, REQUIRED_INPUT_EXTRACTION_FIELDS):
        errors.append(f"{run_dir}: {bundle_name} input_extraction missing {field}")

    canonical_fields = extraction.get("canonical_fields")
    if not isinstance(canonical_fields, dict):
        errors.append(f"{run_dir}: {bundle_name} input_extraction.canonical_fields must be an object")
        return
    for field in _missing_fields(canonical_fields, REQUIRED_CANONICAL_FIELDS):
        errors.append(f"{run_dir}: {bundle_name} input_extraction.canonical_fields missing {field}")

    if not isinstance(extraction.get("missing_fields", []), list):
        errors.append(f"{run_dir}: {bundle_name} input_extraction.missing_fields must be a list")


def _validate_common_bundle_fields(run_dir: Path, bundle_name: str, bundle: Any, errors: list[str]) -> None:
    if not isinstance(bundle, dict):
        errors.append(f"{run_dir}: {bundle_name} must be a JSON object")
        return
    for field in ["execution_id", "trace_id", "contract_version", "schema_version", "timestamp"]:
        if field not in bundle:
            errors.append(f"{run_dir}: {bundle_name} missing {field}")
    if bundle.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"{run_dir}: {bundle_name} contract_version mismatch")
    if bundle.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{run_dir}: {bundle_name} schema_version mismatch")
    _validate_execution_context(run_dir, bundle_name, bundle, errors)
    _validate_input_extraction(run_dir, bundle_name, bundle, errors)


def _validate_evidence_bundle(run_dir: Path, evidence: Any, errors: list[str]) -> None:
    if not isinstance(evidence, dict):
        errors.append(f"{run_dir}: evidence_bundle.json must be a JSON object")
        return

    for field in REQUIRED_EVIDENCE_FIELDS:
        if field not in evidence:
            errors.append(f"{run_dir}: evidence_bundle.json missing {field}")

    _validate_reference_hash(run_dir, evidence.get("payload_reference"), "evidence_bundle.json payload_reference", errors)

    consumer_compatibility = evidence.get("consumer_compatibility")
    if not isinstance(consumer_compatibility, dict):
        errors.append(f"{run_dir}: evidence_bundle.json missing consumer_compatibility")
    elif consumer_compatibility.get("self_contained") is not True:
        errors.append(f"{run_dir}: evidence_bundle.json consumer_compatibility.self_contained must be true")

    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append(f"{run_dir}: evidence_bundle.json artifacts must be an object")
        return
    for artifact_name in REQUIRED_ARTIFACT_KEYS:
        if artifact_name not in artifacts:
            errors.append(f"{run_dir}: evidence_bundle.json artifacts missing {artifact_name}")
    for artifact_name, meta in artifacts.items():
        _validate_reference_hash(run_dir, meta, f"evidence_bundle.json artifacts.{artifact_name}", errors)


def _validate_deterministic_evidence_identifiers(run_dir: Path, evidence: Any, errors: list[str]) -> None:
    if not isinstance(evidence, dict):
        return
    input_path = run_dir / "input.json"
    output_path = run_dir / "output.json"
    if not input_path.exists() or not output_path.exists():
        return

    try:
        raw_payload = read_json(input_path)
        output = read_json(output_path)
    except json.JSONDecodeError as exc:
        errors.append(f"{run_dir}: cannot recompute deterministic identifiers because JSON is invalid: {exc.msg}")
        return

    payload = normalize_input(raw_payload)
    payload_hash = sha256_hex(payload)
    output_hash = sha256_hex(output)
    expected_execution_id = stable_id("exec", CONTRACT_VERSION, SCHEMA_VERSION, payload_hash)
    expected_values = {
        "execution_id": expected_execution_id,
        "trace_id": stable_id("trace", payload.get("case_id", "unknown"), payload_hash),
        "artifact_reference": run_dir.name,
        "replay_reference": stable_id("replay", expected_execution_id, output_hash),
    }

    for field, expected in expected_values.items():
        if evidence.get(field) != expected:
            errors.append(f"{run_dir}: evidence_bundle.json {field} is not deterministic; expected {expected}")


def _validate_lineage_bundle(run_dir: Path, lineage: Any, errors: list[str]) -> None:
    if not isinstance(lineage, dict):
        errors.append(f"{run_dir}: lineage_bundle.json must be a JSON object")
        return

    nodes = lineage.get("nodes")
    if not isinstance(nodes, list):
        errors.append(f"{run_dir}: lineage_bundle.json nodes must be a list")
    else:
        node_ids = {node.get("id") for node in nodes if isinstance(node, dict)}
        for expected_node in sorted(EXPECTED_LINEAGE_NODES - node_ids):
            errors.append(f"{run_dir}: lineage_bundle.json missing node {expected_node}")
        for node in nodes:
            if isinstance(node, dict) and "reference" in node:
                _validate_reference_hash(run_dir, node, f"lineage_bundle.json node {node.get('id', '<unknown>')}", errors)

    edges = lineage.get("edges")
    if not isinstance(edges, list):
        errors.append(f"{run_dir}: lineage_bundle.json edges must be a list")
    else:
        edge_set = {
            (edge.get("from"), edge.get("to"), edge.get("relationship"))
            for edge in edges
            if isinstance(edge, dict)
        }
        for expected_edge in sorted(EXPECTED_LINEAGE_EDGES - edge_set):
            errors.append(f"{run_dir}: lineage_bundle.json missing edge {expected_edge}")

    provenance_chain = lineage.get("provenance_chain")
    if not isinstance(provenance_chain, list) or not provenance_chain:
        errors.append(f"{run_dir}: lineage_bundle.json provenance_chain must be a non-empty list")
    else:
        actions = [step.get("action") for step in provenance_chain if isinstance(step, dict)]
        if actions[: len(EXPECTED_PROVENANCE_ACTIONS)] != EXPECTED_PROVENANCE_ACTIONS:
            errors.append(f"{run_dir}: lineage_bundle.json provenance_chain does not contain the expected ordered actions")


def _validate_replay_bundle(run_dir: Path, replay: Any, errors: list[str]) -> None:
    if not isinstance(replay, dict):
        errors.append(f"{run_dir}: replay_bundle.json must be a JSON object")
        return

    if not isinstance(replay.get("replay_command"), str) or "operational_drift_monitor.py run" not in replay["replay_command"]:
        errors.append(f"{run_dir}: replay_bundle.json replay_command must run operational_drift_monitor.py")

    replay_inputs = replay.get("replay_inputs")
    if not isinstance(replay_inputs, list) or not replay_inputs:
        errors.append(f"{run_dir}: replay_bundle.json replay_inputs must be a non-empty list")
    elif not isinstance(replay_inputs[0], dict):
        errors.append(f"{run_dir}: replay_bundle.json replay_inputs[0] must be an object")
    else:
        if replay_inputs[0].get("reference") != "input.json":
            errors.append(f"{run_dir}: replay_bundle.json replay_inputs[0] must reference input.json")
        _validate_reference_hash(run_dir, replay_inputs[0], "replay_bundle.json replay_inputs[0]", errors)

    expected_outputs = replay.get("expected_outputs")
    if not isinstance(expected_outputs, list) or not expected_outputs:
        errors.append(f"{run_dir}: replay_bundle.json expected_outputs must be a non-empty list")
    elif not isinstance(expected_outputs[0], dict):
        errors.append(f"{run_dir}: replay_bundle.json expected_outputs[0] must be an object")
    else:
        if expected_outputs[0].get("reference") != "output.json":
            errors.append(f"{run_dir}: replay_bundle.json expected_outputs[0] must reference output.json")
        _validate_reference_hash(run_dir, expected_outputs[0], "replay_bundle.json expected_outputs[0]", errors)

    determinism = replay.get("determinism")
    if not isinstance(determinism, dict) or determinism.get("random_generation") != "not_used":
        errors.append(f"{run_dir}: replay_bundle.json determinism.random_generation must be not_used")

    runtime_requirements = replay.get("runtime_requirements")
    if not isinstance(runtime_requirements, dict) or runtime_requirements.get("entrypoint") != "operational_drift_monitor.py":
        errors.append(f"{run_dir}: replay_bundle.json runtime_requirements.entrypoint mismatch")


def _validate_handover_bundle(run_dir: Path, handover: Any, errors: list[str]) -> None:
    if not isinstance(handover, dict):
        errors.append(f"{run_dir}: handover_bundle.json must be a JSON object")
        return

    bundle_index = handover.get("bundle_index")
    expected_index = {
        "evidence": "evidence_bundle.json",
        "lineage": "lineage_bundle.json",
        "replay": "replay_bundle.json",
        "input": "input.json",
        "output": "output.json",
        "log": "execution.log",
    }
    if not isinstance(bundle_index, dict):
        errors.append(f"{run_dir}: handover_bundle.json bundle_index must be an object")
    else:
        for key, expected_file in expected_index.items():
            if bundle_index.get(key) != expected_file:
                errors.append(f"{run_dir}: handover_bundle.json bundle_index.{key} must be {expected_file}")

    if not isinstance(handover.get("consumer_instructions"), list) or not handover["consumer_instructions"]:
        errors.append(f"{run_dir}: handover_bundle.json consumer_instructions must be a non-empty list")
    if "integration_readiness" not in handover:
        errors.append(f"{run_dir}: handover_bundle.json missing integration_readiness")


def _validate_trace_propagation(run_dir: Path, bundles: dict[str, Any], errors: list[str]) -> None:
    evidence = bundles.get("evidence_bundle.json")
    if not isinstance(evidence, dict):
        return
    for bundle_name, bundle in bundles.items():
        if not isinstance(bundle, dict):
            continue
        for field in PROPAGATED_TRACE_FIELDS:
            if bundle.get(field) != evidence.get(field):
                errors.append(f"{run_dir}: {bundle_name} {field} does not match evidence_bundle.json")


def _parse_execution_log(log_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in log_text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _validate_execution_log(run_dir: Path, evidence: Any, errors: list[str]) -> None:
    log_path = run_dir / "execution.log"
    if not log_path.exists():
        return
    log_values = _parse_execution_log(log_path.read_text(encoding="utf-8"))
    for key in REQUIRED_LOG_KEYS:
        if key not in log_values:
            errors.append(f"{run_dir}: execution.log missing {key}")

    if not isinstance(evidence, dict):
        return
    expected_values = {
        "timestamp": evidence.get("timestamp"),
        "execution_id": evidence.get("execution_id"),
        "trace_id": evidence.get("trace_id"),
        "input_sha256": file_hash(run_dir / "input.json") if (run_dir / "input.json").exists() else None,
        "output_sha256": file_hash(run_dir / "output.json") if (run_dir / "output.json").exists() else None,
        "status": evidence.get("execution_status"),
    }
    for key, expected in expected_values.items():
        if expected is not None and log_values.get(key) != expected:
            errors.append(f"{run_dir}: execution.log {key} does not match generated artifact evidence")


def validate_run_dir(run_dir: Path) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_FILES:
        if not (run_dir / name).exists():
            errors.append(f"{run_dir}: missing {name}")

    bundles: dict[str, Any] = {}
    for name in REQUIRED_BUNDLE_FILES:
        bundle = _load_json_for_validation(run_dir, name, errors)
        if bundle is not None:
            bundles[name] = bundle
            _validate_common_bundle_fields(run_dir, name, bundle, errors)

    _validate_trace_propagation(run_dir, bundles, errors)

    evidence = bundles.get("evidence_bundle.json")
    if evidence is not None:
        _validate_evidence_bundle(run_dir, evidence, errors)
        _validate_deterministic_evidence_identifiers(run_dir, evidence, errors)
        _validate_execution_log(run_dir, evidence, errors)

    lineage = bundles.get("lineage_bundle.json")
    if lineage is not None:
        _validate_lineage_bundle(run_dir, lineage, errors)

    replay = bundles.get("replay_bundle.json")
    if replay is not None:
        _validate_replay_bundle(run_dir, replay, errors)

    handover = bundles.get("handover_bundle.json")
    if handover is not None:
        _validate_handover_bundle(run_dir, handover, errors)

    return errors


def validate_evidence_root(output_root: Path) -> tuple[int, list[str]]:
    if not output_root.exists():
        return 0, [f"{output_root} does not exist"]
    run_dirs = [path for path in output_root.iterdir() if path.is_dir()]
    errors: list[str] = []
    for run_dir in run_dirs:
        errors.extend(validate_run_dir(run_dir))
    return len(run_dirs), errors
