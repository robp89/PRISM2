# Method note: Black mass leach, three feedstock grades (worked example)

_Drafted by PRISM2 on 2026-11-06 from the files in this repository. A draft for the LCA practitioner to review; it states only what the repository records._

> **Demonstration.** The data is synthetic or the process type is unreviewed. Nothing here is evidence.

## Goal and scope

- **Goal:** Demonstrate how a leach inventory responds to feedstock grade and operating conditions
- **Functional unit:** 1 kg dry black mass fed to the leach
- **System boundary:** gate-to-gate (leach and solid-liquid separation) (process type: gate-to-gate, leach and solid-liquid separation; purification, precipitation and residue treatment outside)
- **Intended use:** screening; target tier B
- **Agreed by:** not yet agreed

## Process and data

- **Process type:** Black mass leach (hydrometallurgy) (`bml-v1` v1.1.0), status **draft**.
- **Data origin:** synthetic: invented for demonstration (never evidence). 93 runs.
- **Coverage of the operating window:** 80%; gaps in h2so4_molarity, pulp_density_g_l.

## Fitted models

73 runs trained, 18 held out before fitting (seed 42). Families compared on the same split: polynomial, ann, gp. Decision rule: highest held-out R² per output; polynomial preferred within 0.01 because it exports as a formula

| Output | Chosen | Held-out R² | p90 rel. error % | Residual normality p | Gate |
|---|---|---|---|---|---|
| ni_recovery_pct | gp | 0.991 | 2.4 | 0.630 | pass |
| co_recovery_pct | gp | 0.994 | 2.0 | 0.663 | pass |
| li_recovery_pct | gp | 0.997 | 1.5 | 0.186 | pass |
| mn_recovery_pct | gp | 0.997 | 1.4 | 0.891 | pass |

## Inventory

Per 1 kg dry black mass fed to the leach. Ranges are 5th to 95th percentiles of a 1000-sample Monte Carlo (composition ±5%, conditions ±2% relative s.d., model error from held-out RMSE).

| Exchange | Unit | low | mid | high |
|---|---|---|---|---|
| Black mass (dry) | kg | 1 (1 to 1) | 1 (1 to 1) | 1 (1 to 1) |
| Sulfuric acid (100% basis) | kg | 1.961 (1.87 to 2.052) | 1.961 (1.876 to 2.061) | 1.961 (1.871 to 2.052) |
| Hydrogen peroxide (100% basis) | kg | 0.0666 (0.06349 to 0.06977) | 0.0666 (0.06364 to 0.0699) | 0.0666 (0.06354 to 0.0696) |
| Process water | m3 | 0.01 (0.009668 to 0.01034) | 0.01 (0.009695 to 0.01034) | 0.01 (0.009683 to 0.01033) |
| Process heat | MJ | 2.549 (2.392 to 2.716) | 2.549 (2.392 to 2.703) | 2.549 (2.408 to 2.706) |
| Nickel to pregnant leach solution | kg | 0.1152 (0.105 to 0.1253) | 0.1729 (0.1589 to 0.1876) | 0.2306 (0.2115 to 0.2496) |
| Cobalt to pregnant leach solution | kg | 0.02884 (0.0265 to 0.03138) | 0.05778 (0.05286 to 0.06235) | 0.07716 (0.07054 to 0.08362) |
| Lithium to pregnant leach solution | kg | 0.02303 (0.02113 to 0.02496) | 0.03231 (0.02953 to 0.03492) | 0.04161 (0.03809 to 0.04506) |
| Manganese to pregnant leach solution | kg | 0.03797 (0.03475 to 0.04119) | 0.05696 (0.05234 to 0.06145) | 0.07593 (0.06939 to 0.08221) |
| Leach residue (by difference) | kg | 0.795 (0.7839 to 0.806) | 0.6801 (0.6624 to 0.6965) | 0.5746 (0.5528 to 0.5973) |
| Oxygen from peroxide decomposition (upper bound) | kg | 0.03133 (0.02987 to 0.03282) | 0.03133 (0.02993 to 0.03288) | 0.03133 (0.02989 to 0.03274) |

No emission factors are applied in PRISM. Background data and impact assessment are done in XYCLE.

## Quality

- **Tier D:** Screening only: draft process type, too few runs, or the model failed its gate.
- process type bml-v1 is a draft
- **To raise the tier:** have the process type reviewed by its named owners.

## Assumptions

- A-03 (see docs/ASSUMPTIONS.md)
- A-04 (see docs/ASSUMPTIONS.md)
- A-05 (see docs/ASSUMPTIONS.md)
- A-07 (see docs/ASSUMPTIONS.md)

## Reproducibility

| File | SHA-256 |
|---|---|
| prism.yaml | `317315423f5473e4…` |
| scope.yaml | `f3ad376c09bfe7f9…` |
| feedstocks.yaml | `d968e5d49aed1a59…` |
| signoffs.yaml | `858dd9dfa3940aa5…` |
| library/bml-v1.yaml | `88f3a3d2727a1956…` |
| data/runs.csv | `c209815603cf410f…` |
