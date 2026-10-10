from pathlib import Path

from antislop.models import Capability, Language, SourceSnapshot, SubmissionCreate
from antislop.plugins.builtins import built_in_registry
from antislop.services.planner import VerificationPlanner
from antislop.services.store import SQLiteSubmissionStore


def test_sqlite_queue_claims_and_completes_a_job(tmp_path: Path) -> None:
    store = SQLiteSubmissionStore(tmp_path / "antislop.sqlite3")
    request = SubmissionCreate(
        source=SourceSnapshot(
            repository_url="https://github.com/example/verified-service",
            commit_sha="a" * 40,
        ),
        languages={Language.PYTHON},
        capabilities={Capability.SYNTAX},
    )
    submission = store.create(request, VerificationPlanner(built_in_registry()).create_plan(request))

    queued_submission, job = store.queue(submission.id) or (None, None)
    assert queued_submission is not None
    assert job is not None
    assert queued_submission.status == "queued"

    claimed = store.claim_next_job()
    assert claimed is not None
    assert claimed.id == job.id
    completed = store.complete_job(claimed.id)

    assert completed is not None
    assert completed.status == "succeeded"
    assert store.get(submission.id).status == "succeeded"  # type: ignore[union-attr]
