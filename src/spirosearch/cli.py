from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from spirosearch.contracts import (
    EXIT_INTERNAL_ERROR,
    EXIT_LOCAL_TRACE_ERROR,
    EXIT_PATH_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
)
from spirosearch.enrichment_runtime import run_enrichment
from spirosearch.pipeline import load_candidates, run_screening, write_report, write_report_directory
from spirosearch.traceability import LocalPaperTraceError
from spirosearch.validation import ValidationFailure, write_validation_errors
from spirosearch.v4_runtime import run_v4_round


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "v4-round":
        return _main_v4_round(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "enrich":
        return _main_enrich(sys.argv[2:])
    return _main_screening()


def _main_screening() -> int:
    parser = argparse.ArgumentParser(description="Run Spiro replacement HTL screening.")
    parser.add_argument("--candidates", required=True, help="Path to candidate JSON list.")
    parser.add_argument(
        "--local-paper",
        default="pdf/extracted_text.txt",
        help="Path to local extracted text for the AI-guided perovskite paper.",
    )
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", help="Path to machine-readable JSON report.")
    destination.add_argument("--output-dir", help="Directory for JSON, Markdown, evidence, and manifest artifacts.")
    args = parser.parse_args()

    try:
        candidates = load_candidates(args.candidates)
        report = run_screening(candidates, args.local_paper)
        if args.output_dir:
            output_path = write_report_directory(report, args.output_dir)
            print(
                "Spiro replacement screening report directory "
                f"written to {output_path} "
                f"({report['summary']['candidate_count']} candidates, "
                f"{report['summary']['pareto_frontier_count']} Pareto-frontier candidates)."
            )
        else:
            output_path = write_report(report, args.output)
            print(
                "Spiro replacement screening report "
                f"written to {output_path} "
                f"({report['summary']['candidate_count']} candidates, "
                f"{report['summary']['pareto_frontier_count']} Pareto-frontier candidates)."
            )
        return EXIT_SUCCESS
    except ValidationFailure as exc:
        error_dir = _error_output_dir(args.output_dir, args.output)
        if error_dir is not None:
            write_validation_errors(exc.errors, error_dir)
        print(f"validation failed: {len(exc.errors)} error(s)", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    except LocalPaperTraceError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_LOCAL_TRACE_ERROR
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"input/output path error: {exc}", file=sys.stderr)
        return EXIT_PATH_ERROR
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


def _main_v4_round(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run one V4 autonomous screening round.")
    parser.add_argument("--candidates", required=True, help="Path to candidate JSON list.")
    parser.add_argument("--output-dir", required=True, help="Directory for V4 runtime artifacts.")
    parser.add_argument("--ledger", help="Existing V4 ledger JSONL path.")
    parser.add_argument("--posterior", help="Existing V4 posterior JSON path.")
    parser.add_argument("--observations", help="Experiment observations JSON array path.")
    parser.add_argument("--batch-size", type=int, default=1, help="Maximum recommendation count.")
    parser.add_argument("--budget", type=float, default=100.0, help="Maximum batch budget.")
    parser.add_argument("--model-version", default="bo-v1", help="V4 model version.")
    parser.add_argument(
        "--acquisition-strategy",
        default="ucb",
        choices=("heuristic", "ucb", "ei", "qehvi", "qnehvi"),
        help="Acquisition strategy.",
    )
    args = parser.parse_args(argv)

    try:
        manifest = run_v4_round(
            candidates_path=args.candidates,
            output_dir=args.output_dir,
            ledger_path=args.ledger,
            posterior_path=args.posterior,
            observations_path=args.observations,
            batch_size=args.batch_size,
            budget=args.budget,
            model_version=args.model_version,
            acquisition_config={"strategy": args.acquisition_strategy},
        )
        print(
            "V4 autonomous screening round "
            f"written to {args.output_dir} "
            f"({manifest['run_id']}, {manifest['batch_size']} requested batch size)."
        )
        return EXIT_SUCCESS
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"input/output path error: {exc}", file=sys.stderr)
        return EXIT_PATH_ERROR
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


def _main_enrich(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run local-first candidate data enrichment.")
    parser.add_argument("--candidates", required=True, help="Path to candidate JSON list.")
    parser.add_argument("--output-dir", required=True, help="Directory for enrichment artifacts.")
    parser.add_argument(
        "--source-registry",
        default="data/source_registry.json",
        help="Path to trusted source registry JSON.",
    )
    parser.add_argument(
        "--provider-cache",
        help="Optional provider cache JSONL path. Defaults to output-dir/provider-cache.jsonl.",
    )
    args = parser.parse_args(argv)

    try:
        manifest = run_enrichment(
            candidates_path=args.candidates,
            output_dir=args.output_dir,
            source_registry_path=args.source_registry,
            provider_cache_path=args.provider_cache,
        )
        print(
            "V6 local-first enrichment artifacts "
            f"written to {args.output_dir} "
            f"({manifest['run_id']}, {manifest['candidate_count']} candidates)."
        )
        return EXIT_SUCCESS
    except ValidationFailure as exc:
        write_validation_errors(exc.errors, args.output_dir)
        print(f"validation failed: {len(exc.errors)} error(s)", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"input/output path error: {exc}", file=sys.stderr)
        return EXIT_PATH_ERROR
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


def _error_output_dir(output_dir: str | None, output: str | None) -> Path | None:
    if output_dir:
        return Path(output_dir)
    if output:
        return Path(output).parent
    return None


if __name__ == "__main__":
    raise SystemExit(main())
