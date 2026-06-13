# Integration Guide

## TANTRA Operational Integration

Evidence generation is upstream and already exists in this repository for reproducibility. TANTRA integration starts from an existing `evidence_bundle.json` and produces validation, governance, lineage, convergence, and proof outputs.

Run the TANTRA operational chain from an existing evidence package:

```bash
python run_tantra_chain.py --evidence outputs/evidence_runs/exec_709063d750fe9fbb4618/evidence_bundle.json --out .
```

Use the optional sample bootstrap path only when an evidence package has not been generated yet:

```bash
python run_tantra_chain.py --input sample_inputs/runtime-proof-010.json --evidence-out outputs/evidence_runs --out .
```

Regenerate upstream evidence for one payload when needed:

```bash
python runtime_evidence_producer.py run --input <payload.json> --out outputs/evidence_runs
```

Generate the required 10-run proof set:

```bash
python runtime_evidence_producer.py demo --count 10 --out outputs/evidence_runs
```

Validate generated evidence:

```bash
python runtime_evidence_producer.py validate --root outputs/evidence_runs --min-runs 10
```

## Upstream Input Contract

This contract belongs to the retained evidence generator. TANTRA consumers should normally start from `evidence_bundle.json`.

The preferred canonical input payload includes:

- `case_id`
- `source_system`
- `target_system`
- `operation`
- `payload`

The producer also accepts noncanonical JSON when these fields can be extracted from aliases or nested objects. It can also accept a raw text file or JSON string when the sentence contains recognizable case, source, target, and operation details.

Examples of accepted aliases:

- `id`, `caseId`, `request_id` -> `case_id`
- `from`, `source`, `origin` -> `source_system`
- `to`, `target`, `recipient` -> `target_system`
- `action`, `type`, `command` -> `operation`
- `data`, `body`, `content`, `event` -> `payload`

Only fields that cannot be extracted are listed as missing. The producer preserves the raw submitted payload in `input.json` and writes extracted canonical field details into `input_extraction` inside each required bundle.

Plain English example:

```text
Please process case id runtime-proof-012. source system GC_RUNTIME_EVIDENCE_PRODUCER. target system SHAKTI_GOVERNANCE_CONSUMER. operation lineage capture.
```

## Architecture

The implementation is split into upstream evidence infrastructure and the current TANTRA integration layer:

- `runtime_evidence_producer.py`: upstream evidence CLI entrypoint for `run`, `demo`, and `validate`.
- `runtime_evidence/canonical.py`: canonical JSON, pretty JSON, SHA-256 hashing, deterministic IDs, versions, and timestamps.
- `runtime_evidence/producer.py`: upstream evidence generation, bundle writing, artifact hashing, and validation.
- `runtime_evidence/reference_runtime.py`: current local upstream runtime execution path.
- `shakti_consumer_adapter.py`: SHAKTI consumption, contract/schema checks, artifact integrity checks, replay metadata checks, and governance output.
- `lineage_registration.py`: MDU lineage registration and reconstructable lineage chain output.
- `tms_convergence_emitter.py`: TMS convergence status emission.
- `run_tantra_chain.py`: one-command TANTRA consumption path for existing evidence packages. The `--input` mode is a demo bootstrap that calls the existing producer first.

## Data Flow

```text
existing evidence_bundle.json
  -> shakti_consumer_adapter.py
  -> governance_record.json + validation_decision.json + registration_reference.json
  -> lineage_registration.py
  -> lineage_registration.json + lineage_chain.json
  -> tms_convergence_emitter.py
  -> tms_convergence_status.json
```

The consumer should not need to modify files before reading them.

The raw input payload and evidence generator sit upstream of TANTRA. They are still available for demo generation and validation, but they are not redesigned by the TANTRA integration.

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

