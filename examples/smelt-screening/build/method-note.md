# Method note: Black mass smelting, screening from eight literature-style points

_Drafted by PRISM2 on 2026-11-06 from the files in this repository. A draft for the LCA practitioner to review; it states only what the repository records._

## Goal and scope

- **Goal:** Screening estimate of furnace inputs for a pyrometallurgical route
- **Functional unit:** 1 kg dry black mass fed to the furnace
- **System boundary:** gate-to-gate (smelting furnace) (process type: gate-to-gate, smelting furnace and off-gas cooling; alloy refining outside)
- **Intended use:** screening; target tier D
- **Agreed by:** not yet agreed

## Process and data

- **Process type:** Black mass smelting (pyrometallurgy) - placeholder (`pyro-smelt-v1` v0.1.0), status **draft**.
- **Data origin:** literature: taken from publications. 8 runs.
- **Coverage of the operating window:** 58%; gaps in flux_kg_per_kg, electricity_kwh_per_kg.

## Inventory

Per 1 kg dry black mass fed to the furnace. Ranges are 5th to 95th percentiles of a 1000-sample Monte Carlo (composition ±5%, conditions ±2% relative s.d., model error from held-out RMSE).

| Exchange | Unit | mid |
|---|---|---|
| Black mass (dry) | kg | 1 (1 to 1) |
| Slag flux (limestone and silica) | kg | 0.4 (0.3866 to 0.4138) |
| Electricity | kWh | 1.2 (1.163 to 1.237) |
| Ni-Co-Cu alloy | kg | 0.2487 (0.2335 to 0.2643) |
| Lithium reporting to slag | kg | 0.03388 (0.03104 to 0.03667) |
| Slag | kg | 0.8013 (0.7661 to 0.8361) |
| Carbon dioxide (graphite oxidation) | kg | 1.218 (1.125 to 1.32) |

No emission factors are applied in PRISM. Background data and impact assessment are done in XYCLE.

## Quality

- **Tier D:** Screening only: draft process type, too few runs, or the model failed its gate.
- process type pyro-smelt-v1 is a draft
- **To raise the tier:** have the process type reviewed by its named owners.

## Assumptions

- A-12 (see docs/ASSUMPTIONS.md)

## Reproducibility

| File | SHA-256 |
|---|---|
| prism.yaml | `62e0b4f99f195396…` |
| scope.yaml | `7ae696a71b3911ba…` |
| feedstocks.yaml | `ccd7c051a1af1b93…` |
| signoffs.yaml | `55b615c8a11920a3…` |
| library/pyro-smelt-v1.yaml | `bde8be03eebd31ac…` |
| data/runs.csv | `b262178f836acb0d…` |
