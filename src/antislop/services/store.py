"""Temporary in-memory persistence for the API scaffold."""

from __future__ import annotations

from threading import Lock
from uuid import UUID

from antislop.models import PluginRunStatus, Submission, SubmissionCreate, SubmissionStatus, VerificationPlan


class SubmissionStore:
    def __init__(self) -> None:
        self._submissions: dict[UUID, Submission] = {}
        self._lock = Lock()

    def create(self, request: SubmissionCreate, plan: VerificationPlan) -> Submission:
        submission = Submission(request=request, plan=plan)
        with self._lock:
            self._submissions[submission.id] = submission
        return submission

    def get(self, submission_id: UUID) -> Submission | None:
        with self._lock:
            return self._submissions.get(submission_id)

    def queue(self, submission_id: UUID) -> Submission | None:
        with self._lock:
            submission = self._submissions.get(submission_id)
            if submission is None:
                return None
            queued_runs = [run.model_copy(update={"status": PluginRunStatus.QUEUED}) for run in submission.plan.runs]
            queued_plan = submission.plan.model_copy(update={"runs": queued_runs})
            queued_submission = submission.model_copy(
                update={"plan": queued_plan, "status": SubmissionStatus.QUEUED}
            )
            self._submissions[submission_id] = queued_submission
            return queued_submission
