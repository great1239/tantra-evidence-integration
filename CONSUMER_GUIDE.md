# Consumer Guide

This guide is for the SHAKTI governance consumer that receives generated runtime evidence bundles.

## Evidence Package Layout

Each execution lives in one independent container directory under `outputs/evidence_runs/<execution_id>/`.

Each execution directory contains exactly:

- `evidence_bundle.json`
- `lineage_bundle.json`
- `replay_bundle.json`
- `handover_bundle.json`
- `input.json`
- `output.json`
- `execution.log`

## Read Order

1. Open `evidence_bundle.json`.
2. Confirm `contract_version` is `shakti-runtime-evidence/v1`.
3. Confirm `schema_version` is `1.0.0`.
4. Confirm `execution_status` is `success`.
5. Confirm `execution_context` answers what happened, where, when, producer, consumer, and replayability.
6. Confirm `input_extraction.missing_fields` is empty for successful runs.
7. Confirm `consumer_compatibility.self_contained` is `true`.
8. Use `artifacts` to verify SHA-256 hashes for `input.json`, `output.json`, `lineage_bundle.json`, `replay_bundle.json`, and `handover_bundle.json`.
9. Open `lineage_bundle.json` to reconstruct the producer, artifact, and consumer path.
10. Open `replay_bundle.json` to rerun the raw/mangled input and compare the resulting `output.json` hash.
11. Open `handover_bundle.json` for the bundle index, consumer instructions, known limitations, and readiness.
12. Open `execution.log` if a human-readable execution trail is needed.

## Consumer Contract

The consumer can rely on these invariants:

- One execution directory equals one execution package.
- The required bundle filenames are stable and match the assignment.
- `execution_id` and `trace_id` are deterministic for a given extracted canonical input payload.
- `input.json` and `output.json` are included in the package.
- every required bundle includes `execution_context`.
- `input.json` preserves the raw/mangled submitted input.
- every required bundle includes `input_extraction` with extracted canonical fields.
- `input_extraction.missing_fields` appears only when a field could not be extracted.
- Artifact hashes use SHA-256.
- The package is self-contained.
- Timestamps record actual execution time and are not used to generate deterministic identifiers.

## Validation

Validate the required 10-run proof set:

```bash
python operational_drift_monitor.py validate --root outputs/evidence_runs --min-runs 10
```

Validate the proof root with a lower minimum when only one run is required:

```bash
python operational_drift_monitor.py validate --root outputs/evidence_runs --min-runs 1
```

The validator checks required files, required evidence fields, and artifact hash consistency.

## Manual Hash Check

For a specific run directory, compare the SHA-256 shown in `evidence_bundle.json.artifacts.<name>.sha256` with the file hash.

PowerShell example:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath "outputs\evidence_runs\<execution_id>\output.json"
```

## Replay Process

1. Open `replay_bundle.json`.
2. Read `replay_inputs[0].reference` and confirm it points to `input.json`.
3. Read `expected_outputs[0].sha256`.
4. Run the command in `replay_command`.
5. Hash the replayed `output.json`.
6. Confirm the replayed hash matches `expected_outputs[0].sha256`.

Replay is considered reconstructable when the same input produces the same output hash.

## Lineage Process

1. Open `lineage_bundle.json`.
2. Read `nodes` to identify the input payload, runtime producer, runtime output, and governance consumer.
3. Read `edges` to reconstruct the relationship path.
4. Read `provenance_chain` to reconstruct the ordered execution history.

Expected lineage path:

```text
input_payload -> runtime_processor -> runtime_output -> governance_consumer
```

## Acceptance Criteria

A package is ready for SHAKTI consumption when:

- `execution_status` is `success`.
- `contract_version` and `schema_version` match the expected values.
- all required files are present.
- artifact hashes match the files on disk.
- replay reconstruction can reproduce the expected output hash.
- lineage reconstruction identifies input, producer, output, and consumer.
- `input_extraction.missing_fields` is empty for successful execution.

For edge cases and failure handling, see `EDGE_CASES_AND_FAILURES.md`.
