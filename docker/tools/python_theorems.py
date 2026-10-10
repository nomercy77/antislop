"""Prove a deliberately small, auditable integer-theorem DSL with Z3.

This does not execute or translate arbitrary Python.  A proven result means the
declarative statement in the submitted theorem file follows in integer
arithmetic; ``source`` is traceability metadata only.
"""

from __future__ import annotations

import argparse
import json
from functools import reduce
from operator import mul
from pathlib import Path
from typing import Any

import z3

from python.common import write_findings


class SpecificationError(ValueError):
    pass


def expression(node: Any, variables: dict[str, z3.ArithRef]) -> z3.ArithRef:
    if isinstance(node, dict):
        if set(node) == {"var"}:
            name = node["var"]
            if not isinstance(name, str) or name not in variables:
                raise SpecificationError(f"unknown integer variable: {name!r}")
            return variables[name]
        if set(node) == {"int"} and isinstance(node["int"], int) and not isinstance(node["int"], bool):
            return z3.IntVal(node["int"])
        operator = node.get("op")
        args = node.get("args")
        if operator in {"add", "mul"} and isinstance(args, list) and len(args) >= 2:
            values = [expression(value, variables) for value in args]
            return z3.Sum(values) if operator == "add" else reduce(mul, values)
        if operator == "sub" and isinstance(args, list) and len(args) == 2:
            return expression(args[0], variables) - expression(args[1], variables)
        if operator == "neg" and isinstance(args, list) and len(args) == 1:
            return -expression(args[0], variables)
    raise SpecificationError("invalid integer expression")


def proposition(node: Any, variables: dict[str, z3.ArithRef]) -> z3.BoolRef:
    if not isinstance(node, dict):
        raise SpecificationError("a proposition must be an object")
    operator = node.get("op")
    if operator in {"eq", "ne", "lt", "le", "gt", "ge"}:
        left, right = expression(node.get("left"), variables), expression(node.get("right"), variables)
        return {
            "eq": left == right, "ne": left != right, "lt": left < right,
            "le": left <= right, "gt": left > right, "ge": left >= right,
        }[operator]
    arguments = node.get("args")
    if operator in {"and", "or"} and isinstance(arguments, list) and arguments:
        values = [proposition(value, variables) for value in arguments]
        return z3.And(values) if operator == "and" else z3.Or(values)
    if operator == "not":
        return z3.Not(proposition(node.get("arg"), variables))
    raise SpecificationError("invalid proposition")


def prove(theorem: dict[str, Any]) -> tuple[str, str]:
    identifier = theorem.get("id")
    variable_types = theorem.get("variables")
    assumptions = theorem.get("assumptions", [])
    if not isinstance(identifier, str) or not identifier:
        raise SpecificationError("theorem needs a non-empty id")
    if not isinstance(variable_types, dict) or not variable_types or any(kind != "int" for kind in variable_types.values()):
        raise SpecificationError(f"{identifier}: variables must be a non-empty map of integer variables")
    if not all(isinstance(name, str) and name.isidentifier() for name in variable_types):
        raise SpecificationError(f"{identifier}: variable names must be identifiers")
    if not isinstance(assumptions, list):
        raise SpecificationError(f"{identifier}: assumptions must be a list")
    variables = {name: z3.Int(name) for name in variable_types}
    solver = z3.Solver()
    solver.add(*(proposition(item, variables) for item in assumptions))
    solver.add(z3.Not(proposition(theorem.get("conclusion"), variables)))
    result = solver.check()
    if result == z3.unsat:
        return "proved", f"{identifier}: proved over unbounded mathematical integers"
    if result == z3.sat:
        return "counterexample", f"{identifier}: counterexample {solver.model()}"
    return "unknown", f"{identifier}: solver returned unknown: {solver.reason_unknown()}"


parser = argparse.ArgumentParser()
parser.add_argument("--theorems", required=True)
arguments = parser.parse_args()

try:
    document = json.loads(Path(arguments.theorems).read_text(encoding="utf-8"))
    theorems = document["theorems"]
    if not isinstance(theorems, list) or not theorems:
        raise SpecificationError("theorem file needs a non-empty 'theorems' array")
except (OSError, json.JSONDecodeError, KeyError, SpecificationError) as error:
    print(f"invalid theorem file: {error}")
    write_findings([])
    raise SystemExit(2)

findings: list[dict[str, str]] = []
for theorem in theorems:
    try:
        if not isinstance(theorem, dict):
            raise SpecificationError("each theorem must be an object")
        status, message = prove(theorem)
        print(message)
        if status != "proved":
            findings.append({
                "rule_id": f"theorem.{status}",
                "message": message,
                "severity": "high",
                "evidence": json.dumps(theorem, sort_keys=True),
            })
    except SpecificationError as error:
        findings.append({"rule_id": "theorem.invalid-specification", "message": str(error), "severity": "high"})

write_findings(findings)
