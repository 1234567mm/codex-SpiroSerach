from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.acquisition_replay import evaluate_offline_replay, validated_replay_status
from spirosearch.artifacts import build_run_manifest, write_json_artifact, write_jsonl_artifact
from spirosearch.beard_cole_training import build_beard_cole_training_snapshot
from spirosearch.contracts import (
    EXIT_INTERNAL_ERROR,
    EXIT_LOCAL_TRACE_ERROR,
    EXIT_PATH_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
)
from spirosearch.enrichment_runtime import run_enrichment
from spirosearch.paper_ingest import run_paper_ingest
from spirosearch.pipeline import load_candidates, run_screening, write_report, write_report_directory
from spirosearch.public_device_baseline import build_public_device_snapshot
from spirosearch.model_evaluation import evaluate_grouped_snapshot
from spirosearch.prediction_dataset import training_snapshot_from_dict
from spirosearch.surrogate import HeuristicSurrogate, SklearnSurrogate, UnsupportedSurrogateError
from spirosearch.traceability import LocalPaperTraceError
from spirosearch.validation import ValidationFailure, write_validation_errors
from spirosearch.v4_runtime import run_v4_round


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "v4-round":
        return _main_v4_round(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "enrich":
        return _main_enrich(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "validate-artifacts":
        return _main_validate_artifacts(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "dataset-import":
        return _main_dataset_import(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "beard-cole-import":
        return _main_beard_cole_import(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "model-evaluate":
        return _main_model_evaluate(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "acquisition-replay":
        return _main_acquisition_replay(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "paper-ingest":
        return _main_paper_ingest(sys.argv[2:])
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
    except (OSError, ValueError, json.JSONDecodeError):
        print("input/output path error", file=sys.stderr)
        return EXIT_PATH_ERROR
    except Exception:
        print("internal error", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


def _main_enrich(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run local-first candidate data enrichment.")
    parser.add_argument("--candidates", required=True, help="Path to candidate JSON list.")
    parser.add_argument("--output-dir", required=True, help="Directory for enrichment artifacts.")
    parser.add_argument(
        "--mode",
        default="offline-local",
        choices=("offline-local", "live-cache-first"),
        help="Enrichment execution mode. Default never calls live providers.",
    )
    parser.add_argument(
        "--providers",
        default="",
        help="Comma-separated live providers for live-cache-first mode.",
    )
    parser.add_argument(
        "--source-registry",
        default="data/source_registry.json",
        help="Path to trusted source registry JSON.",
    )
    parser.add_argument(
        "--provider-cache",
        help="Optional provider cache JSONL path. Defaults to output-dir/provider-cache.jsonl.",
    )
    parser.add_argument(
        "--review-events",
        help="Optional review events JSONL fixture path.",
    )
    args = parser.parse_args(argv)

    try:
        selected_providers = [item.strip() for item in args.providers.split(",") if item.strip()]
        manifest = run_enrichment(
            candidates_path=args.candidates,
            output_dir=args.output_dir,
            source_registry_path=args.source_registry,
            provider_cache_path=args.provider_cache,
            live=args.mode == "live-cache-first",
            providers=selected_providers,
            review_events_path=args.review_events,
        )
        display_mode = args.mode if args.mode == "live-cache-first" else "local-first"
        print(
            f"V6 {display_mode} enrichment artifacts "
            f"written to {args.output_dir} "
            f"({manifest['run_id']}, {manifest['candidate_count']} candidates)."
        )
        return EXIT_SUCCESS
    except ValidationFailure as exc:
        write_validation_errors(exc.errors, args.output_dir)
        print(f"validation failed: {len(exc.errors)} error(s)", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    except (OSError, ValueError, json.JSONDecodeError):
        print("input/output path error", file=sys.stderr)
        return EXIT_PATH_ERROR
    except Exception:
        print("internal error", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


def _main_validate_artifacts(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate a manifest-discovered artifact output directory.")
    parser.add_argument("--output-dir", required=True, help="Directory containing run-manifest.json and artifacts.")
    parser.add_argument("--output", help="Optional path to write the validation report JSON.")
    parser.add_argument(
        "--optional-artifact",
        action="append",
        default=[],
        metavar="KIND[=PANEL]",
        help="Optional artifact kind that should degrade locally when absent. May be repeated.",
    )
    args = parser.parse_args(argv)

    try:
        report = validate_artifact_run(
            args.output_dir,
            optional_artifacts=_parse_optional_artifacts(args.optional_artifact),
        )
        report_json = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report_json, encoding="utf-8")
        else:
            print(report_json, end="")
        return EXIT_SUCCESS if report.status in {"valid", "degraded"} else EXIT_VALIDATION_ERROR
    except (OSError, ValueError, json.JSONDecodeError):
        print("input/output path error", file=sys.stderr)
        return EXIT_PATH_ERROR
    except Exception:
        print("internal error", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


def _main_dataset_import(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build a verified offline public-device snapshot.")
    parser.add_argument("--source", required=True, help="Local source JSON downloaded from the declared public source.")
    parser.add_argument("--source-manifest", required=True, help="Source license and checksum manifest JSON.")
    parser.add_argument("--output", required=True, help="Path for the normalized snapshot JSON.")
    parser.add_argument("--max-records", type=int, default=24)
    parser.add_argument("--per-htl", type=int, default=2)
    args = parser.parse_args(argv)

    try:
        source_manifest = json.loads(Path(args.source_manifest).read_text(encoding="utf-8"))
        snapshot = build_public_device_snapshot(
            args.source,
            source_manifest,
            max_records=args.max_records,
            per_htl=args.per_htl,
        )
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError):
        print("dataset-import failed validation; verify the local source and source manifest", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    return EXIT_SUCCESS


def _main_beard_cole_import(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Import a local Beard/Cole PSC source into V17 artifacts.")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    try:
        source_path = Path(args.source_file)
        manifest_path = Path(args.source_manifest)
        raw_records = json.loads(source_path.read_text(encoding="utf-8"))
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        training = build_beard_cole_training_snapshot(raw_records, source_manifest)

        replay_report = evaluate_offline_replay(
            _beard_cole_replay_candidates(training.accepted_records),
            request_id="v17-beard-cole-replay",
            model_version="beard-cole-heuristic-v1",
            strategy="deterministic-pce-replay",
            batch_size=1,
        )
        evaluation = evaluate_grouped_snapshot(
            training.snapshot,
            objective_name="pce",
            model_factory=HeuristicSurrogate,
            model_version="beard-cole-heuristic-v1",
            surrogate_type="HEURISTIC",
            replay_status=replay_report["replay"]["status"],
            data_leakage_count=training.quality_report.fold_leakage_count,
            blocking_review_count=0,
        )

        output_dir = Path(args.output_dir)
        generated_at = datetime.now(UTC).isoformat()
        input_hash = _combined_file_hash((source_path, manifest_path))
        common = {
            "run_id": f"v17-beard-cole-{training.snapshot.content_sha256[:12]}",
            "input_hash": input_hash,
            "generated_at": generated_at,
            "producer_version": "spirosearch-v17",
        }
        artifacts = [
            write_jsonl_artifact(
                output_dir,
                "device-evidence.jsonl",
                [record.to_device_evidence().to_dict() for record in training.accepted_records],
                kind="device_evidence",
                **common,
            ),
            write_json_artifact(
                output_dir,
                "training-snapshot.json",
                training.snapshot.to_dict(),
                kind="training_snapshot",
                **common,
            ),
            write_json_artifact(
                output_dir,
                "data-quality-report.json",
                training.quality_report.to_dict(),
                kind="data_quality_report",
                **common,
            ),
            write_json_artifact(
                output_dir,
                "model-evaluation.json",
                evaluation.to_dict(),
                kind="model_evaluation",
                **common,
            ),
            write_json_artifact(
                output_dir,
                "acquisition-breakdown.json",
                replay_report,
                kind="acquisition_breakdown",
                **common,
            ),
        ]
        build_run_manifest(artifacts, **common).write_json(output_dir)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        print("beard-cole-import failed validation", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    return EXIT_SUCCESS


def _main_model_evaluate(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a model with grouped, fail-closed activation gates.")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--model", required=True, choices=("heuristic", "sklearn"))
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--replay-report", help="Validated acquisition-breakdown JSON from acquisition-replay.")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    factories = {"heuristic": HeuristicSurrogate, "sklearn": SklearnSurrogate}
    try:
        snapshot_payload = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        snapshot = training_snapshot_from_dict(snapshot_payload)
        replay_status = "unavailable"
        if args.replay_report:
            replay_payload = json.loads(Path(args.replay_report).read_text(encoding="utf-8"))
            replay_status = validated_replay_status(
                replay_payload, expected_model_version=args.model_version
            )
        evaluation = evaluate_grouped_snapshot(
            snapshot,
            objective_name=args.objective,
            model_factory=factories[args.model],
            model_version=args.model_version,
            surrogate_type="HEURISTIC" if args.model == "heuristic" else "SKLEARN_GPR",
            replay_status=replay_status,
        )
        output_dir = Path(args.output_dir)
        generated_at = datetime.now(UTC).isoformat()
        common = {
            "run_id": f"v13-model-{snapshot.content_sha256[:12]}",
            "input_hash": f"sha256:{snapshot.content_sha256}",
            "generated_at": generated_at,
            "producer_version": "spirosearch-v13",
        }
        artifacts = [
            write_json_artifact(
                output_dir,
                "training-snapshot.json",
                snapshot.to_dict(),
                kind="training_snapshot",
                **common,
            ),
            write_json_artifact(
                output_dir,
                "model-evaluation.json",
                evaluation.to_dict(),
                kind="model_evaluation",
                **common,
            ),
        ]
        build_run_manifest(artifacts, **common).write_json(output_dir)
    except (OSError, ValueError, json.JSONDecodeError, UnsupportedSurrogateError):
        print("model-evaluate failed validation or optional model availability", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    return EXIT_SUCCESS


def _beard_cole_replay_candidates(records) -> list[dict[str, float | str]]:
    return [
        {
            "candidate_id": record.source_row_id,
            "model_score": record.pce,
            "heuristic_score": record.active_area_cm2 or 0.0,
            "observed_utility": record.pce,
        }
        for record in records
    ]


def _combined_file_hash(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _main_acquisition_replay(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compare model and heuristic acquisition on observed outcomes.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        raw_input = Path(args.input).read_bytes()
        payload = json.loads(raw_input.decode("utf-8"))
        report = evaluate_offline_replay(
            payload["candidates"],
            request_id=payload["request_id"],
            model_version=payload["model_version"],
            strategy=payload["strategy"],
            batch_size=int(payload.get("batch_size", 1)),
        )
        output_dir = Path(args.output_dir)
        generated_at = datetime.now(UTC).isoformat()
        common = {
            "run_id": f"v13-replay-{hashlib.sha256(raw_input).hexdigest()[:12]}",
            "input_hash": f"sha256:{hashlib.sha256(raw_input).hexdigest()}",
            "generated_at": generated_at,
            "producer_version": "spirosearch-v13",
        }
        artifact = write_json_artifact(
            output_dir,
            "acquisition-breakdown.json",
            report,
            kind="acquisition_breakdown",
            **common,
        )
        build_run_manifest([artifact], **common).write_json(output_dir)
    except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError):
        print("acquisition-replay failed validation", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    return EXIT_SUCCESS


def _main_paper_ingest(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run the local V18 paper intelligence ingest.")
    parser.add_argument("--paper-dir", required=True, help="Directory containing DOI-hashed paper folders.")
    parser.add_argument("--output-dir", required=True, help="Directory for manifest-backed ingest artifacts.")
    parser.add_argument("--extractor", default="regex", choices=("regex",), help="Offline extractor to use.")
    parser.add_argument("--obsidian-dir", help="Optional Obsidian vault directory for derived notes.")
    args = parser.parse_args(argv)

    try:
        run_paper_ingest(
            args.paper_dir,
            args.output_dir,
            extractor=args.extractor,
            obsidian_dir=args.obsidian_dir,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        print("paper-ingest failed validation", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    except Exception:
        print("internal error", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    return EXIT_SUCCESS


def _parse_optional_artifacts(items: list[str]) -> dict[str, str | None]:
    optional_artifacts: dict[str, str | None] = {}
    for item in items:
        kind, separator, panel = item.partition("=")
        optional_artifacts[kind.strip()] = panel.strip() if separator and panel.strip() else None
    return optional_artifacts


def _error_output_dir(output_dir: str | None, output: str | None) -> Path | None:
    if output_dir:
        return Path(output_dir)
    if output:
        return Path(output).parent
    return None


if __name__ == "__main__":
    raise SystemExit(main())
