# Verification showcase artifacts

This directory is a compact, versioned evidence bundle from the verification work demonstrated in this repository. It intentionally excludes transient SQLite queues, local API data, credentials, and exploratory failures.

## Included evidence

- `proofs.json`: two successful source-linked Z3 theorem claims for `square()` in `examples/theorem_sample_repo/math_utils.py`.
- `findings.json`: the normalized findings output for that theorem run; it is empty because both submitted theorems were proved.
- `theorem.log`: the runner’s human-readable proof output.
- `python-formal-contracts-findings.json`: successful Python `formal.contracts` output for the `square()` examples; empty findings means every declared case held.
- `javascript-bounded-contracts-findings.json`: successful JavaScript `formal.bounded` output for the finite `add()` domain; empty findings means every expanded case held.
- `run-summary.json`: the commands and pass counts for the backend, core verification, and UI/API-adapter checks completed during the showcase.

The contract outputs are finite runtime checks, not proofs: they establish only that their declared or generated cases held within the recorded bound. The theorem applies to the documented restricted integer-expression model only. It is evidence of the stated theorem, not a claim that the complete Python runtime, imports, exceptions, heap state, or arbitrary program behavior has been verified.
