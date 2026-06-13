"""MDU lineage registration for validated TANTRA evidence."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from runtime_evidence.canonical import sha256_hex, stable_id
from runtime_evidence.producer import file_hash, read_json, write_json

REGISTRAR_NAME = "mdu-lineage-registration"
REGISTRAR_VERSION = "1.0.0"


def _artifact(reference: Path, artifact_type: str, role: str) -> dict[str, str]:
    return {
        "reference": reference.as_posix(),
        "role": role,
        "sha256": file_hash(reference),
        "type": artifact_type,
    }


def register_lineage(evidence_path: Path, governance_record_path: Path, registration_reference_path: Path, output_root: Path) -> dict[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    evidence = read_json(evidence_path)
    governance_record = read_json(governance_record_path)
    registration_reference = read_json(registration_reference_path)
    evidence_dir = evidence_path.parent
    input_path = evidence_dir / evidence["payload_reference"]["reference"]

    artifacts = [
        _artifact(input_path, "input_artifact", "raw_runtime_input"),
        _artifact(evidence_path, "evidence_bundle", "validated_evidence"),
        _artifact(governance_record_path, "governance_record", "shakti_validation_record"),
        _artifact(registration_reference_path, "consumer_registration", "shakti_registration_reference"),
    ]
    registration_material = {
        "artifacts": artifacts,
        "governance_record_id": governance_record.get("governance_record_id"),
        "trace_id": evidence.get("trace_id"),
    }
    lineage_registration = {
        "deterministic": True,
        "execution_id": evidence.get("execution_id"),
        "governance_record_id": governance_record.get("governance_record_id"),
        "mdu_registration_id": stable_id("mdu_registration", registration_material),
        "query_keys": {
            "execution_id": evidence.get("execution_id"),
            "governance_record_id": governance_record.get("governance_record_id"),
            "registration_id": registration_reference.get("registration_id"),
            "trace_id": evidence.get("trace_id"),
        },
        "registered_artifacts": artifacts,
        "registrar": {
            "name": REGISTRAR_NAME,
            "version": REGISTRAR_VERSION,
        },
        "registration_status": "REGISTERED" if registration_reference.get("registration_status") == "REGISTERED" else "REJECTED",
        "trace_id": evidence.get("trace_id"),
    }

    chain_steps = [
        {
            "step": 1,
            "from": "input_artifact",
            "to": "evidence_bundle",
            "relationship": "generated_evidence_package",
        },
        {
            "step": 2,
            "from": "evidence_bundle",
            "to": "governance_record",
            "relationship": "validated_by_shakti",
        },
        {
            "step": 3,
            "from": "governance_record",
            "to": "consumer_registration",
            "relationship": "registered_for_consumption",
        },
        {
            "step": 4,
            "from": "consumer_registration",
            "to": "mdu_registration",
            "relationship": "registered_in_mdu",
        },
    ]
    lineage_chain = {
        "chain_id": stable_id("lineage_chain", lineage_registration["mdu_registration_id"], chain_steps),
        "chain_steps": chain_steps,
        "deterministic": True,
        "execution_id": evidence.get("execution_id"),
        "reconstruction": {
            "artifact_count": len(artifacts),
            "ordered_steps": [step["relationship"] for step in chain_steps],
            "reconstructable": all(Path(artifact["reference"]).exists() for artifact in artifacts),
        },
        "trace_id": evidence.get("trace_id"),
    }

    registration_path = output_root / "lineage_registration.json"
    chain_path = output_root / "lineage_chain.json"
    write_json(registration_path, lineage_registration)
    write_json(chain_path, lineage_chain)
    return {
        "lineage_registration": registration_path,
        "lineage_chain": chain_path,
    }


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Register validated evidence lineage with the MDU layer.")
    parser.add_argument("--evidence", required=True, type=Path, help="Path to evidence_bundle.json")
    parser.add_argument("--governance-record", default=Path("governance_record.json"), type=Path)
    parser.add_argument("--registration-reference", default=Path("registration_reference.json"), type=Path)
    parser.add_argument("--out", default=Path("."), type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = register_lineage(args.evidence, args.governance_record, args.registration_reference, args.out)
    print({key: path.as_posix() for key, path in paths.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
