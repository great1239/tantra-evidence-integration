from pathlib import Path
import json
import tempfile
import unittest

from runtime_evidence.canonical import stable_id
from runtime_evidence.producer import produce_evidence_run, validate_evidence_root, write_json
from runtime_evidence.reference_runtime import demo_payloads
from runtime_evidence.normalizer import normalize_input


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


if __name__ == "__main__":
    unittest.main()
