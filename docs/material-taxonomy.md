# Material Taxonomy for Spiro-OMeTAD Replacement Mining

This taxonomy supports seed mining for industrial n-i-p perovskite solar cells where the target is to replace, reduce, or functionally de-risk doped Spiro-OMeTAD at the perovskite/top-contact side.

## Screening Intent

Rank candidates by whether they can remove the known industrial liabilities of doped Spiro-OMeTAD: expensive synthesis, hygroscopic dopants such as LiTFSI, volatile additives such as tBP, slow oxidation-dependent conductivity, and unstable ion or metal migration under heat, light, moisture, and bias.

The mining system should not treat every seed as a direct one-layer HTL. Some classes are direct replacements, while others are interface or barrier components that become useful only in a stack.

## Classes

### `polymer_htm`

Conjugated or arylamine polymers that can form a continuous hole-transport layer on top of perovskite.

Primary examples: PTAA, P3HT, poly-TPD, PCDTBT, DPP-DTT family.

Useful descriptors:

- HOMO near the perovskite valence band, commonly around -5.0 to -5.5 eV.
- Hole mobility above 1e-5 cm2/Vs, with higher priority above 1e-4 cm2/Vs.
- Hydrophobicity and water-vapor resistance.
- Molecular weight, dispersity, regioregularity, and batch metadata.
- Orthogonal, scalable solvent options.

Main red flags:

- Batch-to-batch variability.
- Strong visible absorption in thick films.
- Dependence on halogenated solvents.
- Low intrinsic conductivity if used without dopants.

### `dopant_free_small_molecule`

Discrete organic HTMs designed to avoid LiTFSI/tBP while maintaining processable, reproducible hole extraction.

Primary examples: DFH, TaTm, VNPB, X60, Trux-OMeTAD, BTT-TPA family.

Useful descriptors:

- HOMO around -5.1 to -5.5 eV.
- Intrinsic mobility and conductivity without oxidative dopants.
- Glass-transition temperature and crystallization tendency.
- Purification route, sublimation compatibility, and synthetic step count.
- Film-forming ability at 20 to 100 nm.

Main red flags:

- Good p-i-n results may not transfer directly to n-i-p top contacts.
- Synthetic complexity and IP constraints can erase material-cost gains.
- Low conductivity may reintroduce dopants or require a conductive interlayer.

### `inorganic_hybrid_htm`

Inorganic p-type semiconductors, oxides, sulfides, iodides, or hybrid inorganic/organic contacts that can reduce organic HTL thickness and improve thermal stability.

Primary examples: CuSCN, CuI, NiOx nanoparticles, MoOx, CuOx.

Useful descriptors:

- Work function around -5.0 to -5.6 eV.
- Wide bandgap and low parasitic absorption.
- Low-temperature deposition after perovskite formation.
- Ion migration risk, especially Cu and I species.
- Solvent and plasma compatibility with the perovskite top surface.

Main red flags:

- Direct deposition can damage perovskite.
- Cu-containing materials need diffusion barriers.
- Oxide stoichiometry can strongly shift work function and recombination.
- Some oxides are excellent p-i-n bottom contacts but poor top-side n-i-p drop-ins.

### `sam_derived_interface`

Self-assembled monolayers and SAM-inspired molecules that tune interface dipoles, defect chemistry, and hole selectivity. These should be modeled as interface enablers rather than bulk conductors.

Primary examples: 2PACz, MeO-2PACz, Me-4PACz, Br-2PACz.

Useful descriptors:

- Anchor group, binding surface, dipole direction, and work-function shift.
- Coverage uniformity and pinhole tolerance.
- Chemical compatibility with perovskite and adjacent conductive layer.
- Whether the SAM is used under perovskite, on a metal oxide, or in a transferred/hybrid top contact.

Main red flags:

- A monolayer cannot replace the full conductivity role of Spiro-OMeTAD.
- Phosphonic-acid SAMs usually require oxide or reactive anchoring surfaces.
- Missing coverage at module scale can dominate recombination and leakage.

### `two_dimensional_barrier`

2D materials used as ultrathin conductive additives, diffusion barriers, moisture barriers, passivation layers, or composite fillers. Most are not standalone HTLs.

Primary examples: graphene oxide, reduced graphene oxide, MoS2, WS2, h-BN, Ti3C2Tx MXene.

Useful descriptors:

- Conductive versus insulating character.
- Work function and surface termination.
- Flake lateral size, thickness, aspect ratio, and dispersion solvent.
- Barrier function against H2O, O2, halides, metal atoms, and Cu migration.
- Percolation threshold and shunt risk.

Main red flags:

- Insulating barriers such as h-BN must be tunneling-thin.
- Conductive flakes can create shunts if coverage is uncontrolled.
- Aqueous or polar processing can damage exposed perovskite.
- Residual surfactants, etchants, or ions can poison device stability.

## Cross-Class First-Pass Filters

Use these as coarse filters before expensive modeling or synthesis:

- Energy alignment: HOMO or work function should usually sit between -5.0 and -5.6 eV for common mixed-cation iodide/bromide perovskites.
- Conductivity: direct HTLs need enough intrinsic conductivity at 10 to 100 nm without hygroscopic dopants.
- Process temperature: top-side n-i-p processing should generally stay below 120 C unless the perovskite stack is proven stable.
- Solvent orthogonality: solvents must not dissolve, ion-exchange, or roughen the perovskite.
- Stability: reject materials with obvious mobile-ion, acidic, hygroscopic, or electrode-corrosion risks unless the design includes a barrier.
- Optical loss: HTL or interlayer absorption must be negligible at the chosen thickness.
- Scale path: prefer materials with supplier availability, simple purification, non-halogenated solvent routes, or vacuum compatibility.

## Evidence Labels

Use these labels when ingesting papers or patents:

- `direct_nip_demo`: demonstrated as the main top HTL in an n-i-p PSC.
- `nip_hybrid_demo`: demonstrated in n-i-p only as part of a bilayer, composite, barrier, or contact modifier.
- `pin_transfer_candidate`: strong p-i-n evidence but not a direct n-i-p top-contact proof.
- `device_adjacent_evidence`: OLED, OPV, transistor, or coating evidence supports descriptors but PSC validation is incomplete.
- `class_prior`: plausible family-level seed with estimated descriptors; do not use as a ground-truth label.

## Notes for Later Curation

The seed JSON intentionally mixes procurement-ready materials with family-level exploration seeds. Later curation should split ambiguous family entries into exact structures with CAS, InChIKey, supplier grade, purification method, and a canonical source record.

SAM and 2D entries should be down-weighted in direct Spiro-replacement rankings unless the model is explicitly searching for bilayers or composite stacks. They are included because industrial reliability may come from a stack-level replacement rather than a single molecule.
