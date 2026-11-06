# Working in a PRISM2 model repository

This folder is one life cycle inventory kept as code. Read `prism.yaml`, `scope.yaml` and `decisions/` first.

## Commands
- `prism validate` - every finding has a stable id and a `file:line`. Fix errors at that location.
- `prism build [--demo]` - fit and test models, certify, generate the inventory into `build/`.
- `prism status` - the verdict and whether `build/` is outdated.
- `prism design` - a space-filling run sheet when data is missing.
- `prism export xycle [--demo]` - XYCLE import files. Fails closed.

## Non-negotiable rules
1. **Never invent science.** Do not change operating windows, recipe coefficients, rule thresholds or gate
   settings to make a check pass. Propose the change in a decision record for the named owner to review.
2. **Never edit `build/`.** It is generated; rebuild instead.
3. **No impacts in PRISM.** Only physical flows. Emission factors and characterisation live in XYCLE.
4. **Exclude runs only with a reason** in `prism.yaml` (`data.exclude`), and say so in your summary.
5. **Do not mark data as anything other than its true origin.** Synthetic data is always `synthetic`.
6. **Do not add sign-offs.** Only the named person adds their own sign-off.
7. **No customer or NDA data in git.** Load it from restricted storage.

## Definition of done
`prism validate` has no errors, `prism build` ran, `prism status` says the build is up to date, and your
summary lists anything excluded, any assumption touched, and what would raise the quality tier.
