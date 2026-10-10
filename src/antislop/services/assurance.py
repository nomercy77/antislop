"""Explicit, non-overlapping assurance claims for verification runs."""

from antislop.models import (
    AssuranceClaim,
    AssuranceLevel,
    AssuranceStatus,
    Capability,
    PluginRun,
    PluginRunStatus,
    RunEvidence,
)


_LEVELS = {
    Capability.SYNTAX: (AssuranceLevel.SYNTAX_VALID, "Source parses under the configured runner."),
    Capability.TESTS: (AssuranceLevel.TESTS_PASSED, "Configured test commands completed successfully."),
    Capability.STATIC_ANALYSIS: (AssuranceLevel.ANALYSIS_COMPLETED, "Static-analysis rules completed."),
    Capability.AST_CFG: (AssuranceLevel.ANALYSIS_COMPLETED, "AST/control-flow rules completed."),
    Capability.FORMAL_TYPE_SAFETY: (AssuranceLevel.TYPE_SAFETY_CHECKED, "Type checker completed."),
    Capability.FORMAL_BOUNDED: (AssuranceLevel.BOUNDED_CONTRACT_HELD, "Contract held within the recorded finite bound."),
    Capability.FORMAL_CONTRACTS: (AssuranceLevel.RUNTIME_CONTRACT_HELD, "Runtime contract cases held."),
    Capability.FORMAL_THEOREM_PROVING: (AssuranceLevel.THEOREM_PROVED, "Restricted integer theorem was proved."),
    Capability.AGENT_REVIEW: (AssuranceLevel.AGENT_REVIEW_COMPLETED, "Trusted provider returned a review result."),
}


def planned_claim(capability: Capability) -> AssuranceClaim:
    level, summary = _LEVELS[capability]
    return AssuranceClaim(level=level, summary=summary)


def completed_claim(run: PluginRun, evidence: RunEvidence | None, status: PluginRunStatus) -> AssuranceClaim:
    claim = planned_claim(run.capability)
    if status == PluginRunStatus.FAILED or evidence is None or evidence.exit_code != 0:
        return claim.model_copy(update={"status": AssuranceStatus.FAILED, "summary": "Verification run failed."})
    rules = {finding.rule_id for finding in evidence.findings}
    if run.capability == Capability.FORMAL_THEOREM_PROVING:
        if "theorem.counterexample" in rules:
            return claim.model_copy(update={"status": AssuranceStatus.COUNTEREXAMPLE, "summary": "A theorem counterexample was recorded."})
        if "theorem.unknown" in rules:
            return claim.model_copy(update={"status": AssuranceStatus.INCONCLUSIVE, "summary": "The solver could not prove the theorem."})
        if evidence.findings:
            return claim.model_copy(update={"status": AssuranceStatus.FINDINGS, "summary": "The theorem specification is invalid or unsupported."})
        return claim.model_copy(update={"status": AssuranceStatus.PROVED})
    if run.capability in {Capability.FORMAL_BOUNDED, Capability.FORMAL_CONTRACTS} and evidence.findings:
        return claim.model_copy(update={"status": AssuranceStatus.COUNTEREXAMPLE, "summary": "A contract counterexample was recorded."})
    if evidence.findings:
        return claim.model_copy(update={"status": AssuranceStatus.FINDINGS, "summary": "Verification completed with findings."})
    return claim.model_copy(update={"status": AssuranceStatus.SATISFIED})
