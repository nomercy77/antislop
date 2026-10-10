# Theorem-proving sample

This directory is a small standalone Python repository. Its theorem file uses
the antislop integer-arithmetic DSL and is intended to be submitted with
`formal.theorem-proving` and `formal.theorem_path` set to `.antislop/theorems.json`.

It also contains `.antislop/contracts.json` for the existing bounded runtime
contract runner (`formal.contracts`). That check executes three examples of
`square`; the theorem runner proves the declarative integer statement without
sampling values.

The `source` field identifies the implementation that the theorem documents. It
is traceability metadata: the current proof engine proves the mathematical DSL
statement, not equivalence between arbitrary Python code and that statement.
