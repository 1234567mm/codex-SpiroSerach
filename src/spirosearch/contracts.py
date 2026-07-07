from __future__ import annotations

SUCCESS_ARTIFACTS = (
    "screening-report.json",
    "screening-report.md",
    "evidence-chain.json",
    "decision-digest.json",
    "run-manifest.json",
)

VALIDATION_ERROR_ARTIFACT = "validation-errors.json"

EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 1
EXIT_LOCAL_TRACE_ERROR = 2
EXIT_PATH_ERROR = 3
EXIT_INTERNAL_ERROR = 4

SCHEMA_VERSION = "2.1"
V31_SCHEMA_VERSION = "3.1"
NORMALIZATION_VERSION = "candidate_normalization_v2_1"
ROLE_GATE_VERSION = "role_gate_v2_1"
REPORT_CONTRACT_VERSION = "report_contract_v2_1"

RECORD_TYPES = {
    "candidate",
    "comparator",
    "control",
    "interface_component",
    "barrier_component",
    "architecture_pair",
}

REPLACEMENT_MODES = {
    "direct_htl",
    "bilayer_htl",
    "interface_enabler",
    "barrier_enhancer",
    "baseline_only",
}

MATERIAL_CLASSES = {
    "polymer_htm",
    "dopant_free_small_molecule",
    "inorganic_hybrid_htm",
    "sam_derived_interface",
    "two_dimensional_barrier",
    "baseline_comparator",
}

EVIDENCE_LABELS = {
    "direct_nip_demo",
    "nip_hybrid_demo",
    "pin_transfer_candidate",
    "interface_only",
    "barrier_only",
    "device_adjacent",
    "device_adjacent_evidence",
    "class_prior",
    "negative_or_refuting",
}

V31_RECOMMENDED_ACTIONS = {
    "reject",
    "curate_evidence",
    "calculate",
    "source_or_synthesize",
    "film_screen",
    "half_device_screen",
    "device_screen",
    "stability_screen",
    "architecture_pairing",
}

LOCAL_PAPER_TRUST_LEVELS = (
    "L0_missing",
    "L1_local_file_present",
    "L2_hash_verified",
    "L3_anchor_verified",
    "L4_doi_metadata_matched",
    "L5_curated_reference",
)

TRUST_LEVELS = (
    "T0_missing",
    "T1_calculated",
    "T2_computed_db",
    "T3_literature_machine",
    "T4_literature_curated",
    "T5_experimental_device",
)
