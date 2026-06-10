# Runtime Evidence Producer

This repository contains a deterministic runtime evidence producer for the GC Governance SHAKTI convergence handoff.

The producer generates a self-contained evidence package for each execution:

- `evidence_bundle.json`
- `lineage_bundle.json`
- `replay_bundle.json`
- `handover_bundle.json`
- `input.json`
- `output.json`
- `execution.log`

## Quick Start

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

Inputs are normalized before execution. Canonical fields are extracted from common aliases such as `id`, `caseId`, `from`, `to`, `action`, `type`, `data`, and `body`; missing fields are recorded only when extraction is impossible. Generated proof `input.json` files preserve the raw/mangled submitted input, while each bundle records extraction details in `input_extraction`.

## Developer Handoff

Start with `DEVELOPER_BUNDLE_GUIDE.md` when reviewing the generated containers. It explains the bundle structure, field meanings, artifact relationships, replay process, and lineage process in one place.

## Architecture

- `runtime_evidence_producer.py` is the CLI entrypoint.
- `runtime_evidence/canonical.py` owns canonical JSON, SHA-256 hashing, timestamps, schema versions, and deterministic IDs.
- `runtime_evidence/reference_runtime.py` provides the local execution path used to produce real runtime outputs in this otherwise empty repository.
- `runtime_evidence/producer.py` writes the evidence, lineage, replay, and handover bundles and validates generated artifacts.

## Determinism

Execution IDs, trace IDs, lineage references, handover references, and replay references are generated from stable canonical JSON hashes. Runtime timestamps are real execution times and are deliberately excluded from identifier generation.

