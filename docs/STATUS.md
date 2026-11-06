# Status: what is verified and what is not (6 Nov 2026)

## Verified
- 18 automated tests pass: rules (fail, skip, pass), file:line findings on the planted errors, the leach
  recipe reproducing the User Journey worked example (1.47 kg acid, 0.067 kg H2O2, about 2.5 MJ, residue
  0.68 kg), surrogate families on a known function, polynomial-to-formula equivalence, fail-closed export
  (demo build cannot unlock a real export; stale build refused), XYCLE file layout, the screening path,
  and that reviewed measured data with a technical sign-off reaches tier B.
- The viewer was opened in a headless browser at desktop and phone widths.

## Not verified
- **Any scientific content.** Every process type is a draft; see ASSUMPTIONS.md.
- **XYCLE import.** Files follow the written importer rules but have not been imported into XYCLE.
- **Real data.** Only synthetic runs. No HSC Sim or FactSage importer yet (they need real exports).
- **Usability.** No person has used the viewer.
- **Scale and security.** No authentication; the viewer's build and export buttons write to `build/`.
  Run it locally or behind single sign-on, read-only for shared use.

## Known limits
- Monte Carlo treats inputs as independent normals; model error is added from held-out RMSE.
- A Gaussian process or neural network cannot be exported as an XYCLE formula; the Parameter Import then
  carries point values and the Model Import carries the per-grade inventory.
- Coverage is a simple binning measure, not a space-filling metric.
