# Evidence Specification

## Contract

- Contract version: `shakti-runtime-evidence/v1`
- Schema version: `1.0.0`
- Canonical evidence schema: `schemas/canonical_evidence_schema.json`
- Producer entrypoint: `operational_drift_monitor.py`
- Default output root: `outputs/evidence_runs`

Each execution directory is named by deterministic `execution_id` and contains the complete evidence package for that run.

## Bundle Structure

Each execution directory contains exactly:

- `evidence_bundle.json`: canonical execution summary and consumer compatibility surface.
- `lineage_bundle.json`: provenance graph and ordered lineage chain.
- `replay_bundle.json`: replay command, replay inputs, expected outputs, and determinism rules.
- `handover_bundle.json`: bundle index, consumer instructions, known limitations, and readiness.
- `input.json`: raw submitted input payload. Demo proof inputs are intentionally noncanonical/mangled to demonstrate extraction.
- `output.json`: exact output produced by the runtime.
- `execution.log`: plain-text execution trail.

## Phase 2 Execution Context

Every required bundle includes `execution_context` so the Phase 2 questions are answered directly in each file:

- `what_happened`: operation and status.
- `where_it_happened`: runtime/evidence producer location.
- `when_it_happened`: bundle generation timestamp.
- `what_produced_it`: executable entrypoint that produced the evidence.
- `what_consumed_it`: intended governance consumer.
- `what_can_be_replayed`: replayable artifact and replay command location.

Every required bundle also includes `input_extraction` so a consumer can see how `input.json` was converted into canonical runtime fields:

- `input_reference`: always `input.json`.
- `input_shape`: `already_canonical` or `noncanonical_extracted`.
- `raw_input_sha256`: SHA-256 of the submitted raw input object.
- `raw_input_type`: JSON type of the submitted input.
- `canonical_fields`: extracted `case_id`, `source_system`, `target_system`, `operation`, payload type, and payload hash.
- `field_sources`: raw JSON paths used for extraction.
- `missing_fields`: canonical fields that could not be extracted.

## Field Meanings

Every `evidence_bundle.json` includes:

- `execution_id`: deterministic execution identifier, formatted as `exec_<20 hex chars>`.
- `trace_id`: deterministic trace identifier shared across the bundles for the same run.
- `contract_version`: evidence contract identifier expected by the consumer.
- `schema_version`: current evidence format version.
- `timestamp`: UTC timestamp for when the bundle was generated.
- `source_system`: system that submitted or represents the input.
- `target_system`: intended governance consumer.
- `payload_reference`: reference and SHA-256 hash for the raw submitted `input.json`.
- `artifact_reference`: execution directory name relative to the output root.
- `replay_reference`: deterministic replay identifier.
- `execution_status`: `success` or `failed`.
- `confidence`: runtime confidence/readiness score between `0` and `1`.
- `producer`: name, version, and entrypoint of the evidence producer.
- `consumer_compatibility`: consumer contract and self-contained status.
- `artifacts`: references and SHA-256 hashes for generated artifacts.
- `summary`: human-readable statement of what happened, where, producer, consumer, and replayability.
- `execution_context`: direct answers to the Phase 2 bundle clarity questions.
- `input_extraction`: extraction report for raw/mangled input.

The canonical schema requires these fields for every execution:

- `execution_id`
- `trace_id`
- `contract_version`
- `schema_version`
- `timestamp`
- `source_system`
- `target_system`
- `payload_reference`
- `artifact_reference`
- `replay_reference`
- `execution_status`
- `confidence`

## Input Normalization

The preferred input shape is:

```json
{
  "case_id": "runtime-proof-001",
  "source_system": "GC_RUNTIME_EVIDENCE_PRODUCER",
  "target_system": "SHAKTI_GOVERNANCE_CONSUMER",
  "operation": "evidence_standardization",
  "payload": {}
}
```

If the submitted JSON does not follow this shape, the producer attempts to extract the canonical fields before execution.

Supported extraction aliases include:

- `case_id`: `case_id`, `caseId`, `id`, `run_id`, `request_id`, `record_id`, `ticket_id`, `execution_id`
- `source_system`: `source_system`, `sourceSystem`, `source`, `src`, `from`, `origin`, `producer`, `submitted_by`
- `target_system`: `target_system`, `targetSystem`, `target`, `destination`, `dst`, `to`, `consumer`, `recipient`
- `operation`: `operation`, `op`, `action`, `event_type`, `eventType`, `type`, `task`, `workflow`, `intent`, `command`
- `payload`: `payload`, `data`, `body`, `content`, `request`, `input`, `event`, `record`, `message`, `values`, `attributes`

The extractor searches top-level fields and nested objects such as `metadata`, `meta`, `context`, `headers`, `envelope`, `request`, `event`, `execution`, and `systems`.

If a field cannot be extracted, it is listed in `input_extraction.missing_fields` in each bundle. Missing fields are used only after extraction fails.

## Bundle Formats

`lineage_bundle.json` contains:

- common identifiers: `execution_id`, `trace_id`, `contract_version`, `schema_version`, `timestamp`, `source_system`, `target_system`
- `execution_context`
- `input_extraction`
- `lineage_reference`
- `nodes`
- `edges`
- `provenance_chain`

`replay_bundle.json` contains:

- common identifiers
- `execution_context`
- `input_extraction`
- `replay_reference`
- `replay_command`
- `replay_inputs`
- `expected_outputs`
- `determinism`
- `runtime_requirements`

`handover_bundle.json` contains:

- common identifiers
- `execution_context`
- `input_extraction`
- `handover_reference`
- `bundle_index`
- `consumer_instructions`
- `known_limitations`
- `integration_readiness`

## Artifact Relationships

The runtime data flow is:

```text
input.json
  -> canonical extraction
  -> runtime execution
  -> output.json
```

The generated bundles describe the same run from different angles:

- `evidence_bundle.json` references every generated artifact through the `artifacts` object.
- `handover_bundle.json` indexes the same files for consumers.
- `lineage_bundle.json` explains how the input, producer, output, and consumer relate.
- `replay_bundle.json` explains how to reconstruct the output.

## Hashing and IDs

All JSON is serialized with sorted keys and compact separators before hashing. Generated JSON files are written with sorted keys and indentation for human review.

IDs use SHA-256 prefixes:

- `exec_<20 hex chars>`
- `trace_<20 hex chars>`
- `lineage_<20 hex chars>`
- `replay_<20 hex chars>`
- `handover_<20 hex chars>`

No `uuid4` or random generation is used.

## Replay Reconstruction

Replay reconstruction uses `replay_bundle.json`:

1. Use `replay_inputs[0].reference` to locate `input.json`.
2. Run `replay_command`.
3. Hash the replayed `output.json` using SHA-256.
4. Compare the result to `expected_outputs[0].sha256`.

Replay is valid when the hashes match.

## Lineage Reconstruction

Lineage reconstruction uses `lineage_bundle.json`:

1. Read `nodes` to identify payload, producer, output artifact, and consumer.
2. Read `edges` to reconstruct relationships between nodes.
3. Read `provenance_chain` to reconstruct execution order.

The expected path is:

```text
input_payload consumed_by runtime_processor
runtime_processor produced runtime_output
runtime_output available_to governance_consumer
```

The public formats are documented in this file using the exact bundle filenames required by the assignment.
