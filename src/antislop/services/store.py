"""Durable submission and job storage.

SQLite keeps the first worker deployment simple. Its interface is intentionally
small so production can replace it with a transactional database adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from threading import Lock
from uuid import UUID

from antislop.models import (
    AssuranceClaim,
    JobStatus,
    PluginRunStatus,
    RunEvidence,
    Submission,
    SubmissionCreate,
    SubmissionStatus,
    VerificationJob,
    VerificationPlan,
)


class SubmissionRepository(ABC):
    @abstractmethod
    def create(self, request: SubmissionCreate, plan: VerificationPlan) -> Submission: ...

    @abstractmethod
    def get(self, submission_id: UUID) -> Submission | None: ...

    @abstractmethod
    def queue(self, submission_id: UUID) -> tuple[Submission, VerificationJob] | None: ...

    @abstractmethod
    def claim_next_job(self) -> VerificationJob | None: ...

    @abstractmethod
    def complete_job(self, job_id: UUID, error: str | None = None) -> VerificationJob | None: ...

    @abstractmethod
    def update_run(
        self,
        submission_id: UUID,
        run_id: UUID,
        run_status: PluginRunStatus,
        evidence: RunEvidence | None = None,
        claim: AssuranceClaim | None = None,
    ) -> Submission | None: ...


def _replace_run(
    submission: Submission,
    run_id: UUID,
    run_status: PluginRunStatus,
    evidence: RunEvidence | None,
    claim: AssuranceClaim | None = None,
) -> Submission:
    runs = []
    found = False
    for run in submission.plan.runs:
        if run.id == run_id:
            updates = {"status": run_status, "evidence": evidence}
            if claim is not None:
                updates["claim"] = claim
            runs.append(run.model_copy(update=updates))
            found = True
        else:
            runs.append(run)
    if not found:
        raise KeyError(f"run not found: {run_id}")
    return submission.model_copy(update={"plan": submission.plan.model_copy(update={"runs": runs})})


def _complete_submission(submission: Submission, failed: bool) -> Submission:
    return submission.model_copy(
        update={"status": SubmissionStatus.FAILED if failed else SubmissionStatus.SUCCEEDED}
    )


class InMemorySubmissionStore(SubmissionRepository):
    """Test double and local fallback; jobs disappear when its process exits."""

    def __init__(self) -> None:
        self._submissions: dict[UUID, Submission] = {}
        self._jobs: dict[UUID, VerificationJob] = {}
        self._submission_jobs: dict[UUID, UUID] = {}
        self._lock = Lock()

    def create(self, request: SubmissionCreate, plan: VerificationPlan) -> Submission:
        submission = Submission(request=request, plan=plan)
        with self._lock:
            self._submissions[submission.id] = submission
        return submission

    def get(self, submission_id: UUID) -> Submission | None:
        with self._lock:
            return self._submissions.get(submission_id)

    def queue(self, submission_id: UUID) -> tuple[Submission, VerificationJob] | None:
        with self._lock:
            submission = self._submissions.get(submission_id)
            if submission is None:
                return None
            existing_id = self._submission_jobs.get(submission_id)
            if existing_id is not None:
                return submission, self._jobs[existing_id]
            queued_runs = [run.model_copy(update={"status": PluginRunStatus.QUEUED}) for run in submission.plan.runs]
            queued_submission = submission.model_copy(
                update={
                    "plan": submission.plan.model_copy(update={"runs": queued_runs}),
                    "status": SubmissionStatus.QUEUED,
                }
            )
            job = VerificationJob(submission_id=submission_id)
            self._submissions[submission_id] = queued_submission
            self._jobs[job.id] = job
            self._submission_jobs[submission_id] = job.id
            return queued_submission, job

    def claim_next_job(self) -> VerificationJob | None:
        with self._lock:
            candidates = [job for job in self._jobs.values() if job.status == JobStatus.QUEUED]
            if not candidates:
                return None
            job = min(candidates, key=lambda item: item.created_at)
            claimed = job.model_copy(update={"status": JobStatus.RUNNING, "started_at": datetime.now(UTC)})
            self._jobs[job.id] = claimed
            return claimed

    def complete_job(self, job_id: UUID, error: str | None = None) -> VerificationJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            complete = job.model_copy(
                update={
                    "status": JobStatus.FAILED if error else JobStatus.SUCCEEDED,
                    "finished_at": datetime.now(UTC),
                    "error": error,
                }
            )
            self._jobs[job_id] = complete
            submission = self._submissions[job.submission_id]
            self._submissions[job.submission_id] = _complete_submission(submission, failed=error is not None)
            return complete

    def update_run(
        self,
        submission_id: UUID,
        run_id: UUID,
        run_status: PluginRunStatus,
        evidence: RunEvidence | None = None,
        claim: AssuranceClaim | None = None,
    ) -> Submission | None:
        with self._lock:
            submission = self._submissions.get(submission_id)
            if submission is None:
                return None
            updated = _replace_run(submission, run_id, run_status, evidence, claim)
            self._submissions[submission_id] = updated
            return updated


class SQLiteSubmissionStore(SubmissionRepository):
    """A SQLite-backed queue safe for a single worker process in the first release."""

    def __init__(self, database_path: Path) -> None:
        self._path = database_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS submissions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS verification_jobs (
                    id TEXT PRIMARY KEY,
                    submission_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _serialize(model: Submission | VerificationJob) -> str:
        return model.model_dump_json()

    def create(self, request: SubmissionCreate, plan: VerificationPlan) -> Submission:
        submission = Submission(request=request, plan=plan)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO submissions (id, payload) VALUES (?, ?)",
                (str(submission.id), self._serialize(submission)),
            )
        return submission

    def get(self, submission_id: UUID) -> Submission | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM submissions WHERE id = ?", (str(submission_id),)).fetchone()
        return Submission.model_validate_json(row["payload"]) if row else None

    def queue(self, submission_id: UUID) -> tuple[Submission, VerificationJob] | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT payload FROM submissions WHERE id = ?", (str(submission_id),)
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return None
                submission = Submission.model_validate_json(row["payload"])
                existing = connection.execute(
                    "SELECT payload FROM verification_jobs WHERE submission_id = ?", (str(submission_id),)
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    return submission, VerificationJob.model_validate_json(existing["payload"])
                queued_runs = [
                    run.model_copy(update={"status": PluginRunStatus.QUEUED}) for run in submission.plan.runs
                ]
                queued_submission = submission.model_copy(
                    update={
                        "plan": submission.plan.model_copy(update={"runs": queued_runs}),
                        "status": SubmissionStatus.QUEUED,
                    }
                )
                job = VerificationJob(submission_id=submission_id)
                connection.execute(
                    "UPDATE submissions SET payload = ? WHERE id = ?",
                    (self._serialize(queued_submission), str(submission_id)),
                )
                connection.execute(
                    "INSERT INTO verification_jobs (id, submission_id, status, created_at, payload) VALUES (?, ?, ?, ?, ?)",
                    (str(job.id), str(submission_id), job.status, job.created_at.isoformat(), self._serialize(job)),
                )
                connection.commit()
                return queued_submission, job
            except Exception:
                connection.rollback()
                raise

    def claim_next_job(self) -> VerificationJob | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT payload FROM verification_jobs WHERE status = ? ORDER BY created_at LIMIT 1",
                    (JobStatus.QUEUED,),
                ).fetchone()
                if row is None:
                    connection.commit()
                    return None
                job = VerificationJob.model_validate_json(row["payload"])
                claimed = job.model_copy(update={"status": JobStatus.RUNNING, "started_at": datetime.now(UTC)})
                connection.execute(
                    "UPDATE verification_jobs SET status = ?, payload = ? WHERE id = ?",
                    (claimed.status, self._serialize(claimed), str(job.id)),
                )
                connection.commit()
                return claimed
            except Exception:
                connection.rollback()
                raise

    def complete_job(self, job_id: UUID, error: str | None = None) -> VerificationJob | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT payload FROM verification_jobs WHERE id = ?", (str(job_id),)
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return None
                job = VerificationJob.model_validate_json(row["payload"])
                completed = job.model_copy(
                    update={
                        "status": JobStatus.FAILED if error else JobStatus.SUCCEEDED,
                        "finished_at": datetime.now(UTC),
                        "error": error,
                    }
                )
                submission_row = connection.execute(
                    "SELECT payload FROM submissions WHERE id = ?", (str(job.submission_id),)
                ).fetchone()
                if submission_row is None:
                    raise RuntimeError(f"job {job.id} references a missing submission")
                submission = Submission.model_validate_json(submission_row["payload"])
                complete_submission = _complete_submission(submission, failed=error is not None)
                connection.execute(
                    "UPDATE verification_jobs SET status = ?, payload = ? WHERE id = ?",
                    (completed.status, self._serialize(completed), str(job_id)),
                )
                connection.execute(
                    "UPDATE submissions SET payload = ? WHERE id = ?",
                    (self._serialize(complete_submission), str(job.submission_id)),
                )
                connection.commit()
                return completed
            except Exception:
                connection.rollback()
                raise

    def update_run(
        self,
        submission_id: UUID,
        run_id: UUID,
        run_status: PluginRunStatus,
        evidence: RunEvidence | None = None,
        claim: AssuranceClaim | None = None,
    ) -> Submission | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT payload FROM submissions WHERE id = ?", (str(submission_id),)
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return None
                updated = _replace_run(
                    Submission.model_validate_json(row["payload"]), run_id, run_status, evidence, claim
                )
                connection.execute(
                    "UPDATE submissions SET payload = ? WHERE id = ?",
                    (self._serialize(updated), str(submission_id)),
                )
                connection.commit()
                return updated
            except Exception:
                connection.rollback()
                raise
