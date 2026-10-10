from __future__ import annotations

import ast
from pathlib import Path

from python.common import location, python_files, write_findings


def finding(rule_id: str, message: str, path: Path, line: int, severity: str) -> dict[str, object]:
    return {"rule_id": rule_id, "message": message, "severity": severity, **location(path, line)}


class StaticVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.findings: list[dict[str, object]] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = self._call_name(node.func)
        if name in {"eval", "exec", "compile"}:
            self.findings.append(
                finding("python.dynamic-execution", f"Call to {name} requires review", self.path, node.lineno, "high")
            )
        if name in {"subprocess.run", "subprocess.call", "subprocess.Popen"} and any(
            keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
            for keyword in node.keywords
        ):
            self.findings.append(
                finding("python.subprocess-shell", "subprocess call enables shell=True", self.path, node.lineno, "high")
            )
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.findings.append(
                finding("python.bare-except", "Bare except catches system-level exceptions", self.path, node.lineno, "medium")
            )
        self.generic_visit(node)

    @staticmethod
    def _call_name(node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        return None


findings: list[dict[str, object]] = []
for source in python_files():
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    except (OSError, SyntaxError) as error:
        findings.append(finding("python.parse-error", str(error), source, getattr(error, "lineno", 1) or 1, "high"))
        continue
    visitor = StaticVisitor(source)
    visitor.visit(tree)
    findings.extend(visitor.findings)
write_findings(findings)
