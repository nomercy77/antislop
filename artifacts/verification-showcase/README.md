# Verification showcase artifacts

This directory is a compact, versioned evidence bundle from the verification work demonstrated in this repository. It intentionally excludes transient SQLite queues, local API data, credentials, and exploratory failures.

## Included evidence

- `proofs.json`: two successful source-linked Z3 theorem claims for `square()` in `examples/theorem_sample_repo/math_utils.py`.
- `findings.json`: the normalized findings output for that theorem run; it is empty because both submitted theorems were proved.
- `theorem.log`: the runner’s human-readable proof output.
- `run-summary.json`: the commands and pass counts for the backend, core verification, and UI/API-adapter checks completed during the showcase.

The proof applies to the documented restricted integer-expression model only. It is evidence of the stated theorem, not a claim that the complete Python runtime, imports, exceptions, heap state, or arbitrary program behavior has been verified.
