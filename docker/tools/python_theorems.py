"""Prove a deliberately small, auditable integer-theorem DSL with Z3.

When a theorem includes ``source``, this tool links a single-return-expression
Python function to the theorem's ``result`` variable. Unsupported source is
rejected rather than treated as linked.
"""

from __future__ import annotations

import argparse
import ast
import json
from functools import reduce
from operator import mul
from pathlib import Path
from typing import Any

import z3

from python.common import ARTIFACTS, write_findings


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


def source_expression(source: Any, variables: dict[str, z3.ArithRef]) -> z3.ArithRef:
    if not isinstance(source, dict) or set(source) != {"path", "symbol"}:
        raise SpecificationError("source must contain exactly relative path and function symbol")
    path, symbol = source["path"], source["symbol"]
    if not isinstance(path, str) or path.startswith("/") or ".." in path.split("/"):
        raise SpecificationError("source path must be relative and cannot contain '..'")
    if not isinstance(symbol, str) or not symbol.isidentifier():
        raise SpecificationError("source symbol must be a Python identifier")
    try:
        module = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
    except (OSError, SyntaxError) as error:
        raise SpecificationError(f"unable to parse linked source: {error}") from error
    function = next((node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == symbol), None)
    if function is None:
        raise SpecificationError(f"linked function not found: {path}:{symbol}")
    body = [node for node in function.body if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str)]
    if function.args.vararg or function.args.kwarg or function.args.defaults or function.args.kwonlyargs or len(body) != 1 or not isinstance(body[0], ast.Return):
        raise SpecificationError("linked function must have positional parameters and one return expression")
    parameters = [argument.arg for argument in function.args.args]
    if set(parameters) != set(variables):
        raise SpecificationError("linked function parameters must match theorem variables")

    def translate(node: ast.expr) -> z3.ArithRef:
        if isinstance(node, ast.Name) and node.id in variables:
            return variables[node.id]
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            return z3.IntVal(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            left, right = translate(node.left), translate(node.right)
            return left + right if isinstance(node.op, ast.Add) else left - right if isinstance(node.op, ast.Sub) else left * right
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -translate(node.operand)
        raise SpecificationError("linked return expression supports only integer constants, parameters, +, -, *, and unary -")

    if body[0].value is None:
        raise SpecificationError("linked function must return an integer expression")
    return translate(body[0].value)


def prove(theorem: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
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
    linked = "source" in theorem
    if linked:
        variables["result"] = source_expression(theorem["source"], variables)
    solver = z3.Solver()
    solver.add(*(proposition(item, variables) for item in assumptions))
    solver.add(z3.Not(proposition(theorem.get("conclusion"), variables)))
    result = solver.check()
    if result == z3.unsat:
        suffix = " with linked source expression" if linked else ""
        return "proved", f"{identifier}: proved over unbounded mathematical integers{suffix}", {"linked_source": linked}
    if result == z3.sat:
        model = {name: str(solver.model().eval(value, model_completion=True)) for name, value in variables.items() if name != "result"}
        return "counterexample", f"{identifier}: counterexample {model}", {"linked_source": linked, "counterexample": model}
    return "unknown", f"{identifier}: solver returned unknown: {solver.reason_unknown()}", {"linked_source": linked, "reason": solver.reason_unknown()}


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
proofs: list[dict[str, Any]] = []
for theorem in theorems:
    try:
        if not isinstance(theorem, dict):
            raise SpecificationError("each theorem must be an object")
        status, message, detail = prove(theorem)
        print(message)
        proofs.append({"id": theorem.get("id"), "status": status, "message": message, **detail})
        if status != "proved":
            findings.append({
                "rule_id": f"theorem.{status}",
                "message": message,
                "severity": "high",
                "evidence": json.dumps({"theorem": theorem, **detail}, sort_keys=True),
            })
    except SpecificationError as error:
        proofs.append({"id": theorem.get("id") if isinstance(theorem, dict) else None, "status": "invalid", "message": str(error)})
        findings.append({"rule_id": "theorem.invalid-specification", "message": str(error), "severity": "high"})

write_findings(findings)
ARTIFACTS.mkdir(parents=True, exist_ok=True)
(ARTIFACTS / "proofs.json").write_text(json.dumps(proofs, indent=2, sort_keys=True), encoding="utf-8")
