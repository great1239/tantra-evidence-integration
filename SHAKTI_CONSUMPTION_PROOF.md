# SHAKTI Consumption Proof

## Flow

`evidence_bundle.json -> SHAKTI Consumer Adapter -> validation_decision.json`

## Consumer Responsibility

The adapter treats evidence generation as upstream. It consumes the existing bundle, verifies required schema fields, validates contract and schema versions, recomputes artifact hashes, checks replay metadata, and emits a deterministic governance decision.

## Validation Decision

```json
{"decision":"APPROVED","decision_id":"validation_decision_31b41e7df3701143e179","reason_codes":[],"trace_id":"trace_b996d7b5e3d19d0967f0"}
```

## Checks

24 deterministic checks were executed. Failed checks: 0.

## Failure Surface

Unsupported contract versions, missing canonical evidence fields, artifact hash mismatches, failed execution status, low confidence, non-self-contained bundles, and incomplete replay metadata produce `REJECTED`.
