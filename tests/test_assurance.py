from datetime import UTC, datetime

from antislop.models import Capability, ExecutionPolicy, Finding, Language, PluginRun, PluginRunStatus, RunEvidence
from antislop.services.assurance import completed_claim


def test_contract_finding_is_a_counterexample_not_a_pass() -> None:
    run = PluginRun(
        plugin_id="builtin.formal",
        plugin_version="0.1.0",
        language=Language.PYTHON,
        capability=Capability.FORMAL_CONTRACTS,
        policy=ExecutionPolicy(),
    )
    evidence = RunEvidence(
        command=["python", "contracts.py"],
        exit_code=0,
        findings=[Finding(rule_id="contract.contracts-counterexample", message="wrong answer")],
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )

    claim = completed_claim(run, evidence, PluginRunStatus.SUCCEEDED)

    assert claim.level == "runtime-contract-held"
    assert claim.status == "counterexample"
