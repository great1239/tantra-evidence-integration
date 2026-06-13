# TANTRA Evidence Integration

This repository contains the TANTRA operational chain for consuming, validating, propagating, registering, converging, and reconstructing runtime evidence.

The evidence generator from the previous assignment is intentionally retained as upstream infrastructure so the integration can be reproduced end to end. The new assignment work starts at an existing evidence package and moves it through SHAKTI, MDU, and TMS.

Existing evidence packages contain:

- `evidence_bundle.json`
- `lineage_bundle.json`
- `replay_bundle.json`
- `handover_bundle.json`
- `input.json`
- `output.json`
- `execution.log`

## Quick Start

Primary assignment path: consume an existing evidence package through TANTRA.

```bash
python run_tantra_chain.py --evidence outputs/evidence_runs/exec_709063d750fe9fbb4618/evidence_bundle.json --out .
```

Optional demo path: create a sample evidence package first using the existing upstream producer, then consume it through TANTRA.

```bash
python run_tantra_chain.py --input sample_inputs/runtime-proof-010.json --evidence-out outputs/evidence_runs --out .
```

Generate the required 10-run proof set:

```bash
python runtime_evidence_producer.py demo --count 10 --out outputs/evidence_runs
```

Validate the generated bundles:

```bash
python runtime_evidence_producer.py validate --root outputs/evidence_runs --min-runs 10
```

Generate one bundle from an input payload:

```bash
python runtime_evidence_producer.py run --input sample_inputs/runtime-proof-001.json --out outputs/evidence_runs
```

Inputs are normalized before execution. Canonical fields are extracted from common aliases such as `id`, `caseId`, `from`, `to`, `action`, `type`, `data`, and `body`. The producer also extracts fields from schema-free plain English text when it contains recognizable case, source, target, and operation details. Missing fields are recorded only when extraction is impossible. Generated proof `input.json` files preserve the raw/mangled submitted input, while each bundle records extraction details in `input_extraction`.

## Assignment Boundary

This submission does not introduce a new evidence format. The retained producer files are there to regenerate sample evidence and keep Phase 5/Phase 6 reproducible. The TANTRA integration layer is:

- `shakti_consumer_adapter.py`
- `lineage_registration.py`
- `tms_convergence_emitter.py`
- `run_tantra_chain.py`
- generated governance, lineage, convergence, and proof artifacts

## Developer Handoff

Start with `DEVELOPER_BUNDLE_GUIDE.md` when reviewing the generated containers. It explains the bundle structure, field meanings, artifact relationships, replay process, and lineage process in one place.

## Architecture

- `runtime_evidence_producer.py` is the upstream evidence CLI retained for reproducibility.
- `runtime_evidence/canonical.py` owns canonical JSON, SHA-256 hashing, timestamps, schema versions, and deterministic IDs.
- `runtime_evidence/reference_runtime.py` provides the local execution path used to produce real runtime outputs in this otherwise empty repository.
- `runtime_evidence/producer.py` writes the upstream evidence, lineage, replay, and handover bundles and validates generated artifacts.
- `shakti_consumer_adapter.py` consumes existing evidence bundles and emits deterministic SHAKTI governance outputs.
- `lineage_registration.py` registers SHAKTI-validated evidence lineage for MDU reconstruction.
- `tms_convergence_emitter.py` emits TMS convergence status from validation and lineage records.
- `run_tantra_chain.py` runs the operational chain from an existing evidence package to convergence. Its `--input` mode is only a sample bootstrap path that calls the existing producer first.

## Determinism

Execution IDs, trace IDs, lineage references, handover references, and replay references are generated from stable canonical JSON hashes. Runtime timestamps are real execution times and are deliberately excluded from identifier generation.

