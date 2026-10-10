"""Commands for the executable verification plugins.

Commands are interpreted only inside the sandbox container. They are never
passed through a host shell.
"""

from __future__ import annotations

from antislop.models import Capability, Language, PluginRun, SubmissionCreate


class UnsupportedExecutablePluginError(ValueError):
    pass


def command_for(run: PluginRun, request: SubmissionCreate) -> list[str]:
    if run.capability == Capability.SYNTAX:
        return _syntax_command(run.language)
    if run.capability == Capability.TESTS:
        return ["/bin/sh", "-ceu", "\n".join(request.test_commands)]
    if run.capability == Capability.STATIC_ANALYSIS:
        return _tool_command(run.language, "static")
    if run.capability == Capability.AST_CFG:
        return _tool_command(run.language, "cfg")
    if run.capability == Capability.FORMAL_TYPE_SAFETY:
        return _tool_command(run.language, "type_safety")
    if run.capability in {Capability.FORMAL_BOUNDED, Capability.FORMAL_CONTRACTS}:
        if request.formal is None:
            raise UnsupportedExecutablePluginError("formal configuration is required")
        mode = "bounded" if run.capability == Capability.FORMAL_BOUNDED else "contracts"
        return _contract_command(run.language, request.formal.contract_path, request.formal.max_cases, mode)
    raise UnsupportedExecutablePluginError(
        f"plugin '{run.plugin_id}' does not have an executable command for '{run.capability}'"
    )


def _syntax_command(language: Language) -> list[str]:
    if language == Language.PYTHON:
        # compile() parses without importing application code or creating .pyc files.
        command = (
            "find . -type f -name '*.py' -exec python -B -c "
            "'import pathlib, sys; "
            "[compile(pathlib.Path(name).read_text(encoding=\"utf-8\"), name, \"exec\") "
            "for name in sys.argv[1:]]' {} +"
        )
    elif language == Language.JAVASCRIPT:
        command = (
            "find . -type f \\( -name '*.js' -o -name '*.mjs' -o -name '*.cjs' \\) "
            "-exec sh -ceu 'for source do node --check \"$source\"; done' _ {} +"
        )
    else:  # pragma: no cover - Language is closed today, but retain a safe boundary.
        raise UnsupportedExecutablePluginError(f"syntax checking is unavailable for '{language}'")
    return ["/bin/sh", "-ceu", command]


def _tool_command(language: Language, tool: str) -> list[str]:
    if language == Language.PYTHON:
        return ["python", f"/opt/antislop/python_{tool}.py"]
    if language == Language.JAVASCRIPT:
        return ["node", f"/opt/antislop/javascript_{tool}.cjs"]
    raise UnsupportedExecutablePluginError(f"{tool} is unavailable for '{language}'")


def _contract_command(language: Language, contract_path: str, max_cases: int, mode: str) -> list[str]:
    if language == Language.PYTHON:
        executable = "python"
        script = "/opt/antislop/python_contracts.py"
    elif language == Language.JAVASCRIPT:
        executable = "node"
        script = "/opt/antislop/javascript_contracts.cjs"
    else:  # pragma: no cover - Language is closed today, but retain a safe boundary.
        raise UnsupportedExecutablePluginError(f"contracts are unavailable for '{language}'")
    return [executable, script, "--contracts", contract_path, "--max-cases", str(max_cases), "--mode", mode]
