# Integration Guide

## Producer Integration

Generate evidence for one payload:

```bash
python operational_drift_monitor.py run --input <payload.json> --out outputs/evidence_runs
```

Generate the required 10-run proof set:

```bash
python operational_drift_monitor.py demo --count 10 --out outputs/evidence_runs
```

Validate generated evidence:

```bash
python operational_drift_monitor.py validate --root outputs/evidence_runs --min-runs 10
```

## Input Contract

The preferred canonical input payload includes:

- `case_id`
- `source_system`
- `target_system`
- `operation`
- `payload`

The producer also accepts noncanonical JSON when these fields can be extracted from aliases or nested objects.

Examples of accepted aliases:

- `id`, `caseId`, `request_id` -> `case_id`
- `from`, `source`, `origin` -> `source_system`
- `to`, `target`, `recipient` -> `target_system`
- `action`, `type`, `command` -> `operation`
- `data`, `body`, `content`, `event` -> `payload`

Only fields that cannot be extracted are listed as missing. The producer preserves the raw submitted payload in `input.json` and writes extracted canonical field details into `input_extraction` inside each required bundle.

## Architecture

The implementation is split into three parts:

- `operational_drift_monitor.py`: CLI entrypoint for `run`, `demo`, and `validate`.
- `runtime_evidence/canonical.py`: canonical JSON, pretty JSON, SHA-256 hashing, deterministic IDs, versions, and timestamps.
- `runtime_evidence/producer.py`: evidence generation, bundle writing, artifact hashing, and validation.
- `runtime_evidence/reference_runtime.py`: current local runtime execution path.

## Data Flow

```text
input payload
  -> operational_drift_monitor.py
  -> runtime_evidence.producer.produce_evidence_run
  -> runtime_evidence.reference_runtime.execute_payload
  -> raw input.json + output.json
  -> evidence_bundle.json + lineage_bundle.json + replay_bundle.json + handover_bundle.json
  -> execution.log
```

The consumer should not need to modify files before reading them.

## Replacing the Reference Runtime

This repository did not contain an upstream runtime entrypoint when the evidence system was created. The local reference runtime lives in `runtime_evidence/reference_runtime.py`.

To connect a real upstream runtime later:

1. Keep `produce_evidence_run` as the artifact boundary.
2. Replace `execute_payload(payload)` with the real execution call.
3. Preserve `execution_status`, output hashing, and bundle generation.
4. Keep deterministic ID generation in `runtime_evidence/canonical.py`.
5. Run validation after producing the proof set.

## Integration Expectations For Ansh

Ansh's consumer should:

- read `evidence_bundle.json` first.
- verify `contract_version`, `schema_version`, and `execution_status`.
- verify SHA-256 hashes in `artifacts`.
- use `lineage_bundle.json` for provenance reconstruction.
- use `replay_bundle.json` for replay reconstruction.
- use `handover_bundle.json` for bundle index and readiness.
- use `input_extraction` in any bundle to inspect how the mangled `input.json` was canonicalized.

## Compatibility Notes

- The implementation uses Python standard library only.
- Bundle filenames match the assignment exactly.
- JSON files are pretty-printed for review.
- Hashing and deterministic IDs still use canonical JSON.
