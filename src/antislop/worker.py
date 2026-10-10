"""Process queued verification jobs outside the FastAPI process."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import time

from antislop.agent_review import AgentReviewError, AgentReviewProvider, HttpAgentReviewProvider
from antislop.models import Capability, PluginRun, PluginRunStatus, RunEvidence
from antislop.plugins.commands import command_for
from antislop.sandbox import DockerSandbox, DockerSandboxError
from antislop.services.store import SQLiteSubmissionStore, SubmissionRepository


class VerificationWorker:
    def __init__(
        self,
        store: SubmissionRepository,
        sandbox: DockerSandbox,
        agent_provider: AgentReviewProvider | None = None,
    ) -> None:
        self._store = store
        self._sandbox = sandbox
        self._agent_provider = agent_provider or HttpAgentReviewProvider.from_environment()

    def run_once(self) -> bool:
        job = self._store.claim_next_job()
        if job is None:
            return False
        submission = self._store.get(job.submission_id)
        if submission is None:
            self._store.complete_job(job.id, "submission was deleted before its job started")
            return True
        failures: list[str] = []
        try:
            with self._sandbox.checkout(submission.request.source) as workspace:
                for run in submission.plan.runs:
                    self._store.update_run(submission.id, run.id, PluginRunStatus.RUNNING)
                    try:
                        evidence = (
                            self._run_agent_review(workspace, run, submission.request.source)
                            if run.capability == Capability.AGENT_REVIEW
                            else self._sandbox.execute(workspace, run, command_for(run, submission.request))
                        )
                        run_status = (
                            PluginRunStatus.SUCCEEDED if evidence.exit_code == 0 else PluginRunStatus.FAILED
                        )
                        self._store.update_run(submission.id, run.id, run_status, evidence)
                        if run_status == PluginRunStatus.FAILED:
                            failures.append(f"{run.capability} failed with exit code {evidence.exit_code}")
                    except (AgentReviewError, DockerSandboxError, OSError, ValueError) as error:
                        self._store.update_run(submission.id, run.id, PluginRunStatus.FAILED)
                        failures.append(f"{run.capability}: {error}")
        except (AgentReviewError, DockerSandboxError, OSError, ValueError) as error:
            for run in submission.plan.runs:
                self._store.update_run(submission.id, run.id, PluginRunStatus.FAILED)
            failures.append(str(error))
        self._store.complete_job(job.id, "; ".join(failures) if failures else None)
        return True

    def _run_agent_review(self, workspace: Path, run: PluginRun, source) -> RunEvidence:
        started_at = datetime.now(UTC)
        findings, summary = self._agent_provider.review(source, workspace)
        return RunEvidence(
            command=["agent-review"],
            exit_code=0,
            output_tail=summary,
            findings=findings,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run antislop Docker-sandboxed verification jobs")
    parser.add_argument("--database-path", type=Path, default=Path(".antislop/antislop.sqlite3"))
    parser.add_argument("--artifacts-dir", type=Path, default=Path(".antislop/artifacts"))
    parser.add_argument("--once", action="store_true", help="process at most one job")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    arguments = parser.parse_args()

    worker = VerificationWorker(
        SQLiteSubmissionStore(arguments.database_path),
        DockerSandbox(arguments.artifacts_dir),
    )
    if arguments.once:
        worker.run_once()
        return 0
    while True:
        if not worker.run_once():
            time.sleep(arguments.poll_interval)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
