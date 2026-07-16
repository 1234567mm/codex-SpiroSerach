from __future__ import annotations

from typing import Any


def build_v25_runtime_profile() -> dict[str, Any]:
    return {
        "schema_version": "v25.release_profile.v1",
        "profile_id": "v25-supported-runtime",
        "default_runtime": {
            "python": "cpython",
            "requires_python": ">=3.11",
            "dependencies": ["jsonschema>=4.18", "referencing>=0.30"],
        },
        "optional_extras": {
            "ml": {
                "included_in_default": False,
                "dependencies": ["numpy>=2.0", "scikit-learn>=1.5"],
            },
            "bo": {
                "included_in_default": False,
                "dependencies": ["torch>=2.5", "gpytorch>=1.14", "botorch>=0.15"],
            },
        },
        "entry_points": ["spirosearch.cli.main", "artifact_viewer_static"],
        "external_services": [],
        "release_boundaries": {
            "direct_lab_dispatch": False,
            "new_provider_execution": False,
            "new_model_family": False,
            "read_only_surfaces_mutate_state": False,
        },
    }
