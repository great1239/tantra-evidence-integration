from pathlib import Path
import json
import tempfile
import unittest

from runtime_evidence.canonical import stable_id
from runtime_evidence.producer import produce_evidence_run, validate_evidence_root, write_json
from runtime_evidence.reference_runtime import demo_payloads
from runtime_evidence.normalizer import normalize_input
from run_tantra_chain import run_chain, run_operational_chain
from shakti_consumer_adapter import consume_evidence
from tms_convergence_emitter import emit_convergence


class RuntimeEvidenceTests(unittest.TestCase):
    def test_stable_id_is_deterministic(self):
        first = stable_id("exec", {"b": 2, "a": 1})
        second = stable_id("exec", {"a": 1, "b": 2})
        self.assertEqual(first, second)

    def test_canonical_evidence_schema_requires_assignment_fields(self):
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "canonical_evidence_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["required"],
            [
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
            ],
        )

    def test_produce_and_validate_one_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.json"
            write_json(input_path, demo_payloads(1)[0])
            produce_evidence_run(input_path, root / "runs")
            run_count, errors = validate_evidence_root(root / "runs")
            self.assertEqual(run_count, 1)
            self.assertEqual(errors, [])

    def test_normalizes_top_level_aliases(self):
        raw = {
            "id": "loose-001",
            "from": "SOURCE_A",
            "to": "TARGET_B",
            "action": "lineage_capture",
            "data": {"signals": []},
        }
        normalized = normalize_input(raw)
        self.assertEqual(normalized["case_id"], "loose-001")
        self.assertEqual(normalized["source_system"], "SOURCE_A")
        self.assertEqual(normalized["target_system"], "TARGET_B")
        self.assertEqual(normalized["operation"], "lineage_capture")
        self.assertEqual(normalized["payload"], {"signals": []})
        self.assertEqual(normalized["_normalization"]["missing_fields"], [])

    def test_normalizes_nested_aliases(self):
        raw = {
            "metadata": {
                "caseId": "nested-001",
                "sourceSystem": "SOURCE_NESTED",
                "targetSystem": "TARGET_NESTED",
            },
            "event": {
                "type": "replay_reference_capture",
                "body": {"signals": [{"severity": "info", "name": "nested"}]},
            },
        }
        normalized = normalize_input(raw)
        self.assertEqual(normalized["case_id"], "nested-001")
        self.assertEqual(normalized["source_system"], "SOURCE_NESTED")
        self.assertEqual(normalized["target_system"], "TARGET_NESTED")
        self.assertEqual(normalized["operation"], "replay_reference_capture")
        self.assertEqual(normalized["payload"], {"signals": [{"severity": "info", "name": "nested"}]})
        self.assertEqual(normalized["_normalization"]["missing_fields"], [])

    def test_missing_fields_only_when_unextractable(self):
        raw = {"data": {"signals": []}}
        normalized = normalize_input(raw)
        self.assertEqual(normalized["payload"], {"signals": []})
        self.assertEqual(
            normalized["_normalization"]["missing_fields"],
            ["case_id", "source_system", "target_system", "operation"],
        )

    def test_extracts_canonical_fields_from_plain_english_string(self):
        raw = (
            "Run runtime-proof-011 from GC_RUNTIME_EVIDENCE_PRODUCER "
            "to SHAKTI_GOVERNANCE_CONSUMER for artifact_generation with payload signals complete."
        )
        normalized = normalize_input(raw)
        self.assertEqual(normalized["case_id"], "runtime-proof-011")
        self.assertEqual(normalized["source_system"], "GC_RUNTIME_EVIDENCE_PRODUCER")
        self.assertEqual(normalized["target_system"], "SHAKTI_GOVERNANCE_CONSUMER")
        self.assertEqual(normalized["operation"], "artifact_generation")
        self.assertEqual(normalized["payload"], raw)
        self.assertEqual(normalized["_normalization"]["missing_fields"], [])

    def test_raw_text_file_with_plain_english_data_produces_successful_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "plain-request.txt"
            input_path.write_text(
                "Please process case id runtime-proof-012. "
                "source system GC_RUNTIME_EVIDENCE_PRODUCER. "
                "target system SHAKTI_GOVERNANCE_CONSUMER. "
                "operation lineage capture.",
                encoding="utf-8",
            )
            run_dir = produce_evidence_run(input_path, root / "runs")
            output = json.loads((run_dir / "output.json").read_text(encoding="utf-8"))
            evidence = json.loads((run_dir / "evidence_bundle.json").read_text(encoding="utf-8"))
            raw_input = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
            self.assertEqual(output["execution_status"], "success")
            self.assertEqual(output["missing_required_fields"], [])
            self.assertEqual(evidence["input_extraction"]["canonical_fields"]["case_id"], "runtime-proof-012")
            self.assertEqual(evidence["input_extraction"]["missing_fields"], [])
            self.assertIsInstance(raw_input, str)

    def test_produce_run_from_loose_schema_succeeds_when_extractable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "loose.json"
            write_json(
                input_path,
                {
                    "requestId": "loose-run-001",
                    "origin": "LOOSE_SOURCE",
                    "recipient": "LOOSE_TARGET",
                    "command": "artifact_generation",
                    "body": {"signals": []},
                },
            )
            run_dir = produce_evidence_run(input_path, root / "runs")
            output = __import__("json").loads((run_dir / "output.json").read_text(encoding="utf-8"))
            raw_input = __import__("json").loads((run_dir / "input.json").read_text(encoding="utf-8"))
            evidence = __import__("json").loads((run_dir / "evidence_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(output["execution_status"], "success")
            self.assertEqual(output["missing_required_fields"], [])
            self.assertEqual(raw_input["requestId"], "loose-run-001")
            self.assertEqual(evidence["input_extraction"]["canonical_fields"]["case_id"], "loose-run-001")
            self.assertEqual(evidence["input_extraction"]["missing_fields"], [])

    def test_non_dict_signals_do_not_crash_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "bad-signals.json"
            write_json(
                input_path,
                {
                    "case_id": "bad-signals-001",
                    "source_system": "SOURCE",
                    "target_system": "TARGET",
                    "operation": "artifact_generation",
                    "payload": {"signals": ["not-a-dict", {"severity": "warning", "name": "valid"}]},
                },
            )
            run_dir = produce_evidence_run(input_path, root / "runs")
            output = __import__("json").loads((run_dir / "output.json").read_text(encoding="utf-8"))
            self.assertEqual(output["execution_status"], "success")
            self.assertEqual(output["signal_count"], 1)
            self.assertEqual(output["ignored_signal_count"], 1)

    def test_scalar_json_produces_failed_evidence_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "scalar.json"
            write_json(input_path, "raw text payload")
            run_dir = produce_evidence_run(input_path, root / "runs")
            output = __import__("json").loads((run_dir / "output.json").read_text(encoding="utf-8"))
            evidence = __import__("json").loads((run_dir / "evidence_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(output["execution_status"], "failed")
            self.assertEqual(
                output["missing_required_fields"],
                ["case_id", "source_system", "target_system", "operation"],
            )
            self.assertEqual(evidence["input_extraction"]["canonical_fields"]["payload_type"], "str")

    def test_demo_payloads_are_mangled_but_extractable(self):
        for payload in demo_payloads(10):
            normalized = normalize_input(payload)
            self.assertEqual(normalized["_normalization"]["missing_fields"], [])
            self.assertIn("_normalization", normalized)

    def test_all_required_bundles_include_input_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "loose.json"
            write_json(input_path, demo_payloads(1)[0])
            run_dir = produce_evidence_run(input_path, root / "runs")
            for name in ["evidence_bundle.json", "lineage_bundle.json", "replay_bundle.json", "handover_bundle.json"]:
                bundle = __import__("json").loads((run_dir / name).read_text(encoding="utf-8"))
                self.assertEqual(bundle["input_extraction"]["input_shape"], "noncanonical_extracted")
                self.assertEqual(bundle["input_extraction"]["missing_fields"], [])

    def test_validator_checks_replay_and_lineage_reconstruction_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "loose.json"
            write_json(input_path, demo_payloads(1)[0])
            run_dir = produce_evidence_run(input_path, root / "runs")

            lineage = json.loads((run_dir / "lineage_bundle.json").read_text(encoding="utf-8"))
            lineage["edges"] = []
            write_json(run_dir / "lineage_bundle.json", lineage)

            replay = json.loads((run_dir / "replay_bundle.json").read_text(encoding="utf-8"))
            replay["expected_outputs"][0]["reference"] = "missing-output.json"
            write_json(run_dir / "replay_bundle.json", replay)

            _, errors = validate_evidence_root(root / "runs")
            self.assertTrue(any("lineage_bundle.json missing edge" in error for error in errors))
            self.assertTrue(any("expected_outputs[0] must reference output.json" in error for error in errors))

    def test_validator_recomputes_deterministic_evidence_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "loose.json"
            write_json(input_path, demo_payloads(1)[0])
            run_dir = produce_evidence_run(input_path, root / "runs")

            evidence_path = run_dir / "evidence_bundle.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["execution_id"] = "exec_00000000000000000000"
            evidence["trace_id"] = "trace_00000000000000000000"
            evidence["artifact_reference"] = "exec_00000000000000000000"
            evidence["replay_reference"] = "replay_00000000000000000000"
            write_json(evidence_path, evidence)

            _, errors = validate_evidence_root(root / "runs")
            self.assertTrue(any("execution_id is not deterministic" in error for error in errors))
            self.assertTrue(any("trace_id is not deterministic" in error for error in errors))
            self.assertTrue(any("artifact_reference is not deterministic" in error for error in errors))
            self.assertTrue(any("replay_reference is not deterministic" in error for error in errors))

    def test_validator_checks_trace_propagation_and_execution_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "loose.json"
            write_json(input_path, demo_payloads(1)[0])
            run_dir = produce_evidence_run(input_path, root / "runs")

            replay_path = run_dir / "replay_bundle.json"
            replay = json.loads(replay_path.read_text(encoding="utf-8"))
            replay["trace_id"] = "trace_00000000000000000000"
            write_json(replay_path, replay)

            log_path = run_dir / "execution.log"
            log_path.write_text(log_path.read_text(encoding="utf-8").replace("status=success", "status=failed"), encoding="utf-8")

            _, errors = validate_evidence_root(root / "runs")
            self.assertTrue(any("replay_bundle.json trace_id does not match" in error for error in errors))
            self.assertTrue(any("execution.log status does not match" in error for error in errors))

    def test_shakti_adapter_outputs_are_deterministic_for_same_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "plain-request.txt"
            input_path.write_text(
                "Please process case id runtime-proof-201. "
                "source system GC_RUNTIME_EVIDENCE_PRODUCER. "
                "target system SHAKTI_GOVERNANCE_CONSUMER. "
                "operation consumer handoff.",
                encoding="utf-8",
            )
            run_dir = produce_evidence_run(input_path, root / "runs")
            evidence_path = run_dir / "evidence_bundle.json"

            first = root / "first"
            second = root / "second"
            consume_evidence(evidence_path, first)
            consume_evidence(evidence_path, second)

            for name in ["validation_decision.json", "governance_record.json", "registration_reference.json"]:
                self.assertEqual(
                    json.loads((first / name).read_text(encoding="utf-8")),
                    json.loads((second / name).read_text(encoding="utf-8")),
                )

    def test_shakti_adapter_rejects_invalid_contract_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "plain-request.txt"
            input_path.write_text(
                "Please process case id runtime-proof-301. "
                "source system GC_RUNTIME_EVIDENCE_PRODUCER. "
                "target system SHAKTI_GOVERNANCE_CONSUMER. "
                "operation consumer handoff.",
                encoding="utf-8",
            )
            run_dir = produce_evidence_run(input_path, root / "runs")
            evidence_path = run_dir / "evidence_bundle.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["contract_version"] = "unsupported-contract/v0"
            write_json(evidence_path, evidence)

            consume_evidence(evidence_path, root / "tantra")
            decision = json.loads((root / "tantra" / "validation_decision.json").read_text(encoding="utf-8"))
            registration = json.loads((root / "tantra" / "registration_reference.json").read_text(encoding="utf-8"))

            self.assertEqual(decision["decision"], "REJECTED")
            self.assertIn("contract_version", decision["reason_codes"])
            self.assertEqual(registration["registration_status"], "REJECTED")

    def test_shakti_adapter_rejects_missing_required_schema_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "plain-request.txt"
            input_path.write_text(
                "Please process case id runtime-proof-302. "
                "source system GC_RUNTIME_EVIDENCE_PRODUCER. "
                "target system SHAKTI_GOVERNANCE_CONSUMER. "
                "operation consumer handoff.",
                encoding="utf-8",
            )
            run_dir = produce_evidence_run(input_path, root / "runs")
            evidence_path = run_dir / "evidence_bundle.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            del evidence["trace_id"]
            write_json(evidence_path, evidence)

            consume_evidence(evidence_path, root / "tantra")
            decision = json.loads((root / "tantra" / "validation_decision.json").read_text(encoding="utf-8"))

            self.assertEqual(decision["decision"], "REJECTED")
            self.assertIn("schema_required_fields", decision["reason_codes"])
            self.assertIn("schema_trace_id_present", decision["reason_codes"])

    def test_shakti_adapter_rejects_artifact_integrity_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "plain-request.txt"
            input_path.write_text(
                "Please process case id runtime-proof-303. "
                "source system GC_RUNTIME_EVIDENCE_PRODUCER. "
                "target system SHAKTI_GOVERNANCE_CONSUMER. "
                "operation artifact generation.",
                encoding="utf-8",
            )
            run_dir = produce_evidence_run(input_path, root / "runs")
            write_json(run_dir / "output.json", {"tampered": True})

            consume_evidence(run_dir / "evidence_bundle.json", root / "tantra")
            decision = json.loads((root / "tantra" / "validation_decision.json").read_text(encoding="utf-8"))

            self.assertEqual(decision["decision"], "REJECTED")
            self.assertIn("artifact_integrity_output", decision["reason_codes"])
            self.assertIn("replay_expected_output_integrity", decision["reason_codes"])

    def test_shakti_adapter_rejects_missing_replay_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "plain-request.txt"
            input_path.write_text(
                "Please process case id runtime-proof-304. "
                "source system GC_RUNTIME_EVIDENCE_PRODUCER. "
                "target system SHAKTI_GOVERNANCE_CONSUMER. "
                "operation replay validation.",
                encoding="utf-8",
            )
            run_dir = produce_evidence_run(input_path, root / "runs")
            replay_path = run_dir / "replay_bundle.json"
            replay = json.loads(replay_path.read_text(encoding="utf-8"))
            del replay["replay_inputs"]
            write_json(replay_path, replay)

            consume_evidence(run_dir / "evidence_bundle.json", root / "tantra")
            decision = json.loads((root / "tantra" / "validation_decision.json").read_text(encoding="utf-8"))

            self.assertEqual(decision["decision"], "REJECTED")
            self.assertIn("artifact_integrity_replay", decision["reason_codes"])
            self.assertIn("replay_input_integrity", decision["reason_codes"])

    def test_tms_emits_partial_when_mdu_registration_does_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "validation_decision.json",
                {
                    "decision": "APPROVED",
                    "decision_id": "validation_decision_test",
                    "execution_id": "exec_test",
                    "trace_id": "trace_test",
                },
            )
            write_json(
                root / "lineage_registration.json",
                {
                    "mdu_registration_id": "mdu_registration_test",
                    "registration_status": "REJECTED",
                    "trace_id": "trace_test",
                },
            )
            write_json(
                root / "lineage_chain.json",
                {
                    "chain_id": "lineage_chain_test",
                    "reconstruction": {"reconstructable": True},
                    "trace_id": "trace_test",
                },
            )

            output_path = emit_convergence(
                root / "validation_decision.json",
                root / "lineage_registration.json",
                root / "lineage_chain.json",
                root,
            )
            convergence = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual(convergence["status"], "PARTIAL")
            self.assertIn("MDU_REGISTRATION_NOT_REGISTERED", convergence["reason_codes"])

    def test_tms_emits_failed_when_shakti_rejects_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "validation_decision.json",
                {
                    "decision": "REJECTED",
                    "decision_id": "validation_decision_test",
                    "execution_id": "exec_test",
                    "trace_id": "trace_test",
                },
            )
            write_json(
                root / "lineage_registration.json",
                {
                    "mdu_registration_id": "mdu_registration_test",
                    "registration_status": "REGISTERED",
                    "trace_id": "trace_test",
                },
            )
            write_json(
                root / "lineage_chain.json",
                {
                    "chain_id": "lineage_chain_test",
                    "reconstruction": {"reconstructable": True},
                    "trace_id": "trace_test",
                },
            )

            output_path = emit_convergence(
                root / "validation_decision.json",
                root / "lineage_registration.json",
                root / "lineage_chain.json",
                root,
            )
            convergence = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual(convergence["status"], "FAILED")
            self.assertIn("SHAKTI_VALIDATION_NOT_APPROVED", convergence["reason_codes"])

    def test_tantra_chain_consumes_existing_evidence_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "plain-request.txt"
            input_path.write_text(
                "Please process case id runtime-proof-401. "
                "source system GC_RUNTIME_EVIDENCE_PRODUCER. "
                "target system SHAKTI_GOVERNANCE_CONSUMER. "
                "operation governance consumption.",
                encoding="utf-8",
            )
            evidence_root = root / "evidence_runs"
            run_dir = produce_evidence_run(input_path, evidence_root)
            summary = run_operational_chain(run_dir / "evidence_bundle.json", root / "tantra")

            self.assertEqual(summary["input_mode"], "existing_evidence_package")
            self.assertEqual(len([path for path in evidence_root.iterdir() if path.is_dir()]), 1)
            self.assertEqual(summary["convergence_status"], "CONVERGED")
            self.assertTrue((root / "tantra" / "validation_decision.json").exists())
            self.assertTrue((root / "tantra" / "lineage_chain.json").exists())

    def test_tantra_chain_runs_one_trace_to_convergence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "plain-request.txt"
            input_path.write_text(
                "Please process case id runtime-proof-202. "
                "source system GC_RUNTIME_EVIDENCE_PRODUCER. "
                "target system SHAKTI_GOVERNANCE_CONSUMER. "
                "operation lineage capture.",
                encoding="utf-8",
            )
            summary = run_chain(input_path, root / "evidence_runs", root / "tantra")

            validation = json.loads((root / "tantra" / "validation_decision.json").read_text(encoding="utf-8"))
            governance = json.loads((root / "tantra" / "governance_record.json").read_text(encoding="utf-8"))
            lineage = json.loads((root / "tantra" / "lineage_chain.json").read_text(encoding="utf-8"))
            convergence = json.loads((root / "tantra" / "tms_convergence_status.json").read_text(encoding="utf-8"))

            self.assertEqual(summary["trace_id"], validation["trace_id"])
            self.assertEqual(validation["trace_id"], governance["trace_id"])
            self.assertEqual(governance["trace_id"], lineage["trace_id"])
            self.assertEqual(lineage["trace_id"], convergence["trace_id"])
            self.assertEqual(validation["decision"], "APPROVED")
            self.assertEqual(convergence["status"], "CONVERGED")
            self.assertEqual(summary["input_mode"], "generated_sample_evidence")
            self.assertEqual(summary["sample_input"], input_path.as_posix())
            self.assertTrue(lineage["reconstruction"]["reconstructable"])
            proof_text = (root / "tantra" / "TANTRA_CHAIN_PROOF.md").read_text(encoding="utf-8")
            self.assertIn(
                "Input Payload -> Evidence Generation -> SHAKTI Validation -> MDU Registration -> TMS Convergence",
                proof_text,
            )
            ansh_proof = (root / "tantra" / "ANSH_INTEGRATION_PROOF.md").read_text(encoding="utf-8")
            self.assertIn("Phase 6 Execution", ansh_proof)
            self.assertIn("SHAKTI Validation", ansh_proof)
            self.assertIn("MDU And TMS Result", ansh_proof)

            for name in [
                "SHAKTI_CONSUMPTION_PROOF.md",
                "GOVERNANCE_REGISTRATION_PROOF.md",
                "TMS_CONVERGENCE_PROOF.md",
                "TANTRA_CHAIN_PROOF.md",
                "ANSH_INTEGRATION_PROOF.md",
            ]:
                self.assertTrue((root / "tantra" / name).exists())


if __name__ == "__main__":
    unittest.main()
