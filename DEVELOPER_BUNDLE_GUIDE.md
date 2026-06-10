# Developer Bundle Guide

This guide is the first file a new developer should read when trying to understand the generated runtime evidence containers.

Each run is a self-contained container under:

```text
outputs/evidence_runs/<execution_id>/
```

Nothing outside that directory is required to inspect the run, verify its hashes, or reconstruct lineage. Replay uses the repository CLI command recorded in `replay_bundle.json`.

## Bundle Structure

Each execution container contains these files:

| File | Purpose |
| --- | --- |
| `input.json` | The raw submitted input. Demo inputs are intentionally mangled or noncanonical to prove extraction behavior. |
| `output.json` | The exact deterministic output produced by the runtime processor after canonical extraction. |
| `evidence_bundle.json` | The main summary bundle. Read this first. It identifies the run, status, producer, consumer, hashes, and artifact references. |
| `lineage_bundle.json` | The provenance bundle. It shows which input was consumed, which producer processed it, which output was produced, and which consumer receives it. |
| `replay_bundle.json` | The replay bundle. It gives the replay command, replay inputs, expected output hash, and deterministic assumptions. |
| `handover_bundle.json` | The consumer handoff index. It lists bundle files, instructions, limitations, and readiness. |
| `execution.log` | A plain-text execution trail for human review. |

## Common Bundle Fields

These fields appear across the required bundles so a developer can correlate files without guessing.

| Field | Meaning |
| --- | --- |
| `execution_id` | Deterministic run directory identifier. Format: `exec_<20 hex chars>`. Generated from the extracted canonical input, contract, and schema. |
| `trace_id` | Deterministic trace identifier shared by all bundles for the same run. |
| `contract_version` | Evidence contract expected by the consumer. Current value: `shakti-runtime-evidence/v1`. |
| `schema_version` | Bundle schema version. Current value: `1.0.0`. |
| `timestamp` | UTC time when the bundle was generated. It is not used to generate deterministic IDs. |
| `source_system` | Extracted system that submitted or represents the input. |
| `target_system` | Extracted governance consumer or destination system. |
| `execution_context` | Direct answers to what happened, where, when, producer, consumer, and replayability. |
| `input_extraction` | Report showing how raw `input.json` was converted into canonical runtime fields. |

## Execution Context

Every required bundle includes `execution_context` with the same six fields.

| Field | Meaning |
| --- | --- |
| `what_happened` | Operation executed and resulting status. |
| `where_it_happened` | Runtime/evidence producer location. |
| `when_it_happened` | Bundle generation timestamp. |
| `what_produced_it` | Entrypoint that produced the bundle, currently `runtime_evidence_producer.py`. |
| `what_consumed_it` | Intended consumer extracted from the input. |
| `what_can_be_replayed` | Replayable artifact and where to find the replay command. |

## Input Extraction

`input.json` intentionally preserves the submitted payload, even when it is badly shaped. The canonical runtime fields are recorded in `input_extraction`.

| Field | Meaning |
| --- | --- |
| `input_reference` | Always points to `input.json`. |
| `input_shape` | `already_canonical` when the raw input used the preferred schema; `noncanonical_extracted` when aliases or nested fields were used. |
| `raw_input_sha256` | SHA-256 hash of the raw submitted input as written to `input.json`. |
| `raw_input_type` | JSON type of the submitted input, such as `dict` or `list`. |
| `canonical_fields.case_id` | Extracted case/run identifier. |
| `canonical_fields.source_system` | Extracted producer/source system. |
| `canonical_fields.target_system` | Extracted consumer/target system. |
| `canonical_fields.operation` | Extracted operation or event type. |
| `canonical_fields.payload_type` | Runtime payload type after extraction. |
| `canonical_fields.payload_sha256` | SHA-256 hash of the extracted runtime payload. |
| `field_sources` | JSON paths and matched keys used to extract each canonical field. |
| `missing_fields` | Canonical fields that could not be extracted. Successful proof runs should have an empty list. |

## Evidence Bundle

`evidence_bundle.json` is the primary entry point.

| Field | Meaning |
| --- | --- |
| `payload_reference` | Reference and SHA-256 hash for raw `input.json`. |
| `artifact_reference` | Run directory name relative to the output root. |
| `replay_reference` | Deterministic replay identifier. |
| `execution_status` | `success` when required canonical fields were present after extraction; otherwise `failed`. |
| `confidence` | Runtime readiness score between `0` and `1`. |
| `producer` | Producer name, version, and entrypoint. |
| `consumer_compatibility` | Consumer contract and whether the package is self-contained. |
| `artifacts` | References and SHA-256 hashes for generated files. This is the main hash verification map. |
| `summary` | Same content as `execution_context`, provided for consumer compatibility. |

## Output Artifact

`output.json` is the runtime result generated from the extracted canonical payload.

| Field | Meaning |
| --- | --- |
| `case_id` | Case identifier used by the runtime. |
| `operation` | Operation executed by the runtime. |
| `execution_status` | Runtime status. |
| `normalization` | Normalization metadata copied from the extraction step. |
| `payload_digest` | SHA-256 hash of the extracted payload body. |
| `payload_field_count` | Number of top-level fields in the extracted payload when it is an object. |
| `signal_count` | Count of valid signal objects processed. |
| `ignored_signal_count` | Count of malformed signal items ignored by the runtime. |
| `blocker_count` | Count of blocker severity signals. |
| `warning_count` | Count of warning severity signals. |
| `readiness_score` | Numeric readiness score used as evidence confidence. |
| `governance_posture` | `ready_for_consumer_validation` or `needs_review`. |
| `missing_required_fields` | Runtime-required canonical fields that were still unavailable. |
| `observations` | Human-readable status observations from the runtime. |

## Artifact Relationships

The runtime data flow is:

```text
input.json
  -> canonical extraction
  -> runtime execution
  -> output.json
```

The generated bundles then describe that same run from different angles:

```text
evidence_bundle.json indexes files and hashes
lineage_bundle.json explains provenance
replay_bundle.json explains reproducibility
handover_bundle.json explains consumer handoff
```

Practical relationships:

| Relationship | Where to verify it |
| --- | --- |
| Raw input to evidence | `evidence_bundle.json.payload_reference.sha256` matches `input.json`. |
| Output to evidence | `evidence_bundle.json.artifacts.output.sha256` matches `output.json`. |
| Bundle index to files | `handover_bundle.json.bundle_index` lists the files a consumer should inspect. |
| Input, producer, output, consumer graph | `lineage_bundle.json.nodes` and `lineage_bundle.json.edges`. |
| Replay input to expected output | `replay_bundle.json.replay_inputs` and `replay_bundle.json.expected_outputs`. |

## Replay Process

Use `replay_bundle.json` to replay a run.

1. Open `replay_bundle.json`.
2. Confirm `replay_inputs[0].reference` is `input.json`.
3. Confirm `expected_outputs[0].reference` is `output.json`.
4. Run the command in `replay_command`.
5. Hash the replayed `output.json`.
6. Compare the hash to `expected_outputs[0].sha256`.

PowerShell hash example:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath "outputs\evidence_runs\<execution_id>\output.json"
```

Replay succeeds when the replayed output hash equals the expected output hash. The bundle timestamp may change when regenerated, but deterministic identifiers and runtime output remain based on the extracted canonical input.

## Lineage Process

Use `lineage_bundle.json` to reconstruct provenance.

1. Open `lineage_bundle.json`.
2. Read `nodes`.
3. Read `edges`.
4. Read `provenance_chain`.
5. Confirm the path below exists.

Expected lineage path:

```text
input_payload --consumed_by--> runtime_processor
runtime_processor --produced--> runtime_output
runtime_output --available_to--> governance_consumer
```

Field meanings:

| Field | Meaning |
| --- | --- |
| `lineage_reference` | Deterministic lineage identifier for the run. |
| `nodes[].id` | Stable local node name, such as `input_payload` or `runtime_processor`. |
| `nodes[].type` | Node category: payload, producer, artifact, or consumer. |
| `nodes[].reference` | File reference for artifact-backed nodes. |
| `nodes[].sha256` | Hash for artifact-backed nodes. |
| `edges[].from` | Source node ID. |
| `edges[].to` | Target node ID. |
| `edges[].relationship` | Relationship type between nodes. |
| `provenance_chain[].step` | Ordered execution step. |
| `provenance_chain[].actor` | System or producer responsible for the step. |
| `provenance_chain[].action` | Action performed at that step. |
| `provenance_chain[].artifact` | File produced or used at that step. |

## Developer Read Path

For a new run container, use this order:

1. `evidence_bundle.json` for status, versions, hashes, and file references.
2. `input_extraction` inside any bundle to understand how raw input became canonical.
3. `output.json` to inspect the actual runtime result.
4. `lineage_bundle.json` to reconstruct provenance.
5. `replay_bundle.json` to reproduce the output hash.
6. `handover_bundle.json` to see consumer instructions and readiness.
7. `execution.log` for a compact human execution trail.

## Success Criteria

Use this checklist to decide whether a generated package satisfies the assignment.

| Criterion | How it is satisfied |
| --- | --- |
| A runtime execution produces a complete evidence package. | Each run directory contains `input.json`, `output.json`, `evidence_bundle.json`, `lineage_bundle.json`, `replay_bundle.json`, `handover_bundle.json`, and `execution.log`. |
| Ansh can consume the package without modifying it. | `evidence_bundle.json.consumer_compatibility.self_contained` is `true`, `handover_bundle.json.bundle_index` names every artifact, and all artifact references are local to the run container. |
| A new developer can reconstruct the execution path using only the generated artifacts. | `execution_context`, `input_extraction`, `output.json`, `execution.log`, and the lineage/replay bundles explain the path from raw input to output. |
| Replay reconstruction is possible. | `replay_bundle.json` contains `replay_command`, `replay_inputs`, `expected_outputs`, deterministic assumptions, and runtime requirements. |
| Lineage reconstruction is possible. | `lineage_bundle.json` contains nodes, edges, and provenance chain for `input_payload -> runtime_processor -> runtime_output -> governance_consumer`. |
| Governance validation can be performed using the generated evidence. | `evidence_bundle.json` contains contract/schema versions, execution status, confidence, consumer compatibility, artifact hashes, execution context, and input extraction details. |

The command below validates these criteria structurally for every run container.

## Protocol Alignment

| Protocol concept | Implementation |
| --- | --- |
| Event sourcing | The run container preserves the input event, produced output, ordered provenance actions, and execution log. This is an evidence-level event trail for replay and audit, not a full append-only application event store. |
| Execution lineage | `lineage_bundle.json` models the path from `input_payload` to `runtime_processor` to `runtime_output` to `governance_consumer`. |
| Trace propagation | The same `execution_id`, `trace_id`, contract, schema, timestamp, source, and target are propagated through every required bundle. |
| Replay systems | `replay_bundle.json` records the replay command, input reference/hash, expected output reference/hash, determinism rules, and runtime requirements. |
| Audit artifacts | `evidence_bundle.json.artifacts` and `execution.log` provide local hashes and run facts for governance validation. |
| Provenance chains | `lineage_bundle.json.provenance_chain` records ordered actions for submission, execution, and evidence generation. |

## Validation Commands

Generate the required 10-run proof set:

```bash
python runtime_evidence_producer.py demo --count 10 --out outputs/evidence_runs
```

Validate the generated containers:

```bash
python runtime_evidence_producer.py validate --root outputs/evidence_runs --min-runs 10
```

Run the unit tests:

```bash
python -m unittest discover -s tests
```

