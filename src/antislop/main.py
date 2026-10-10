"""FastAPI entrypoint for verification planning."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException, status

from antislop.models import PluginManifest, Submission, SubmissionCreate
from antislop.plugins.builtins import built_in_registry
from antislop.services.planner import UnsupportedCapabilityError, VerificationPlanner
from antislop.services.store import SubmissionStore


def create_app() -> FastAPI:
    app = FastAPI(title="antislop verification API", version="0.1.0")
    registry = built_in_registry()
    planner = VerificationPlanner(registry)
    store = SubmissionStore()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/capabilities", response_model=list[PluginManifest])
    def list_capabilities() -> list[PluginManifest]:
        return registry.list()

    @app.post("/v1/submissions", response_model=Submission, status_code=status.HTTP_201_CREATED)
    def create_submission(request: SubmissionCreate) -> Submission:
        try:
            plan = planner.create_plan(request)
        except UnsupportedCapabilityError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
        return store.create(request, plan)

    @app.get("/v1/submissions/{submission_id}", response_model=Submission)
    def get_submission(submission_id: UUID) -> Submission:
        submission = store.get(submission_id)
        if submission is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found")
        return submission

    @app.post("/v1/submissions/{submission_id}/queue", response_model=Submission)
    def queue_submission(submission_id: UUID) -> Submission:
        submission = store.queue(submission_id)
        if submission is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found")
        return submission

    return app


app = create_app()
