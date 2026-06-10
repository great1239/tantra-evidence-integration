# Edge Cases and Failures

This file is the single source of truth for edge-case behavior and failure handling in the runtime evidence producer.

## Edge Case Behavior

| Edge case | System reaction | Evidence result |
| --- | --- | --- |
| Canonical input with all required fields | Uses the input as-is. | `execution_status` is based on runtime result; normal proof bundles are produced. |
| Noncanonical input with extractable aliases | Extracts canonical fields and writes raw submitted input to `input.json`; extraction details are recorded in bundle `input_extraction`. | Successful when all required fields are extracted. |
| Nested metadata/event input | Searches nested objects for aliases such as `metadata.caseId`, `metadata.sourceSystem`, `event.type`, and `event.body`. | Successful when all required fields are extracted. |
| Missing `case_id`, `source_system`, `target_system`, or `operation` after extraction | Records impossible-to-extract fields in `_normalization.missing_fields`. | Bundles are still produced; `output.json.execution_status` is `failed`. |
| Missing `payload` after extraction | Derives `payload` from the remaining raw input when possible. | Usually still produces an evidence package; missing payload is recorded only if derivation is impossible. |
| Valid JSON scalar without recognizable evidence details, such as `"raw text payload"` or a number | Wraps the raw scalar as `payload`; canonical fields are recorded missing only after text extraction fails. | Bundles are produced with `execution_status: failed` and missing scalar fields. |
| JSON string containing recognizable plain English evidence details | Extracts canonical fields using deterministic text patterns before missing-field fallback. | Successful when case, source, target, and operation are present in the text. |
| Raw `.txt` file containing recognizable plain English evidence details | Reads the file as text, writes the text to `input.json`, and extracts canonical fields using deterministic text patterns. | Successful when case, source, target, and operation are present in the text. |
| Plain text with no recognizable case/source/target/operation details | Preserves the text as payload and records only impossible-to-extract fields as missing. | Bundles are produced with `execution_status: failed`. |
| Valid top-level JSON array | Searches items for aliases; if no aliases exist, the array becomes `payload`. | Successful only if required scalar fields are extracted somewhere in the array. |
| Duplicate aliases for the same field | Chooses the best match by exact canonical key first, then shallower and more stable paths. | Bundle `input_extraction.field_sources` records the chosen source. |
| Null scalar alias, such as `"case_id": null` in noncanonical input | Null is not treated as an extractable scalar. | Field remains missing unless another alias provides it. |
| Non-scalar value for scalar fields, such as `"case_id": {}` | Non-scalar values are ignored for scalar canonical fields. | Field remains missing unless another alias provides it. |
| `payload.signals` is absent | Runtime treats signals as an empty list. | Successful if required canonical fields exist. |
| `payload.signals` is not a list | Runtime ignores it and uses an empty signal list. | Successful if required canonical fields exist. |
| `payload.signals` contains non-object items | Runtime ignores non-object signal items and records `ignored_signal_count` in `output.json`. | Successful if required canonical fields exist. |
| Signal severity is `warning` | Reduces `confidence` by `0.1` per warning. | Bundle remains successful unless required fields are missing. |
| Signal severity is `blocker` | Reduces `confidence` by `0.35` per blocker. | Bundle remains successful unless required fields are missing; posture may require review. |
| Invalid JSON file that is readable as text | Treats the file as raw text input and attempts text extraction. | Bundles are produced; success depends on whether required fields can be extracted from the text. |
| Input file path does not exist | File read fails. | No evidence package is produced; the CLI exits with an error. |
| Output root does not exist during validation | Validator reports the missing root. | Validation fails. |
| Required bundle file missing | Validator reports the missing file. | Validation fails. |
| Artifact hash mismatch | Validator reports the mismatched artifact. | Validation fails. |
| Extra files in a run directory | Validator ignores unrelated extra files. | Validation can still pass; assignment handoff should keep exact required filenames. |
| Timestamp changes between replays | Timestamp is excluded from deterministic ID generation. | Replay identity remains based on canonical input/output, not timestamp. |
| Same normalized input rerun | Produces the same `execution_id` and `trace_id`. | Replayable if `output.json` hash matches `expected_outputs[0].sha256`. |

## Failure Cases

| Failure case | Evidence package produced? | Where the failure is recorded | Consumer action |
| --- | --- | --- | --- |
| Required canonical input fields cannot be extracted | Yes | Bundle `input_extraction.missing_fields`, `output.json.missing_required_fields`, `evidence_bundle.json.execution_status` | Treat as a failed execution package and inspect missing fields. |
| Valid JSON scalar or array lacks extractable canonical fields | Yes | Bundle `input_extraction`, `output.json.missing_required_fields` | Treat as failed unless the missing fields are acceptable for a future adapter. |
| Input file is missing | No | CLI error before `input.json` is written | Fix the path and rerun. |
| Input file is unreadable | No | File read error before normalization | Fix permissions or path and rerun. |
| Text input lacks extractable canonical fields | Yes | Bundle `input_extraction.missing_fields`, `output.json.missing_required_fields` | Treat as failed unless the missing fields are acceptable for a future adapter. |
| Runtime payload contains malformed `signals` | Yes | `output.json.ignored_signal_count` when non-object signal items are ignored | Review ignored count; package can still be consumed if execution status is `success`. |
| Required bundle file is missing | Existing package is incomplete | Validator output | Regenerate the evidence package. |
| Required evidence field is missing | Existing package is invalid | Validator output | Regenerate or fix producer logic. |
| Artifact hash mismatch | Existing package is invalid | Validator output | Do not consume; regenerate from source input. |
| Replay output hash mismatch | Existing package is not replay-equivalent | Manual replay comparison or consumer replay check | Investigate runtime drift before accepting. |
| Unsupported `contract_version` or `schema_version` | Package may be well formed but incompatible | `evidence_bundle.json` | Consumer should reject or route to a compatible adapter. |

## Failure Categories

- Pre-generation failures: missing or unreadable input file. No evidence package is produced.
- Runtime evidence failures: valid JSON is processed, but required canonical fields remain missing. A failed evidence package is produced.
- Validation failures: package exists, but required files, required fields, or hashes do not match.
- Replay failures: package validates structurally, but replayed output hash differs from the expected output hash.
- Compatibility failures: package uses an unsupported contract or schema version.

## Handling Summary

- Failed execution with bundles present: inspect `output.json.missing_required_fields`, bundle `input_extraction`, and `execution.log`.
- CLI failure before bundle generation: fix the input file path or file readability and rerun.
- Validation failure: regenerate the package from the source input before consumer ingestion.
- Replay failure: compare the replayed `output.json` hash to `replay_bundle.json.expected_outputs[0].sha256` and investigate runtime drift.
- Version mismatch: reject the package unless the consumer explicitly supports the reported `contract_version` and `schema_version`.
