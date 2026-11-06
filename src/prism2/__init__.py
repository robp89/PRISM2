"""PRISM2: life cycle inventory as code.

A PRISM model is a folder of plain files kept in git: a scope card, a process type
from the reviewed library, feedstock grades, run data with provenance, sign-offs and
decision records. The ``prism`` CLI checks them, reconciles balances, designs runs,
fits and benchmarks surrogate models, certifies (fail closed), generates the
inventory with ranges, and writes XYCLE import files. PRISM never calculates
impacts: background data and characterisation stay in XYCLE.
"""

__version__ = "0.1.0"
