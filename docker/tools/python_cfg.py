from __future__ import annotations

import ast
from pathlib import Path

from python.common import location, python_files, write_findings


TERMINAL = (ast.Return, ast.Raise, ast.Break, ast.Continue)


def inspect_body(body: list[ast.stmt], path: Path, findings: list[dict[str, object]]) -> None:
    terminated = False
    for statement in body:
        if terminated:
            findings.append(
                {
                    "rule_id": "python.cfg-unreachable",
                    "message": "Statement is unreachable after terminal control flow",
                    "severity": "medium",
                    **location(path, statement.lineno),
                }
            )
        if isinstance(statement, TERMINAL):
            terminated = True
        for attribute in ("body", "orelse", "finalbody"):
            nested = getattr(statement, attribute, None)
            if isinstance(nested, list):
                inspect_body(nested, path, findings)


findings: list[dict[str, object]] = []
for source in python_files():
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    except (OSError, SyntaxError):
        continue
    inspect_body(tree.body, source, findings)
write_findings(findings)
