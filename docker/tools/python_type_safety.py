from __future__ import annotations

import re

from mypy import api

from python.common import write_findings


PATTERN = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+)(?::\d+)?: error: (?P<message>.+?)(?: \[(?P<code>[^\]]+)\])?$"
)
stdout, stderr, exit_status = api.run(
    ["--show-error-codes", "--no-error-summary", "--hide-error-context", "--check-untyped-defs", "."]
)
findings = []
for line in stdout.splitlines():
    match = PATTERN.match(line)
    if match:
        findings.append(
            {
                "rule_id": f"mypy.{match.group('code') or 'error'}",
                "message": match.group("message"),
                "severity": "medium",
                "path": match.group("path"),
                "line": int(match.group("line")),
                "evidence": line,
            }
        )
write_findings(findings)
print(stdout, end="")
print(stderr, end="")
raise SystemExit(0 if exit_status in {0, 1} else exit_status)
