# D-001 Model family decision rule, written before fitting

**Status:** taken (example)

For every output, fit polynomial (degree 2), a one-layer neural network and a Gaussian process on the
same 80/20 split (seed 42). Choose the family with the highest held-out R². If the polynomial is within
0.01 of the best, choose it, because XYCLE can evaluate it as a formula and the reviewer can read it.

Why written first: the grant's ANN-1 task compares families; choosing the rule after seeing results
would bias the comparison.
