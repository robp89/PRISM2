# Roadmap, tied to the grant plan

| Backlog id | What | WP / milestone | State in PRISM2 |
|---|---|---|---|
| ADAPT-1 | Common run format and adapter registry | WP2 MS2.2 | run table loader built; registry not yet |
| SIM-1 | HSC Sim and FactSage results as runs with provenance | WP2/WP3, PACK-1 | not built (needs licensed exports) |
| ADAPT-2 | Read a ChemE-as-Code flowsheet into PRISM runs | WP2 | not built |
| REC-1 | Data reconciliation of plant stream measurements | WP3 Path A/C | not ported from the PRISM platform yet |
| BAL-1/2 | Energy balance; automatic check against FactSage within 5% | WP2 MS2.1 | not built |
| DOE-1 | Run design and coverage | WP3 | **built** (`prism design`, coverage) |
| ANN-1 | Compare polynomial, ANN, GP on identical splits, rule written first | WP4 | **built** |
| QA-1 | Quality tiers and sign-offs | WP4 MS4.2 | **built** |
| UNC-1 | Monte Carlo to each exchange | WP3/WP4 | **built** (independent normals) |
| RPT-1 | Method note | WP5 D5.2 | **built** (draft) |
| XY-1 | Live XYCLE API instead of files | WP4 MS4.2 | file export built; live API not |
| DPP-1 | Map the DPP draft to battery passport requirements | WP4 | draft block only |
| REE-1 | Rare earth refining module as configuration | WP3 T3.4 | placeholder type built |
| REG-1 | Versioning and re-validation prompts | WP4 | stale-build detection built; git holds history |
| AUTH-1 | Single sign-on for a shared viewer | WP4 | not built |
| VAL-1 | Process-engineer review of every rule and window | WP2/WP3 | open (ASSUMPTIONS.md) |

Order proposed: VAL-1 and SIM-1 as soon as licences allow (M3-M4), then REC-1 and BAL-1 (M5-M6), then XY-1
and the end-user examples (M7-M8).
