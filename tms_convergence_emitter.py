"""TMS convergence emission for TANTRA governance decisions."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from runtime_evidence.canonical import stable_id
from runtime_evidence.producer import file_hash, read_json, write_json

EMITTER_NAME = "tms-convergence-emitter"
EMITTER_VERSION = "1.0.0"
VALID_STATUSES = {"CONVERGED", "PARTIAL", "FAILED"}


def _derive_status(validation_decision: dict, lineage_registration: dict, lineage_chain: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if validation_decision.get("decision") != "APPROVED":
        reasons.append("SHAKTI_VALIDATION_NOT_APPROVED")
    if lineage_registration.get("registration_status") != "REGISTERED":
        reasons.append("MDU_REGISTRATION_NOT_REGISTERED")
    if lineage_chain.get("reconstruction", {}).get("reconstructable") is not True:
        reasons.append("LINEAGE_NOT_RECONSTRUCTABLE")

    if not reasons:
        return "CONVERGED", []
    if validation_decision.get("decision") == "APPROVED":
        return "PARTIAL", reasons
    return "FAILED", reasons


def emit_convergence(validation_decision_path: Path, lineage_registration_path: Path, lineage_chain_path: Path, output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    validation_decision = read_json(validation_decision_path)
    lineage_registration = read_json(lineage_registration_path)
    lineage_chain = read_json(lineage_chain_path)
    status, reasons = _derive_status(validation_decision, lineage_registration, lineage_chain)
    status_record = {
        "convergence_id": stable_id(
            "tms_convergence",
            validation_decision.get("decision_id"),
            lineage_registration.get("mdu_registration_id"),
            lineage_chain.get("chain_id"),
            status,
        ),
        "deterministic": True,
        "emitter": {
            "name": EMITTER_NAME,
            "version": EMITTER_VERSION,
        },
        "execution_id": validation_decision.get("execution_id"),
        "inputs": {
            "lineage_chain": {
                "reference": lineage_chain_path.as_posix(),
                "sha256": file_hash(lineage_chain_path),
            },
            "lineage_registration": {
                "reference": lineage_registration_path.as_posix(),
                "sha256": file_hash(lineage_registration_path),
            },
            "validation_decision": {
                "reference": validation_decision_path.as_posix(),
                "sha256": file_hash(validation_decision_path),
            },
        },
        "reason_codes": reasons,
        "status": status,
        "trace_id": validation_decision.get("trace_id"),
        "valid_statuses": sorted(VALID_STATUSES),
    }
    output_path = output_root / "tms_convergence_status.json"
    write_json(output_path, status_record)
    return output_path


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Emit TMS convergence status from SHAKTI and MDU outputs.")
    parser.add_argument("--validation-decision", default=Path("validation_decision.json"), type=Path)
    parser.add_argument("--lineage-registration", default=Path("lineage_registration.json"), type=Path)
    parser.add_argument("--lineage-chain", default=Path("lineage_chain.json"), type=Path)
    parser.add_argument("--out", default=Path("."), type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = emit_convergence(args.validation_decision, args.lineage_registration, args.lineage_chain, args.out)
    print({"tms_convergence_status": output_path.as_posix()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
