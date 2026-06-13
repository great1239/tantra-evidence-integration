# Review Packet

## Entry Point

Use `run_tantra_chain.py` for the current TANTRA integration task.

## Assignment Boundary

Evidence generation is retained as existing upstream infrastructure. The current assignment does not define a new evidence format and does not replace the producer. The new work is the operational TANTRA chain that consumes an existing evidence package, validates it through SHAKTI, registers lineage through MDU, emits TMS convergence, and preserves replay/lineage reconstruction.

Run the operational chain from an existing evidence package:

```bash
python run_tantra_chain.py --evidence outputs/evidence_runs/exec_709063d750fe9fbb4618/evidence_bundle.json --out .
```

Use the optional demo path only when you need to create a sample evidence package first:

```bash
python run_tantra_chain.py --input sample_inputs/runtime-proof-010.json --evidence-out outputs/evidence_runs --out .
```

Use `runtime_evidence_producer.py` only when regenerating evidence packages directly.

Generate proof:

```bash
python runtime_evidence_producer.py demo --count 10 --out outputs/evidence_runs
```

Validate proof:

```bash
python runtime_evidence_producer.py validate --root outputs/evidence_runs --min-runs 10
```

Run one payload:

```bash
python runtime_evidence_producer.py run --input sample_inputs/runtime-proof-001.json --out outputs/evidence_runs
```

## Execution Flow

The upstream producer CLI reads an input payload, extracts canonical fields when the input is mangled JSON or schema-free text, executes the local runtime processor, writes raw `input.json` and `output.json`, then generates the evidence, lineage, replay, and handover bundles.

The TANTRA chain starts after that point. It consumes an existing `evidence_bundle.json` through SHAKTI, registers governance and lineage outputs for MDU, emits TMS convergence status, and preserves a single trace across all stages.

Operational TANTRA path:

```text
run_tantra_chain.py
  -> existing evidence_bundle.json
  -> shakti_consumer_adapter.py
  -> governance_record.json + validation_decision.json + registration_reference.json
  -> lineage_registration.py
  -> lineage_registration.json + lineage_chain.json
  -> tms_convergence_emitter.py
  -> tms_convergence_status.json
```

Sample bootstrap path:

```text
run_tantra_chain.py --input ...
  -> existing produce_evidence_run(...)
  -> operational TANTRA path above
```

## Upstream Evidence Generation Flow

This flow is kept for reproducibility and sample generation. It is not the new TANTRA artifact format.

1. Read the submitted input payload.
2. Extract canonical fields from aliases, nested objects, or plain English text when the input is noncanonical.
3. Record `_normalization.missing_fields` only for fields that cannot be extracted.
4. Canonicalize input JSON for hashing.
5. Generate deterministic `execution_id`, `trace_id`, and `replay_reference`.
6. Execute the runtime payload.
7. Write raw `input.json` and runtime `output.json`.
8. Generate SHA-256 hashes for input, output, lineage, replay, and handover artifacts.
9. Write `lineage_bundle.json`.
10. Write `replay_bundle.json`.
11. Write `handover_bundle.json`.
12. Write `evidence_bundle.json`.
13. Write `execution.log`.

## Bundle Definitions

- `evidence_bundle.json`: canonical summary, required evidence fields, artifact references, artifact hashes, producer metadata, consumer compatibility, and human summary.
- `lineage_bundle.json`: source, producer, output artifact, governance consumer, graph edges, and ordered provenance chain.
- `replay_bundle.json`: replay command, replay input reference, expected output hash, deterministic ID assumptions, and runtime requirements.
- `handover_bundle.json`: file index, consumer instructions, known limitations, and integration readiness.
- `input.json`: raw submitted payload. Demo proof inputs are intentionally mangled to show extraction efficiency.
- `output.json`: exact runtime output produced from the input.
- `execution.log`: plain-text proof that records timestamp, execution ID, trace ID, input hash, output hash, and status.

Each required bundle includes `execution_context` with direct answers for: what happened, where it happened, when it happened, what produced it, what consumed it, and what can be replayed.

Each required bundle includes `input_extraction` with the canonical fields extracted from the raw/mangled input and the JSON path used for each field.

## TANTRA Integration Outputs

- `validation_decision.json`: SHAKTI validation result, deterministic decision ID, replay availability, check results, and reason codes.
- `governance_record.json`: governance record created from validated evidence.
- `registration_reference.json`: deterministic SHAKTI consumer registration reference.
- `lineage_registration.json`: MDU registration record with query keys and registered artifact hashes.
- `lineage_chain.json`: reconstructable chain from input artifact to evidence, governance record, consumer registration, and MDU registration.
- `tms_convergence_status.json`: TMS status emission using `CONVERGED`, `PARTIAL`, or `FAILED`.

TMS status policy:

- `CONVERGED`: SHAKTI validation is approved, MDU registration is registered, and lineage reconstruction is available.
- `PARTIAL`: SHAKTI validation is approved, but MDU registration or lineage reconstruction is incomplete.
- `FAILED`: SHAKTI validation is not approved.

## Failure Cases

See `EDGE_CASES_AND_FAILURES.md`.

The TANTRA consumer layer also has executable negative-path coverage:

- unsupported SHAKTI contract versions are rejected.
- missing canonical evidence fields are rejected.
- artifact hash mismatches are rejected.
- missing replay metadata is rejected.
- TMS emits `PARTIAL` when SHAKTI approval exists but MDU registration or reconstruction is incomplete.
- TMS emits `FAILED` when SHAKTI validation is not approved.

## Success Criteria

| Criterion | Evidence location |
| --- | --- |
| A runtime execution produces a complete evidence package. | Run container contains the exact required files listed below. |
| Ansh can consume the package without modifying it. | `evidence_bundle.json.consumer_compatibility`, `handover_bundle.json.bundle_index`, and local artifact hashes. |
| A new developer can reconstruct the execution path using only the generated artifacts. | `DEVELOPER_BUNDLE_GUIDE.md`, `execution_context`, `input_extraction`, `output.json`, `lineage_bundle.json`, and `execution.log`. |
| Replay reconstruction is possible. | `replay_bundle.json.replay_command`, `replay_inputs`, `expected_outputs`, and `determinism`. |
| Lineage reconstruction is possible. | `lineage_bundle.json.nodes`, `edges`, and `provenance_chain`. |
| Governance validation can be performed using the generated evidence. | `evidence_bundle.json` contract/schema/status/confidence/consumer compatibility/artifact hashes. |
| Evidence is operational inside TANTRA. | `run_tantra_chain.py --evidence ...` produces SHAKTI, MDU, and TMS outputs from one existing evidence package and one trace. |
| Replay reconstruction remains possible after TANTRA consumption. | `replay_bundle.json` remains referenced by the evidence bundle and is validated by `validation_decision.json`. |

The validator now checks the success criteria surface in addition to required files and hashes.

## Protocol Alignment

| Learning-kit term | How the system follows it | Verification surface |
| --- | --- | --- |
| Event sourcing | Each run preserves the submitted input, runtime output, ordered provenance actions, and execution log as the event trail for that execution. This is evidence-level event sourcing, not a full append-only application event store. | `input.json`, `output.json`, `lineage_bundle.json.provenance_chain`, `execution.log` |
| Execution lineage | The lineage graph records payload, runtime processor, runtime output, and governance consumer relationships. | `lineage_bundle.json.nodes`, `lineage_bundle.json.edges` |
| Trace propagation | `execution_id`, `trace_id`, contract, schema, timestamp, source, and target are propagated across all required bundles. | All required bundles; validator checks cross-bundle consistency. |
| Replay systems | The replay bundle records the replay command, input hash, expected output hash, deterministic assumptions, and runtime requirements. | `replay_bundle.json` |
| Audit artifacts | The evidence bundle indexes all required artifacts and stores SHA-256 hashes for verification. The execution log records the run identifiers and file hashes. | `evidence_bundle.json.artifacts`, `execution.log` |
| Provenance chains | The provenance chain records ordered execution actions: submitted payload, executed payload, and generated evidence bundles. | `lineage_bundle.json.provenance_chain` |

## Sample Outputs

Generated proof artifacts live under `outputs/evidence_runs/<execution_id>/`.

Each directory is an independent output container. Each container contains exactly:

- `input.json`
- `output.json`
- `evidence_bundle.json`
- `lineage_bundle.json`
- `replay_bundle.json`
- `handover_bundle.json`
- `execution.log`

Example run directory:

```text
outputs/evidence_runs/exec_ffdf0ecc6558be6c5033/
```

The `execution.log` files satisfy the assignment requirement for execution screenshots or logs.

## Consumer Instructions

1. Run `python run_tantra_chain.py --evidence outputs/evidence_runs/exec_709063d750fe9fbb4618/evidence_bundle.json --out .`.
2. Open `validation_decision.json` to inspect SHAKTI validation.
3. Open `governance_record.json` and `registration_reference.json` to inspect governance registration.
4. Open `lineage_registration.json` and `lineage_chain.json` to inspect MDU registration and reconstruction.
5. Open `tms_convergence_status.json` to inspect TMS convergence.
6. Use the generated proof files for phase-specific review.
7. Use `replay_bundle.json` under the evidence run directory to rerun `input.json` and compare output hash.

## Known Limitations

This workspace did not contain an existing SHAKTI runtime implementation. The included reference runtime creates real generated artifacts from actual CLI executions, but it should be replaced with the upstream runtime when that system is available.

This workspace also did not contain a separate Ansh SHAKTI module, remote endpoint, or external TMS schema. The current integration validates against the repository contract `shakti-runtime-evidence/v1` and schema `1.0.0`. The replacement point for Ansh integration is `shakti_consumer_adapter.consume_evidence(...)`; the evidence format should remain unchanged.

Timestamps are real execution times and are intentionally excluded from deterministic ID generation.

## Integration Readiness Assessment

Current readiness: `ready_for_consumer_validation`.

The evidence layer is ready for consumer validation once:

- `python runtime_evidence_producer.py validate --root outputs/evidence_runs --min-runs 10` returns `{"status":"ok"}`.
- all 10 execution directories contain the exact required filenames.
- replay reconstruction matches the expected output hash.
- lineage reconstruction identifies input, producer, output, and consumer.
- `python run_tantra_chain.py --evidence outputs/evidence_runs/exec_709063d750fe9fbb4618/evidence_bundle.json --out .` returns `CONVERGED`.
- SHAKTI, MDU, and TMS outputs share the same `trace_id`.
- `python -m unittest discover -s tests` passes the SHAKTI rejection, MDU/TMS propagation, replay reconstruction, and lineage reconstruction tests.

