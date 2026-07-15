import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.artifacts import ARTIFACT_KIND_METADATA, V4_ARTIFACT_KINDS


FIXTURE_DIR = Path("tests/fixtures/v21_identity_closure")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as records:
        return [json.loads(line) for line in records if line.strip()]


def validator(schema_name: str) -> Draft202012Validator:
    return Draft202012Validator(load_json(Path("schemas") / schema_name))


class V21IdentityContractTests(unittest.TestCase):
    def test_identity_artifact_kinds_are_registered_with_frozen_metadata(self):
        self.assertIn("candidate_identity_registry", V4_ARTIFACT_KINDS)
        self.assertIn("candidate_evidence_links", V4_ARTIFACT_KINDS)

        self.assertEqual(
            ARTIFACT_KIND_METADATA["candidate_identity_registry"],
            {
                "schema_ref": "schemas/candidate-identity-registry.schema.json",
                "join_keys": ("candidate_id", "material_id", "use_instance_id", "source_identity_id"),
                "depends_on": ("canonical_evidence",),
            },
        )
        self.assertEqual(
            ARTIFACT_KIND_METADATA["candidate_evidence_links"],
            {
                "schema_ref": "schemas/candidate-evidence-link.schema.json",
                "join_keys": ("link_id", "candidate_id", "evidence_id", "doi", "review_item_id"),
                "depends_on": ("candidate_identity_registry", "canonical_evidence", "literature_claims"),
            },
        )

    def test_identity_registry_schema_validates_stable_ids_and_merge_split_history(self):
        registry = load_json(FIXTURE_DIR / "candidate-identity-registry.json")
        validator("candidate-identity-registry.schema.json").validate(registry)

        self.assertEqual(registry["schema_version"], "v21.candidate_identity_registry.v1")
        identities = {record["candidate_id"]: record for record in registry["records"]}
        self.assertEqual(set(identities), {"candidate-accepted", "candidate-proposed", "candidate-blocked"})

        accepted = identities["candidate-accepted"]
        self.assertIn("material-accepted", accepted["material_ids"])
        self.assertIn("use-accepted-htl", accepted["use_instance_ids"])
        self.assertEqual(accepted["reviewer_state"], "accepted")
        self.assertEqual(accepted["identity_history"][0]["event_type"], "merge")
        self.assertEqual(accepted["identity_history"][1]["event_type"], "split")

    def test_evidence_link_schema_separates_accepted_proposed_and_blocked_links(self):
        links = load_jsonl(FIXTURE_DIR / "candidate-evidence-links.jsonl")
        link_validator = validator("candidate-evidence-link.schema.json")
        for link in links:
            link_validator.validate(link)

        by_id = {link["link_id"]: link for link in links}
        self.assertEqual(by_id["link-accepted"]["reviewer_state"], "accepted")
        self.assertEqual(by_id["link-accepted"]["confidence_category"], "reviewed_explicit")
        self.assertEqual(by_id["link-proposed"]["reviewer_state"], "proposed")
        self.assertEqual(by_id["link-proposed"]["confidence_category"], "deterministic_proposal")
        self.assertEqual(by_id["link-blocked"]["reviewer_state"], "blocked")
        self.assertEqual(by_id["link-blocked"]["blocking_review_ids"], ["review-identity-ambiguous"])

    def test_unsupported_reviewer_or_confidence_state_is_rejected(self):
        registry = load_json(FIXTURE_DIR / "candidate-identity-registry.json")
        registry["records"][0]["reviewer_state"] = "auto_accepted"
        with self.assertRaises(ValidationError):
            validator("candidate-identity-registry.schema.json").validate(registry)

        link = load_jsonl(FIXTURE_DIR / "candidate-evidence-links.jsonl")[0]
        link["confidence_category"] = "fuzzy_truth"
        with self.assertRaises(ValidationError):
            validator("candidate-evidence-link.schema.json").validate(link)

    def test_fixture_run_manifest_validates_identity_artifacts(self):
        report = validate_artifact_run(FIXTURE_DIR).to_dict()
        self.assertEqual(report["status"], "valid", report)

        manifest = load_json(FIXTURE_DIR / "run-manifest.json")
        by_kind = {artifact["kind"]: artifact for artifact in manifest["artifacts"]}
        self.assertEqual(
            by_kind["candidate_identity_registry"]["schema_ref"],
            "schemas/candidate-identity-registry.schema.json",
        )
        self.assertEqual(
            by_kind["candidate_evidence_links"]["schema_ref"],
            "schemas/candidate-evidence-link.schema.json",
        )
        self.assertEqual(by_kind["candidate_evidence_links"]["record_count"], 3)


if __name__ == "__main__":
    unittest.main()
