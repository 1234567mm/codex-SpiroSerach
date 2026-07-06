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
from spirosearch.pipeline import load_candidates, run_screening, write_report, write_report_directory
from spirosearch.traceability import LocalPaperTraceError
from spirosearch.validation import ValidationFailure, write_validation_errors


def main() -> int:
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


def _error_output_dir(output_dir: str | None, output: str | None) -> Path | None:
    if output_dir:
        return Path(output_dir)
    if output:
        return Path(output).parent
    return None


if __name__ == "__main__":
    raise SystemExit(main())
