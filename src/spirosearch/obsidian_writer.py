from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from spirosearch.artifact_repository import JsonArtifactRepository


class ObsidianWriter:
    def write_from_repository(self, output_dir: str | Path, vault_dir: str | Path) -> dict[str, Any]:
        repository = JsonArtifactRepository.from_output_dir(output_dir)
        vault = Path(vault_dir)
        vault.mkdir(parents=True, exist_ok=True)
        for child in ("papers", "molecules", "properties"):
            (vault / child).mkdir(parents=True, exist_ok=True)

        vault_summary = repository.read_json("paper_vault_summary")
        claims_result = repository.read_jsonl("literature_claims")
        papers = tuple(vault_summary.payload.get("papers", ())) if vault_summary.available else ()
        claims = tuple(claims_result.records) if claims_result.available else ()

        notes: list[dict[str, str]] = []
        for paper in papers:
            doi = str(paper["doi"])
            paper_folder = str(paper["paper_folder"])
            paper_claims = [claim for claim in claims if claim.get("doi") == doi]
            materials = sorted({_material_from_claim(claim) for claim in paper_claims})
            properties = sorted({str(claim.get("property", "unknown_property")) for claim in paper_claims})
            paper_path = vault / "papers" / f"{paper_folder}.md"
            _write_text(paper_path, _paper_note(paper, paper_claims, materials, properties))
            notes.append({"note_type": "paper", "note_path": f"papers/{paper_folder}.md", "doi": doi})

            for material in materials or ["No extracted material"]:
                slug = _slug(material)
                path = vault / "molecules" / f"{slug}.md"
                _write_text(path, _molecule_note(material, paper_folder, paper_claims))
                notes.append({"note_type": "molecule", "note_path": f"molecules/{slug}.md", "material": material})

            for prop in properties or ["no_extracted_property"]:
                slug = _slug(prop)
                path = vault / "properties" / f"{slug}.md"
                _write_text(path, _property_note(prop, paper_folder, paper_claims))
                notes.append({"note_type": "property", "note_path": f"properties/{slug}.md", "property": prop})

        return {
            "schema_version": "v18.obsidian_notes.v1",
            "note_count": len(notes),
            "notes": notes,
        }


def _paper_note(
    paper: Mapping[str, Any],
    claims: list[Mapping[str, Any]],
    materials: list[str],
    properties: list[str],
) -> str:
    material_links = ", ".join(f"[[{material}]]" for material in materials) or "No extracted material"
    property_links = ", ".join(f"[[{prop}]]" for prop in properties) or "No extracted property"
    si_line = "Supplementary information available." if paper.get("has_si") else "No supplementary information provided."
    return (
        "---\n"
        f"doi: {paper['doi']}\n"
        f"paper_folder: {paper['paper_folder']}\n"
        f"claims_count: {len(claims)}\n"
        "---\n"
        f"# {paper['paper_folder']}\n\n"
        f"Materials: {material_links}\n\n"
        f"Properties: {property_links}\n\n"
        f"{si_line}\n"
    )


def _molecule_note(material: str, paper_folder: str, claims: list[Mapping[str, Any]]) -> str:
    return (
        "---\n"
        f"material: {material}\n"
        f"claims_count: {len(claims)}\n"
        "---\n"
        f"# {material}\n\n"
        f"Papers: [[{paper_folder}]]\n"
    )


def _property_note(prop: str, paper_folder: str, claims: list[Mapping[str, Any]]) -> str:
    rows = [
        f"| {claim.get('value')} | {claim.get('unit')} | [[{paper_folder}]] |"
        for claim in claims
        if claim.get("property") == prop
    ]
    if not rows:
        rows = [f"| no extracted data |  | [[{paper_folder}]] |"]
    return (
        "---\n"
        f"property: {prop}\n"
        "---\n"
        f"# {prop}\n\n"
        "| value | unit | paper |\n"
        "| --- | --- | --- |\n"
        + "\n".join(rows)
        + "\n"
    )


def _material_from_claim(claim: Mapping[str, Any]) -> str:
    conditions = claim.get("conditions")
    if isinstance(conditions, Mapping):
        for key in ("material", "material_name", "name"):
            value = conditions.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "Unknown Material"


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return slug or "unknown"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
