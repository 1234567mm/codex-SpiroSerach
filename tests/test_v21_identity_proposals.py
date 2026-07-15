import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from spirosearch.identity_links import (
    build_candidate_evidence_link_proposals,
    normalize_doi,
    normalize_inchikey,
)


FIXTURE_DIR = Path("tests/fixtures/v21_identity_closure")


def load_registry() -> dict:
    return json.loads((FIXTURE_DIR / "candidate-identity-registry.json").read_text(encoding="utf-8"))


def evidence_record(evidence_id: str, *, doi: str | None = None, inchikey: str | None = None, material_id: str | None = None):
    return {
        "evidence_id": evidence_id,
        "evidence_kind": "literature_claim",
        "paper": {
            "doi": doi,
            "source_id": f"paper-{evidence_id}",
            "asset_id": f"asset-{evidence_id}",
            "chunk_id": f"chunk-{evidence_id}",
        },
        "identifiers": {
            "doi": doi,
            "inchikey": inchikey,
            "material_id": material_id,
        },
    }


class V21IdentityProposalTests(unittest.TestCase):
    def test_normalizers_are_deterministic_and_conservative(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1000/Accepted "), "10.1000/accepted")
        self.assertEqual(normalize_doi("doi:10.1000/Accepted"), "10.1000/accepted")
        self.assertIsNone(normalize_doi(None))
        self.assertEqual(normalize_inchikey(" acceptedinchikey "), "ACCEPTEDINCHIKEY")
        self.assertIsNone(normalize_inchikey(""))

    def test_exact_identifier_match_creates_proposed_link_not_accepted_truth(self):
        result = build_candidate_evidence_link_proposals(
            load_registry(),
            [evidence_record("claim-new-accepted", doi="https://doi.org/10.1000/Accepted")],
            source_run_id="proposal-run",
        )

        self.assertEqual(result["schema_version"], "v21.identity_link_proposals.v1")
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual(len(result["proposals"]), 1)
        link = result["proposals"][0]
        Draft202012Validator(json.loads(Path("schemas/candidate-evidence-link.schema.json").read_text())).validate(link)
        self.assertEqual(link["candidate_id"], "candidate-accepted")
        self.assertEqual(link["reviewer_state"], "proposed")
        self.assertEqual(link["confidence_category"], "deterministic_proposal")
        self.assertEqual(link["blocking_review_ids"], [])
        self.assertNotIn("score", json.dumps(link, sort_keys=True))
        self.assertNotIn("eligible_for_scoring", json.dumps(link, sort_keys=True))

    def test_proposals_are_deterministic_when_inputs_are_reordered(self):
        records = [
            evidence_record("claim-proposed", doi="10.1000/proposed"),
            evidence_record("claim-accepted", inchikey="acceptedinchikey"),
        ]
        first = build_candidate_evidence_link_proposals(load_registry(), records, source_run_id="proposal-run")
        second = build_candidate_evidence_link_proposals(load_registry(), list(reversed(records)), source_run_id="proposal-run")

        self.assertEqual(first, second)
        self.assertEqual([link["evidence_id"] for link in first["proposals"]], ["claim-accepted", "claim-proposed"])

    def test_ambiguous_or_missing_identity_emits_diagnostics_without_links(self):
        registry = load_registry()
        duplicate = dict(registry["records"][0])
        duplicate["candidate_id"] = "candidate-duplicate"
        duplicate["stable_identity_id"] = "identity-duplicate"
        registry["records"].append(duplicate)

        result = build_candidate_evidence_link_proposals(
            registry,
            [
                evidence_record("claim-ambiguous", doi="10.1000/accepted"),
                evidence_record("claim-missing", doi="10.1000/missing"),
                evidence_record("claim-no-identifiers"),
            ],
            source_run_id="proposal-run",
        )

        self.assertEqual(result["proposals"], [])
        diagnostics = {item["evidence_id"]: item for item in result["diagnostics"]}
        self.assertEqual(diagnostics["claim-ambiguous"]["reason_code"], "ambiguous_candidate_identity")
        self.assertEqual(diagnostics["claim-missing"]["reason_code"], "candidate_identity_not_found")
        self.assertEqual(diagnostics["claim-no-identifiers"]["reason_code"], "candidate_identity_basis_missing")
        self.assertTrue(all(item["reviewer_state"] == "blocked" for item in diagnostics.values()))


if __name__ == "__main__":
    unittest.main()
