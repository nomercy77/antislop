"""API and domain models for verification planning."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import re
from urllib.parse import urlparse
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Language(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"


class Capability(StrEnum):
    SYNTAX = "syntax"
    TESTS = "tests"
    STATIC_ANALYSIS = "static-analysis"
    AST_CFG = "ast-cfg"
    FORMAL_TYPE_SAFETY = "formal.type-safety"
    FORMAL_BOUNDED = "formal.bounded"
    FORMAL_CONTRACTS = "formal.contracts"
    FORMAL_THEOREM_PROVING = "formal.theorem-proving"
    AGENT_REVIEW = "agent-review"


class FindingSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SubmissionStatus(StrEnum):
    PLANNED = "planned"
    QUEUED = "queued"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PluginRunStatus(StrEnum):
    PLANNED = "planned"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PluginState(StrEnum):
    READY = "ready"
    PLANNED = "planned"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SourceSnapshot(BaseModel):
    """An immutable source reference; repository contents are never accepted directly."""

    model_config = ConfigDict(frozen=True)

    repository_url: str
    commit_sha: str

    @field_validator("repository_url")
    @classmethod
    def require_github_repository(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise ValueError("repository_url must be an https://github.com repository URL")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2 or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("repository_url must identify one GitHub owner/repository")
        return value.rstrip("/")

    @field_validator("commit_sha")
    @classmethod
    def require_commit_sha(cls, value: str) -> str:
        if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", value):
            raise ValueError("commit_sha must be a full 40- or 64-character hexadecimal commit identifier")
        return value.lower()


class SubmissionCreate(BaseModel):
    source: SourceSnapshot
    languages: set[Language] = Field(min_length=1)
    capabilities: set[Capability] = Field(min_length=1)
    paths_in_scope: list[str] = Field(default_factory=list)
    build_commands: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    intended_behavior: str | None = Field(default=None, max_length=4_000)
    formal: "FormalConfiguration | None" = None

    @field_validator("paths_in_scope")
    @classmethod
    def require_relative_paths(cls, values: list[str]) -> list[str]:
        for path in values:
            if path.startswith("/") or ".." in path.split("/"):
                raise ValueError("paths_in_scope must contain relative paths without '..'")
        return values

    @model_validator(mode="after")
    def require_tests_for_test_capability(self) -> "SubmissionCreate":
        if Capability.TESTS in self.capabilities and not self.test_commands:
            raise ValueError("test_commands are required when the tests capability is selected")
        formal_capabilities = {
            Capability.FORMAL_BOUNDED,
            Capability.FORMAL_CONTRACTS,
            Capability.FORMAL_THEOREM_PROVING,
        }
        if self.capabilities & formal_capabilities and self.formal is None:
            raise ValueError("formal configuration is required for bounded and contract verification")
        return self


class FormalConfiguration(BaseModel):
    """Paths and limits for the restricted formal-verification specifications."""

    contract_path: str = ".antislop/contracts.json"
    theorem_path: str = ".antislop/theorems.json"
    max_cases: int = Field(default=100, ge=1, le=10_000)

    @field_validator("contract_path")
    @classmethod
    def require_relative_contract_path(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            raise ValueError("contract_path must be relative and cannot contain '..'")
        return value

    @field_validator("theorem_path")
    @classmethod
    def require_relative_theorem_path(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            raise ValueError("theorem_path must be relative and cannot contain '..'")
        return value


class ExecutionPolicy(BaseModel):
    """Limits passed to a future isolated runner; the API process never executes code."""

    network_allowed: bool = False
    timeout_seconds: int = Field(default=900, ge=1, le=3_600)
    cpu_cores: int = Field(default=2, ge=1, le=8)
    memory_mb: int = Field(default=2_048, ge=256, le=16_384)
    disk_mb: int = Field(default=4_096, ge=512, le=32_768)


class PluginManifest(BaseModel):
    id: str
    version: str
    languages: set[Language]
    capabilities: set[Capability]
    state: PluginState = PluginState.PLANNED
    config_schema: dict[str, object] = Field(default_factory=dict)


class Finding(BaseModel):
    rule_id: str
    message: str
    severity: FindingSeverity = FindingSeverity.MEDIUM
    path: str | None = None
    line: int | None = Field(default=None, ge=1)
    evidence: str | None = None


class RunEvidence(BaseModel):
    command: list[str]
    exit_code: int | None = None
    log_path: str | None = None
    output_tail: str = ""
    findings: list[Finding] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime


class PluginRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    plugin_id: str
    plugin_version: str
    language: Language
    capability: Capability
    status: PluginRunStatus = PluginRunStatus.PLANNED
    policy: ExecutionPolicy
    evidence: RunEvidence | None = None


class VerificationPlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source: SourceSnapshot
    runs: list[PluginRun]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Submission(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    request: SubmissionCreate
    plan: VerificationPlan
    status: SubmissionStatus = SubmissionStatus.PLANNED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VerificationJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    submission_id: UUID
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class QueueSubmissionResponse(BaseModel):
    submission: Submission
    job: VerificationJob
