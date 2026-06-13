"""Run the complete SHAKTI evidence to TANTRA integration chain."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from lineage_registration import register_lineage
from runtime_evidence.canonical import canonical_json, stable_id
from runtime_evidence.producer import file_hash, produce_evidence_run, read_json, write_json
from shakti_consumer_adapter import consume_evidence
from tms_convergence_emitter import emit_convergence


def _write_markdown(path: Path, title: str, sections: list[tuple[str, str]]) -> None:
    lines = [f"# {title}", ""]
    for heading, body in sections:
        lines.extend([f"## {heading}", "", body.strip(), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _json_block(value: Any) -> str:
    return "```json\n" + canonical_json(value) + "\n```"


def _proof_paths(output_root: Path) -> dict[str, Path]:
    return {
        "shakti": output_root / "SHAKTI_CONSUMPTION_PROOF.md",
        "governance": output_root / "GOVERNANCE_REGISTRATION_PROOF.md",
        "tms": output_root / "TMS_CONVERGENCE_PROOF.md",
        "tantra": output_root / "TANTRA_CHAIN_PROOF.md",
        "ansh": output_root / "ANSH_INTEGRATION_PROOF.md",
    }


def write_proofs(output_root: Path, chain_summary: dict[str, Any]) -> dict[str, Path]:
    paths = _proof_paths(output_root)
    validation = read_json(output_root / "validation_decision.json")
    governance = read_json(output_root / "governance_record.json")
    registration = read_json(output_root / "registration_reference.json")
    lineage_registration = read_json(output_root / "lineage_registration.json")
    lineage_chain = read_json(output_root / "lineage_chain.json")
    convergence = read_json(output_root / "tms_convergence_status.json")
    if chain_summary.get("input_mode") == "generated_sample_evidence":
        tantra_flow = "`Input Payload -> Evidence Generation -> SHAKTI Validation -> MDU Registration -> TMS Convergence`"
        input_mode = {
            "input_mode": chain_summary.get("input_mode"),
            "sample_input": chain_summary.get("sample_input"),
            "source_evidence": chain_summary.get("source_evidence"),
        }
    else:
        tantra_flow = "`Existing Evidence Package -> SHAKTI Validation -> MDU Registration -> TMS Convergence`"
        input_mode = {
            "input_mode": chain_summary.get("input_mode"),
            "source_evidence": chain_summary.get("source_evidence"),
        }

    _write_markdown(
        paths["shakti"],
        "SHAKTI Consumption Proof",
        [
            ("Flow", "`evidence_bundle.json -> SHAKTI Consumer Adapter -> validation_decision.json`"),
            ("Consumer Responsibility", "The adapter treats evidence generation as upstream. It consumes the existing bundle, verifies required schema fields, validates contract and schema versions, recomputes artifact hashes, checks replay metadata, and emits a deterministic governance decision."),
            ("Validation Decision", _json_block({"decision": validation["decision"], "decision_id": validation["decision_id"], "reason_codes": validation["reason_codes"], "trace_id": validation["trace_id"]})),
            ("Checks", f"{len(validation['validation_checks'])} deterministic checks were executed. Failed checks: {len(validation['reason_codes'])}."),
            ("Failure Surface", "Unsupported contract versions, missing canonical evidence fields, artifact hash mismatches, failed execution status, low confidence, non-self-contained bundles, and incomplete replay metadata produce `REJECTED`."),
        ],
    )
    _write_markdown(
        paths["governance"],
        "Governance Registration Proof",
        [
            ("Flow", "`Evidence -> Governance Record -> Registration`"),
            ("Governance Record", _json_block({"governance_record_id": governance["governance_record_id"], "decision": governance["decision"], "trace_id": governance["trace_id"]})),
            ("Registration Reference", _json_block({"registration_id": registration["registration_id"], "registration_status": registration["registration_status"], "trace_id": registration["trace_id"]})),
        ],
    )
    _write_markdown(
        paths["tms"],
        "TMS Convergence Proof",
        [
            ("Flow", "`Governance Decision -> Convergence Status`"),
            ("Convergence", _json_block({"convergence_id": convergence["convergence_id"], "status": convergence["status"], "reason_codes": convergence["reason_codes"], "trace_id": convergence["trace_id"]})),
            ("Supported Statuses", "`CONVERGED`, `PARTIAL`, `FAILED`"),
            ("Status Policy", "`CONVERGED` means SHAKTI approved the evidence, MDU registration completed, and lineage reconstruction is available. `PARTIAL` means SHAKTI approved the evidence but MDU registration or reconstruction is incomplete. `FAILED` means SHAKTI did not approve validation."),
        ],
    )
    _write_markdown(
        paths["tantra"],
        "TANTRA Chain Proof",
        [
            ("Operational Chain", tantra_flow),
            ("Input Mode", _json_block(input_mode)),
            ("One Trace", _json_block({"trace_id": chain_summary["trace_id"], "execution_id": chain_summary["execution_id"], "chain_id": chain_summary["chain_id"]})),
            ("Replay Reconstruction", f"Replay metadata remains available through `{chain_summary['evidence_run']}/replay_bundle.json`."),
            ("Lineage Reconstruction", "Use `lineage_chain.json.chain_steps` to reconstruct `input_artifact -> evidence_bundle -> governance_record -> consumer_registration -> mdu_registration`."),
        ],
    )
    _write_markdown(
        paths["ansh"],
        "Ansh Integration Proof",
        [
            ("SHAKTI Contract", "The adapter validates the repository's available Ansh-facing SHAKTI contract: `shakti-runtime-evidence/v1` with schema `1.0.0`. The contract constants live in `runtime_evidence/canonical.py`; the canonical evidence schema lives in `schemas/canonical_evidence_schema.json`."),
            ("Phase 6 Execution", _json_block({"input_mode": chain_summary.get("input_mode"), "sample_input": chain_summary.get("sample_input"), "source_evidence": chain_summary.get("source_evidence"), "validation_decision": chain_summary["outputs"]["validation_decision"], "lineage_registration": chain_summary["outputs"]["lineage_registration"], "tms_convergence_status": chain_summary["outputs"]["tms_convergence_status"]})),
            ("SHAKTI Validation", _json_block({"decision": validation["decision"], "decision_id": validation["decision_id"], "governance_status": validation["governance_status"], "reason_codes": validation["reason_codes"], "trace_id": validation["trace_id"]})),
            ("MDU And TMS Result", _json_block({"mdu_registration": lineage_registration["registration_status"], "mdu_registration_id": lineage_registration["mdu_registration_id"], "tms_status": convergence["status"], "tms_reason_codes": convergence["reason_codes"], "trace_id": validation["trace_id"]})),
            ("Integration Boundary", "No separate Ansh SHAKTI runtime or remote API is present in this repository. The integration seam is `shakti_consumer_adapter.consume_evidence(...)`; when Ansh provides a concrete contract module or endpoint, this adapter should call that interface without changing the evidence format."),
            ("End-To-End Result", _json_block({"decision": validation["decision"], "mdu_registration": lineage_registration["registration_status"], "tms_status": convergence["status"], "trace_id": validation["trace_id"]})),
            ("Reconstruction", f"Lineage is reconstructable: `{lineage_chain['reconstruction']['reconstructable']}`."),
        ],
    )
    return paths


def run_operational_chain(
    evidence_path: Path,
    output_root: Path,
    input_mode: str = "existing_evidence_package",
    sample_input: Path | None = None,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = evidence_path.parent

    shakti_outputs = consume_evidence(evidence_path, output_root)
    mdu_outputs = register_lineage(
        evidence_path,
        shakti_outputs["governance_record"],
        shakti_outputs["registration_reference"],
        output_root,
    )
    convergence_path = emit_convergence(
        shakti_outputs["validation_decision"],
        mdu_outputs["lineage_registration"],
        mdu_outputs["lineage_chain"],
        output_root,
    )

    evidence = read_json(evidence_path)
    validation = read_json(shakti_outputs["validation_decision"])
    lineage_chain = read_json(mdu_outputs["lineage_chain"])
    convergence = read_json(convergence_path)
    chain_summary = {
        "chain_id": stable_id("tantra_chain", evidence.get("execution_id"), validation.get("decision_id"), lineage_chain.get("chain_id"), convergence.get("convergence_id")),
        "convergence_status": convergence.get("status"),
        "decision": validation.get("decision"),
        "deterministic": True,
        "evidence_run": run_dir.as_posix(),
        "input_mode": input_mode,
        "execution_id": evidence.get("execution_id"),
        "outputs": {
            "governance_record": shakti_outputs["governance_record"].as_posix(),
            "lineage_chain": mdu_outputs["lineage_chain"].as_posix(),
            "lineage_registration": mdu_outputs["lineage_registration"].as_posix(),
            "registration_reference": shakti_outputs["registration_reference"].as_posix(),
            "tms_convergence_status": convergence_path.as_posix(),
            "validation_decision": shakti_outputs["validation_decision"].as_posix(),
        },
        "source_evidence": evidence_path.as_posix(),
        "trace_id": evidence.get("trace_id"),
    }
    if sample_input is not None:
        chain_summary["sample_input"] = sample_input.as_posix()
    write_json(output_root / "tantra_chain_result.json", chain_summary)
    proof_paths = write_proofs(output_root, chain_summary)
    chain_summary["proofs"] = {key: path.as_posix() for key, path in proof_paths.items()}
    write_json(output_root / "tantra_chain_result.json", chain_summary)
    return chain_summary


def run_chain(input_path: Path, evidence_root: Path, output_root: Path) -> dict[str, Any]:
    run_dir = produce_evidence_run(input_path, evidence_root)
    return run_operational_chain(
        run_dir / "evidence_bundle.json",
        output_root,
        input_mode="generated_sample_evidence",
        sample_input=input_path,
    )


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run one end-to-end TANTRA integration chain.")
    parser.add_argument("--evidence", type=Path, help="Existing evidence_bundle.json to consume through TANTRA.")
    parser.add_argument("--input", type=Path, help="Optional sample input. Uses the existing evidence producer before TANTRA consumption.")
    parser.add_argument("--evidence-out", default=Path("outputs/evidence_runs"), type=Path, help="Evidence package output root.")
    parser.add_argument("--out", default=Path("."), type=Path, help="TANTRA output directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.evidence is not None:
        summary = run_operational_chain(args.evidence, args.out)
    else:
        sample_input = args.input or Path("sample_inputs/runtime-proof-010.json")
        summary = run_chain(sample_input, args.evidence_out, args.out)
    print(canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
