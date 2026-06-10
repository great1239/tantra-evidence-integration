"""CLI entrypoint for producing SHAKTI runtime evidence bundles."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys

from runtime_evidence.canonical import canonical_json
from runtime_evidence.producer import produce_evidence_run, validate_evidence_root, write_json
from runtime_evidence.reference_runtime import demo_payloads


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Produce deterministic runtime evidence bundles.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Generate evidence for one input payload.")
    run_parser.add_argument("--input", required=True, type=Path, help="Path to input JSON payload.")
    run_parser.add_argument("--out", default=Path("outputs/evidence_runs"), type=Path, help="Output root.")

    demo_parser = subparsers.add_parser("demo", help="Generate a multi-run proof set.")
    demo_parser.add_argument("--count", default=10, type=int, help="Number of executions to generate.")
    demo_parser.add_argument("--inputs", default=Path("sample_inputs"), type=Path, help="Directory for generated inputs.")
    demo_parser.add_argument("--out", default=Path("outputs/evidence_runs"), type=Path, help="Output root.")

    validate_parser = subparsers.add_parser("validate", help="Validate generated evidence bundles.")
    validate_parser.add_argument("--root", default=Path("outputs/evidence_runs"), type=Path, help="Evidence run root.")
    validate_parser.add_argument("--min-runs", default=10, type=int, help="Minimum required run count.")

    return parser


def run_command(input_path: Path, output_root: Path) -> int:
    run_dir = produce_evidence_run(input_path, output_root)
    print(f"generated {run_dir.as_posix()}")
    return 0


def demo_command(count: int, inputs_root: Path, output_root: Path) -> int:
    inputs_root.mkdir(parents=True, exist_ok=True)
    for index, payload in enumerate(demo_payloads(count), start=1):
        input_path = inputs_root / f"runtime-proof-{index:03d}.json"
        write_json(input_path, payload)
        produce_evidence_run(input_path, output_root)
    print(canonical_json({"generated_runs": count, "output_root": output_root.as_posix()}))
    return 0


def validate_command(root: Path, min_runs: int) -> int:
    run_count, errors = validate_evidence_root(root)
    if run_count < min_runs:
        errors.append(f"expected at least {min_runs} run directories, found {run_count}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(canonical_json({"validated_runs": run_count, "status": "ok"}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args.input, args.out)
    if args.command == "demo":
        return demo_command(args.count, args.inputs, args.out)
    if args.command == "validate":
        return validate_command(args.root, args.min_runs)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
