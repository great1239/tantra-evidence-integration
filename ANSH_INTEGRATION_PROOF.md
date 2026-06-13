# Ansh Integration Proof

## SHAKTI Contract

The adapter validates the repository's available Ansh-facing SHAKTI contract: `shakti-runtime-evidence/v1` with schema `1.0.0`. The contract constants live in `runtime_evidence/canonical.py`; the canonical evidence schema lives in `schemas/canonical_evidence_schema.json`.

## Phase 6 Execution

```json
{"input_mode":"generated_sample_evidence","lineage_registration":"lineage_registration.json","sample_input":"sample_inputs/runtime-proof-010.json","source_evidence":"outputs/evidence_runs/exec_709063d750fe9fbb4618/evidence_bundle.json","tms_convergence_status":"tms_convergence_status.json","validation_decision":"validation_decision.json"}
```

## SHAKTI Validation

```json
{"decision":"APPROVED","decision_id":"validation_decision_31b41e7df3701143e179","governance_status":"VALIDATED","reason_codes":[],"trace_id":"trace_b996d7b5e3d19d0967f0"}
```

## MDU And TMS Result

```json
{"mdu_registration":"REGISTERED","mdu_registration_id":"mdu_registration_04cc65c006d2bf0b0ef3","tms_reason_codes":[],"tms_status":"CONVERGED","trace_id":"trace_b996d7b5e3d19d0967f0"}
```

## Integration Boundary

No separate Ansh SHAKTI runtime or remote API is present in this repository. The integration seam is `shakti_consumer_adapter.consume_evidence(...)`; when Ansh provides a concrete contract module or endpoint, this adapter should call that interface without changing the evidence format.

## End-To-End Result

```json
{"decision":"APPROVED","mdu_registration":"REGISTERED","tms_status":"CONVERGED","trace_id":"trace_b996d7b5e3d19d0967f0"}
```

## Reconstruction

Lineage is reconstructable: `True`.
