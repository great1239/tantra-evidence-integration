# Review Packet

## Entry Point

Use `operational_drift_monitor.py`.

Generate proof:

```bash
python operational_drift_monitor.py demo --count 10 --out outputs/evidence_runs
```

Validate proof:

```bash
python operational_drift_monitor.py validate --root outputs/evidence_runs --min-runs 10
```

Run one payload:

```bash
python operational_drift_monitor.py run --input sample_inputs/runtime-proof-001.json --out outputs/evidence_runs
```

## Execution Flow

The CLI reads an input JSON payload, extracts canonical fields when the input is mangled, executes the local runtime processor, writes raw `input.json` and `output.json`, then generates the evidence, lineage, replay, and handover bundles.

Execution path:

```text
operational_drift_monitor.py
  -> produce_evidence_run(...)
  -> execute_payload(...)
  -> write raw input/output
  -> write lineage/replay/handover/evidence bundles
  -> write execution.log
```

## Evidence Generation Flow

1. Read the submitted input payload.
2. Extract canonical fields from aliases or nested objects when the input is noncanonical.
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

## Failure Cases

See `EDGE_CASES_AND_FAILURES.md`.

## Success Criteria

| Criterion | Evidence location |
| --- | --- |
| A runtime execution produces a complete evidence package. | Run container contains the exact required files listed below. |
| Ansh can consume the package without modifying it. | `evidence_bundle.json.consumer_compatibility`, `handover_bundle.json.bundle_index`, and local artifact hashes. |
| A new developer can reconstruct the execution path using only the generated artifacts. | `DEVELOPER_BUNDLE_GUIDE.md`, `execution_context`, `input_extraction`, `output.json`, `lineage_bundle.json`, and `execution.log`. |
| Replay reconstruction is possible. | `replay_bundle.json.replay_command`, `replay_inputs`, `expected_outputs`, and `determinism`. |
| Lineage reconstruction is possible. | `lineage_bundle.json.nodes`, `edges`, and `provenance_chain`. |
| Governance validation can be performed using the generated evidence. | `evidence_bundle.json` contract/schema/status/confidence/consumer compatibility/artifact hashes. |

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

1. Read `CONSUMER_GUIDE.md`.
2. Read `DEVELOPER_BUNDLE_GUIDE.md` for the complete developer explanation of bundle structure, field meanings, artifact relationships, replay, and lineage.
3. Validate the proof set.
4. Open one run directory under `outputs/evidence_runs`.
5. Start with `evidence_bundle.json`.
6. Verify hashes in `artifacts`.
7. Use `lineage_bundle.json` to reconstruct source, producer, output, and consumer.
8. Use `replay_bundle.json` to rerun `input.json` and compare output hash.
9. Use `handover_bundle.json` to confirm index, limitations, and readiness.

## Known Limitations

This workspace did not contain an existing SHAKTI runtime implementation. The included reference runtime creates real generated artifacts from actual CLI executions, but it should be replaced with the upstream runtime when that system is available.

Timestamps are real execution times and are intentionally excluded from deterministic ID generation.

## Integration Readiness Assessment

Current readiness: `ready_for_consumer_validation`.

The evidence layer is ready for consumer validation once:

- `python operational_drift_monitor.py validate --root outputs/evidence_runs --min-runs 10` returns `{"status":"ok"}`.
- all 10 execution directories contain the exact required filenames.
- replay reconstruction matches the expected output hash.
- lineage reconstruction identifies input, producer, output, and consumer.
