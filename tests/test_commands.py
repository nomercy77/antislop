from antislop.models import Capability, ExecutionPolicy, Language, PluginRun, SourceSnapshot, SubmissionCreate
from antislop.plugins.commands import command_for


def test_python_syntax_command_compiles_source_without_importing_it() -> None:
    run = PluginRun(
        plugin_id="builtin.syntax",
        plugin_version="0.1.0",
        language=Language.PYTHON,
        capability=Capability.SYNTAX,
        policy=ExecutionPolicy(),
    )
    request = SubmissionCreate(
        source=SourceSnapshot(
            repository_url="https://github.com/example/verified-service",
            commit_sha="a" * 40,
        ),
        languages={Language.PYTHON},
        capabilities={Capability.SYNTAX},
    )

    command = command_for(run, request)

    assert command[:2] == ["/bin/sh", "-ceu"]
    assert "compile(" in command[2]
    assert "sys.argv[1:]" in command[2]
