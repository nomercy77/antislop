from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from antislop.agent_review import AgentReviewProvider
from antislop.models import Capability, Finding, Language, RunEvidence, SourceSnapshot, SubmissionCreate
from antislop.plugins.builtins import built_in_registry
from antislop.services.planner import VerificationPlanner
from antislop.services.store import InMemorySubmissionStore
from antislop.worker import VerificationWorker


class FakeSandbox:
    @contextmanager
    def checkout(self, source: SourceSnapshot) -> Iterator[Path]:
        yield Path(".")

    def execute(self, workspace: Path, run, command):  # pragma: no cover - agent test never invokes Docker.
        return RunEvidence(command=command, exit_code=0, started_at=datetime.now(UTC), finished_at=datetime.now(UTC))


class FakeAgentProvider(AgentReviewProvider):
    def review(self, source: SourceSnapshot, workspace: Path) -> tuple[list[Finding], str]:
        return [Finding(rule_id="agent.example", message="review finding", severity="low")], "one finding"


def test_agent_review_persists_provider_findings() -> None:
    request = SubmissionCreate(
        source=SourceSnapshot(
            repository_url="https://github.com/example/verified-service",
            commit_sha="a" * 40,
        ),
        languages={Language.PYTHON},
        capabilities={Capability.AGENT_REVIEW},
    )
    store = InMemorySubmissionStore()
    submission = store.create(request, VerificationPlanner(built_in_registry()).create_plan(request))
    store.queue(submission.id)

    assert VerificationWorker(store, FakeSandbox(), FakeAgentProvider()).run_once()

    run = store.get(submission.id).plan.runs[0]  # type: ignore[union-attr]
    assert run.status == "succeeded"
    assert run.evidence is not None
    assert run.evidence.findings[0].rule_id == "agent.example"
