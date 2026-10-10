from __future__ import annotations

import argparse
import importlib
import itertools
import json
from pathlib import Path
import sys
from typing import Any

from python.common import write_findings


sys.path.insert(0, str(Path.cwd()))


def expand_cases(target: dict[str, Any], max_cases: int) -> list[dict[str, Any]]:
    cases = list(target.get("cases", []))
    parameters = target.get("parameters", [])
    if parameters:
        values = [parameter.get("values", []) for parameter in parameters]
        if not all(isinstance(option, list) and option for option in values):
            raise ValueError("each bounded parameter needs a non-empty values list")
        for arguments in itertools.product(*values):
            cases.append({"args": list(arguments)})
            if len(cases) > max_cases:
                raise ValueError(f"generated cases exceed max_cases={max_cases}")
    if not cases:
        raise ValueError("each contract target needs cases or bounded parameters")
    if len(cases) > max_cases:
        raise ValueError(f"contract has more than max_cases={max_cases} cases")
    return cases


def verify_assertions(result: Any, case: dict[str, Any]) -> str | None:
    if "expected" in case and result != case["expected"]:
        return f"expected {case['expected']!r}, got {result!r}"
    assertions = case.get("assert", {})
    if not isinstance(assertions, dict):
        return "assert must be an object"
    if "type" in assertions and type(result).__name__ != assertions["type"]:
        return f"expected result type {assertions['type']}, got {type(result).__name__}"
    if "minimum" in assertions and result < assertions["minimum"]:
        return f"expected result >= {assertions['minimum']!r}, got {result!r}"
    if "maximum" in assertions and result > assertions["maximum"]:
        return f"expected result <= {assertions['maximum']!r}, got {result!r}"
    if assertions.get("truthy") is True and not result:
        return "expected a truthy result"
    return None


parser = argparse.ArgumentParser()
parser.add_argument("--contracts", required=True)
parser.add_argument("--max-cases", type=int, required=True)
parser.add_argument("--mode", choices={"bounded", "contracts"}, required=True)
arguments = parser.parse_args()

try:
    document = json.loads(Path(arguments.contracts).read_text(encoding="utf-8"))
    targets = document["targets"]
    if not isinstance(targets, list):
        raise ValueError("targets must be a list")
except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
    print(f"invalid contract file: {error}")
    raise SystemExit(2)

findings: list[dict[str, object]] = []
for target in targets:
    try:
        module = importlib.import_module(target["module"])
        function: Any = module
        for part in target["function"].split("."):
            function = getattr(function, part)
        cases = expand_cases(target, arguments.max_cases)
    except (ImportError, AttributeError, KeyError, TypeError, ValueError) as error:
        findings.append(
            {
                "rule_id": "contract.invalid-target",
                "message": str(error),
                "severity": "high",
                "evidence": repr(target),
            }
        )
        continue
    for index, case in enumerate(cases):
        try:
            result = function(*case.get("args", []), **case.get("kwargs", {}))
            error = verify_assertions(result, case)
        except Exception as exception:  # The target code is untrusted and is isolated by the runner.
            error = f"raised {type(exception).__name__}: {exception}"
        if error:
            findings.append(
                {
                    "rule_id": f"contract.{arguments.mode}-counterexample",
                    "message": error,
                    "severity": "high",
                    "evidence": json.dumps({
                        "target": f"{target.get('module')}.{target.get('function')}",
                        "case_index": index,
                        "args": case.get("args", []),
                        "kwargs": case.get("kwargs", {}),
                        "case": case,
                    }, sort_keys=True, default=repr),
                }
            )
write_findings(findings)
