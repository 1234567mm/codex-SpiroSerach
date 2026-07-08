import unittest

from spirosearch.domain import EnergyEvidence, EvidenceProvenance, ReviewItem
from spirosearch.domain.scoring_view import EvidenceQualityPolicy, ScoringViewBuilder


def _provenance(**overrides):
    values = {
        "source_id": "doi:10.1000/scoring-view",
        "provider_name": "literature_fixture",
        "provider_response_id": "response-1",
        "trust_level": "T4_literature_curated",
        "curation_status": "curated",
    }
    values.update(overrides)
    return EvidenceProvenance(**values)


def _energy(evidence_id: str, property_name: str, **overrides):
    values = {
        "energy_evidence_id": evidence_id,
        "material_id": "mat-1",
        "use_instance_id": "use-1",
        "property_name": property_name,
        "value_ev": -5.2,
        "method": "reported",
        "reference_scale": "vacuum",
        "provenance": _provenance(),
        "eligible_for_scoring": True,
    }
    values.update(overrides)
    return EnergyEvidence(**values)


def _review(target_id: str, **overrides):
    values = {
        "review_item_id": f"review-{target_id}",
        "target_type": "energy_evidence",
        "target_id": target_id,
        "reason_code": "unit_or_reference_scale_mismatch",
        "severity": "high",
        "blocking_surface": "scoring",
        "suggested_action": "curate_reference_scale",
        "resolution_status": "open",
    }
    values.update(overrides)
    return ReviewItem(**values)


class ScoringViewTests(unittest.TestCase):
    def test_quality_policy_blocks_open_scoring_reviews_without_mutating_evidence(self):
        energy = _energy("energy-homo", "homo_ev")
        blocking_review = _review(energy.energy_evidence_id)
        resolved_review = _review(
            energy.energy_evidence_id,
            review_item_id="review-resolved",
            resolution_status="resolved",
        )

        policy = EvidenceQualityPolicy()
        blocked = policy.assess_energy_evidence(energy, [blocking_review, resolved_review])

        self.assertFalse(blocked.eligible_for_scoring)
        self.assertEqual(blocked.blocking_review_count, 1)
        self.assertEqual(blocked.blocking_review_ids, ("review-energy-homo",))
        self.assertTrue(energy.eligible_for_scoring)

    def test_scoring_view_exposes_only_policy_eligible_energy_facts(self):
        eligible = _energy("energy-homo", "homo_ev")
        blocked = _energy("energy-lumo", "lumo_ev", value_ev=-2.1)
        flagged_not_eligible = _energy(
            "energy-gap",
            "band_gap_ev",
            value_ev=2.0,
            eligible_for_scoring=False,
        )

        view = ScoringViewBuilder().build(
            energy_evidence=[eligible, blocked, flagged_not_eligible],
            review_items=[_review(blocked.energy_evidence_id)],
        )

        self.assertEqual([fact.evidence_id for fact in view.energy_facts], ["energy-homo"])
        self.assertEqual(view.energy_facts[0].quality.trust_level, "T4_literature_curated")
        self.assertGreater(view.energy_facts[0].quality.quality_score, 0.0)
        payload = view.to_dict()
        self.assertEqual(payload["energy_facts"][0]["property_name"], "homo_ev")
        self.assertNotIn("confidence", payload["energy_facts"][0])
        self.assertNotIn("provider_confidence", payload["energy_facts"][0])


if __name__ == "__main__":
    unittest.main()
