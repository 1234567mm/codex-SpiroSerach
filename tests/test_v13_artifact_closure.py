import tempfile
import unittest
from pathlib import Path

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import build_run_manifest, write_json_artifact, write_jsonl_artifact


class V13ArtifactClosureTests(unittest.TestCase):
    def test_literature_and_extraction_artifacts_round_trip_through_manifest(self):
        common = {
            "run_id": "v13-contract-run",
            "input_hash": "sha256:input",
            "generated_at": "2026-07-11T00:00:00+00:00",
            "producer_version": "spirosearch-v13",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifacts = [
                write_json_artifact(
                    output_dir,
                    "literature-search-results.json",
                    {
                        "schema_version": "v13.literature_search_results.v1",
                        "query_id": "query-1",
                        "provider": "crossref",
                        "query": "perovskite HTL",
                        "retrieved_at": common["generated_at"],
                        "response_sha256": "a" * 64,
                        "records": [{"doi": "10.1234/example", "title": "Example"}],
                        "next_cursor": None,
                    },
                    kind="literature_search_results",
                    **common,
                ),
                write_jsonl_artifact(
                    output_dir,
                    "source-assets.jsonl",
                    [{
                        "schema_version": "v13.source_asset.v1",
                        "asset_id": "asset-1",
                        "document_id": "doc-1",
                        "doi": "10.1234/example",
                        "source_url": "https://example.invalid/open.txt",
                        "license": "CC BY 4.0",
                        "text_sha256": "b" * 64,
                        "local_path": "assets/doc-1.txt",
                    }],
                    kind="source_assets",
                    **common,
                ),
                write_jsonl_artifact(
                    output_dir,
                    "literature-claims.jsonl",
                    [{
                        "schema_version": "v13.literature_claim.v1",
                        "claim_id": "claim-1",
                        "asset_id": "asset-1",
                        "chunk_id": "chunk-1",
                        "doi": "10.1234/example",
                        "property": "homo_ev",
                        "value": -5.2,
                        "unit": "eV",
                        "text_sha256": "c" * 64,
                        "method": "CV",
                        "conditions": {"reference_scale": "vacuum"},
                        "extractor_version": "regex-v1",
                        "review_status": "needs_review",
                    }],
                    kind="literature_claims",
                    **common,
                ),
                write_json_artifact(
                    output_dir,
                    "extraction-evaluation.json",
                    {
                        "schema_version": "v13.extraction_evaluation.v1",
                        "extractor_version": "regex-v1",
                        "gold_snapshot_hash": "d" * 64,
                        "counts": {"true_positive": 8, "false_positive": 1, "false_negative": 2},
                        "metrics": {"precision": 0.888888, "recall": 0.8, "f1": 0.842105},
                    },
                    kind="extraction_evaluation",
                    **common,
                ),
            ]
            build_run_manifest(artifacts, **common).write_json(output_dir)

            repository = JsonArtifactRepository.from_output_dir(output_dir)
            self.assertTrue(repository.read_json("literature_search_results").available)
            self.assertTrue(repository.read_jsonl("source_assets").available)
            self.assertTrue(repository.read_jsonl("literature_claims").available)
            self.assertTrue(repository.read_json("extraction_evaluation").available)


if __name__ == "__main__":
    unittest.main()
