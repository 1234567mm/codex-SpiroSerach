from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from spirosearch.molecules import MoleculeEntity


HETERO_ATOMS = {"N", "O", "S", "P", "F", "Cl", "Br", "I", "B", "n", "o", "s", "p", "b"}


@dataclass(frozen=True)
class MolecularDescriptorSet:
    molecule_id: str
    structure_status: str
    descriptor_status: str
    descriptor_backend: str
    molecular_weight: float | None = None
    logp: float | None = None
    tpsa: float | None = None
    hbd: int | None = None
    hba: int | None = None
    heavy_atom_count: int | None = None
    hetero_atom_count: int | None = None
    aromatic_atom_count: int | None = None
    missing_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "molecule_id": self.molecule_id,
            "structure_status": self.structure_status,
            "descriptor_status": self.descriptor_status,
            "descriptor_backend": self.descriptor_backend,
            "molecular_weight": self.molecular_weight,
            "logp": self.logp,
            "tpsa": self.tpsa,
            "hbd": self.hbd,
            "hba": self.hba,
            "heavy_atom_count": self.heavy_atom_count,
            "hetero_atom_count": self.hetero_atom_count,
            "aromatic_atom_count": self.aromatic_atom_count,
            "missing_reason": self.missing_reason,
        }


def describe_molecule(molecule: MoleculeEntity) -> MolecularDescriptorSet:
    """Calculate local molecular descriptors when a structure is available.

    RDKit is used when installed. The fallback parser only exposes conservative
    structure counts and marks the descriptor set as partial.
    """
    if molecule.structure_status != "resolved" or not molecule.canonical_smiles:
        return MolecularDescriptorSet(
            molecule_id=molecule.molecule_id,
            structure_status=molecule.structure_status,
            descriptor_status="unavailable",
            descriptor_backend="none",
            missing_reason="requires resolved structure with canonical_smiles",
        )

    rdkit_result = _describe_with_rdkit(molecule)
    if rdkit_result is not None:
        return rdkit_result
    return _describe_with_fallback(molecule)


def _describe_with_rdkit(molecule: MoleculeEntity) -> MolecularDescriptorSet | None:
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors
    except ImportError:
        return None

    mol = Chem.MolFromSmiles(molecule.canonical_smiles or "")
    if mol is None:
        return MolecularDescriptorSet(
            molecule_id=molecule.molecule_id,
            structure_status=molecule.structure_status,
            descriptor_status="unavailable",
            descriptor_backend="rdkit",
            missing_reason="rdkit could not parse canonical_smiles",
        )
    aromatic_atom_count = sum(1 for atom in mol.GetAtoms() if atom.GetIsAromatic())
    hetero_atom_count = sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() not in {1, 6})
    return MolecularDescriptorSet(
        molecule_id=molecule.molecule_id,
        structure_status=molecule.structure_status,
        descriptor_status="computed",
        descriptor_backend="rdkit",
        molecular_weight=round(float(Descriptors.MolWt(mol)), 6),
        logp=round(float(Descriptors.MolLogP(mol)), 6),
        tpsa=round(float(rdMolDescriptors.CalcTPSA(mol)), 6),
        hbd=int(Lipinski.NumHDonors(mol)),
        hba=int(Lipinski.NumHAcceptors(mol)),
        heavy_atom_count=int(mol.GetNumHeavyAtoms()),
        hetero_atom_count=hetero_atom_count,
        aromatic_atom_count=aromatic_atom_count,
    )


def _describe_with_fallback(molecule: MoleculeEntity) -> MolecularDescriptorSet:
    atoms = _scan_smiles_atoms(molecule.canonical_smiles or "")
    return MolecularDescriptorSet(
        molecule_id=molecule.molecule_id,
        structure_status=molecule.structure_status,
        descriptor_status="partial",
        descriptor_backend="smiles-token-fallback",
        heavy_atom_count=len(atoms),
        hetero_atom_count=sum(1 for atom in atoms if atom in HETERO_ATOMS),
        aromatic_atom_count=sum(1 for atom in atoms if atom in {"b", "c", "n", "o", "p", "s"}),
        missing_reason="rdkit unavailable; molecular_weight/logp/tpsa/hbd/hba not computed",
    )


def _scan_smiles_atoms(smiles: str) -> tuple[str, ...]:
    atoms: list[str] = []
    index = 0
    while index < len(smiles):
        token = smiles[index]
        two_char = smiles[index : index + 2]
        if two_char in {"Cl", "Br"}:
            atoms.append(two_char)
            index += 2
            continue
        if token.isupper() or token in {"b", "c", "n", "o", "p", "s"}:
            atoms.append(token)
        index += 1
    return tuple(atoms)
