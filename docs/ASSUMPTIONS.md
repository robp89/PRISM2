# Engineering assumptions awaiting review

Each needs the named reviewer before any process type is set to `reviewed`. Ids match the PRISM platform's
docs where carried over.

| Id | Assumption | Where | Reviewer |
|---|---|---|---|
| A-01 | bml-v1 operating windows (40-90 °C, 0.5-5 mol/L, 30-240 min, 0-5 vol% H2O2, 50-200 g/L) | bml-v1 fields | Irdanto S. L. |
| A-02 | Composition basis is wt% of dry black mass | bml-v1 | Irdanto S. L. |
| A-03 | Acid charged = molarity × liquor volume, liquor volume = 1000 / pulp density; water = liquor volume | bml-v1 recipe | Sahin A. |
| A-04 | H2O2 dosed as 30 wt% solution, 1.11 kg/L; O2 from full decomposition is an upper bound | bml-v1 recipe | Sahin A. |
| A-05 | Sensible heat only: liquor cp 4.18 kJ/kg K, solids 0.9 kJ/kg K, from 25 °C; no reaction enthalpy | bml-v1 recipe | Sahin A. |
| A-06 | Heat delivery efficiency 0.67 | bml-v1 recipe | Sahin A. |
| A-07 | Residue by difference of the four tracked metals only (Al, Cu dissolution not deducted) | bml-v1 recipe | Irdanto S. L. |
| A-08 | R3 acid demand: 1 mol H2SO4 per mol Ni, Co, Mn, Cu; 0.5 per Li; 1.5 per Al | bml-v1 rules | Sahin A. |
| A-09 | R3 acid-to-solid warning band 1.2-2.5 g/g; R6 Li recovery warning below 85% | bml-v1 rules | Irdanto S. L. |
| A-10 | R7 element balance tolerance 5% | bml-v1 rules | Irdanto S. L. |
| A-11 | Gate defaults: R² ≥ 0.92 (grant ANN criterion), p90 error ≤ 10%, normality p ≥ 0.05, ≥ 8 held-out runs, ≥ 20 runs | project defaults | Rohin S. / Sahin A. |
| A-12 | pyro-smelt-v1 placeholder: all windows, 95% Cu to alloy, 95% graphite oxidised | pyro-smelt-v1 | Irdanto S. L. |
| A-13 | ree-ndfeb-leach-v1 placeholder: all windows and the recipe | ree-ndfeb-leach-v1 | Irdanto S. L. |
| A-14 | Default input uncertainty: composition 5%, conditions 2% relative s.d., normal | inventory | Costanza T. |
| A-15 | Tier rules: draft type, < 20 runs or failed gate → D; simulation → C (B once compared with measurements); measured → B (A with full coverage); sign-offs can only lower the tier | certify.py | Costanza T. / Irdanto S. L. |
| A-16 | Coverage: a field's window in four bins, complete when ≥ 3 of 4 are filled and every grade has runs | doe.py | Irdanto S. L. |
