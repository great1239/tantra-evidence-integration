# TANTRA Chain Proof

## Operational Chain

`Input Payload -> Evidence Generation -> SHAKTI Validation -> MDU Registration -> TMS Convergence`

## Input Mode

```json
{"input_mode":"generated_sample_evidence","sample_input":"sample_inputs/runtime-proof-010.json","source_evidence":"outputs/evidence_runs/exec_709063d750fe9fbb4618/evidence_bundle.json"}
```

## One Trace

```json
{"chain_id":"tantra_chain_2df59275e834788ed8da","execution_id":"exec_709063d750fe9fbb4618","trace_id":"trace_b996d7b5e3d19d0967f0"}
```

## Replay Reconstruction

Replay metadata remains available through `outputs/evidence_runs/exec_709063d750fe9fbb4618/replay_bundle.json`.

## Lineage Reconstruction

Use `lineage_chain.json.chain_steps` to reconstruct `input_artifact -> evidence_bundle -> governance_record -> consumer_registration -> mdu_registration`.
