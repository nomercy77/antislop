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
    AGENT_REVIEW = "agent-review"


class SubmissionStatus(StrEnum):
    PLANNED = "planned"
    QUEUED = "queued"


class PluginRunStatus(StrEnum):
    PLANNED = "planned"
    QUEUED = "queued"


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
        if not re.fullmatch(r"[0-9a-fA-F]{7,64}", value):
            raise ValueError("commit_sha must be a 7-64 character hexadecimal commit identifier")
        return value.lower()


class SubmissionCreate(BaseModel):
    source: SourceSnapshot
    languages: set[Language] = Field(min_length=1)
    capabilities: set[Capability] = Field(min_length=1)
    paths_in_scope: list[str] = Field(default_factory=list)
    build_commands: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    intended_behavior: str | None = Field(default=None, max_length=4_000)

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
        return self


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
    config_schema: dict[str, object] = Field(default_factory=dict)


class PluginRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    plugin_id: str
    plugin_version: str
    language: Language
    capability: Capability
    status: PluginRunStatus = PluginRunStatus.PLANNED
    policy: ExecutionPolicy


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
