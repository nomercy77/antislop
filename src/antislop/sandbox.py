"""Docker-backed execution of untrusted verification jobs."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Iterator
from uuid import uuid4

from antislop.models import Finding, Language, PluginRun, RunEvidence, SourceSnapshot


class DockerSandboxError(RuntimeError):
    pass


@dataclass(frozen=True)
class DockerSandboxSettings:
    docker_binary: str = "docker"
    git_image: str = "alpine/git:2.49.1"
    python_image: str = "antislop-runner-python:0.1.0"
    javascript_image: str = "antislop-runner-javascript:0.1.0"
    checkout_timeout_seconds: int = 120
    output_tail_bytes: int = 65_536


class DockerSandbox:
    """Fetches a pinned source snapshot, then verifies it without network access."""

    def __init__(self, artifacts_root: Path, settings: DockerSandboxSettings | None = None) -> None:
        self._artifacts_root = artifacts_root
        self._settings = settings or DockerSandboxSettings()

    @contextmanager
    def checkout(self, source: SourceSnapshot) -> Iterator[Path]:
        with tempfile.TemporaryDirectory(prefix="antislop-source-") as temporary_directory:
            workspace = Path(temporary_directory) / "source"
            workspace.mkdir()
            # The fetch image runs unprivileged and receives only an empty workspace.
            # It needs a network solely to fetch the already validated GitHub URL.
            workspace.chmod(0o777)
            script = "\n".join(
                [
                    "git init -q .",
                    "git remote add origin \"$ANTISLOP_REPOSITORY_URL\"",
                    "git fetch --depth=1 origin \"$ANTISLOP_COMMIT_SHA\"",
                    "git checkout --detach --force -q FETCH_HEAD",
                    "actual=$(git rev-parse HEAD)",
                    "case \"$actual\" in \"$ANTISLOP_COMMIT_SHA\"*) ;; *) exit 42 ;; esac",
                ]
            )
            completed = self._docker_run(
                [
                    "--network",
                    "bridge",
                    "--read-only",
                    "--tmpfs",
                    "/tmp:rw,noexec,nosuid,nodev,size=64m",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges=true",
                    "--pids-limit",
                    "128",
                    "--memory",
                    "512m",
                    "--memory-swap",
                    "512m",
                    "--cpus",
                    "1",
                    "--user",
                    "65532:65532",
                    "--workdir",
                    "/workspace",
                    "--env",
                    f"ANTISLOP_REPOSITORY_URL={source.repository_url}",
                    "--env",
                    f"ANTISLOP_COMMIT_SHA={source.commit_sha}",
                    "--mount",
                    self._mount(workspace, "/workspace", read_only=False),
                    "--entrypoint",
                    "/bin/sh",
                    self._settings.git_image,
                    "-ceu",
                    script,
                ],
                timeout_seconds=self._settings.checkout_timeout_seconds,
            )
            if completed.returncode != 0:
                raise DockerSandboxError(f"unable to fetch pinned source snapshot: {self._tail(completed.stdout)}")
            yield workspace

    def execute(
        self,
        workspace: Path,
        run: PluginRun,
        command: list[str],
    ) -> RunEvidence:
        started_at = datetime.now(UTC)
        artifact_directory = self._artifacts_root / str(run.id)
        artifact_directory.mkdir(parents=True, exist_ok=True)
        artifact_directory.chmod(0o777)
        image = self._image_for(run.language)
        image_id = self._image_id(image)
        completed = self._docker_run(
            [
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=64m",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges=true",
                "--pids-limit",
                str(max(64, run.policy.cpu_cores * 128)),
                "--memory",
                f"{run.policy.memory_mb}m",
                "--memory-swap",
                f"{run.policy.memory_mb}m",
                "--cpus",
                str(run.policy.cpu_cores),
                "--user",
                "65532:65532",
                "--workdir",
                "/workspace",
                "--env",
                "HOME=/tmp",
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                "--env",
                "ANTISLOP_ARTIFACTS_DIR=/artifacts",
                "--mount",
                self._mount(workspace, "/workspace", read_only=True),
                "--mount",
                self._mount(artifact_directory, "/artifacts", read_only=False),
                "--entrypoint",
                command[0],
                image,
                *command[1:],
            ],
            timeout_seconds=run.policy.timeout_seconds,
        )
        finished_at = datetime.now(UTC)
        log_path = artifact_directory / "container.log"
        log_path.write_text(completed.stdout, encoding="utf-8")
        return RunEvidence(
            command=command,
            exit_code=completed.returncode,
            log_path=str(log_path),
            output_tail=self._tail(completed.stdout),
            findings=self._read_findings(artifact_directory),
            runner_image=image,
            runner_image_id=image_id,
            started_at=started_at,
            finished_at=finished_at,
        )

    def _docker_run(self, arguments: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        container_name = f"antislop-{uuid4().hex}"
        command = [
            self._settings.docker_binary,
            "run",
            "--rm",
            "--pull",
            "never",
            "--name",
            container_name,
            *arguments,
        ]
        try:
            return subprocess.run(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as error:
            raise DockerSandboxError("Docker CLI is unavailable to the worker") from error
        except subprocess.TimeoutExpired as error:
            subprocess.run(
                [self._settings.docker_binary, "kill", container_name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            output = error.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            return subprocess.CompletedProcess(command, returncode=124, stdout=f"timed out\n{output}")

    @staticmethod
    def _mount(path: Path, destination: str, *, read_only: bool) -> str:
        mode = "readonly" if read_only else ""
        return f"type=bind,src={path.resolve()},dst={destination}{',' + mode if mode else ''}"

    def _image_for(self, language: Language) -> str:
        if language == Language.PYTHON:
            return self._settings.python_image
        if language == Language.JAVASCRIPT:
            return self._settings.javascript_image
        raise DockerSandboxError(f"no runner image is configured for '{language}'")

    def _image_id(self, image: str) -> str | None:
        """Best-effort immutable local image identity; execution need not depend on it."""
        try:
            completed = subprocess.run(
                [self._settings.docker_binary, "image", "inspect", "--format", "{{.Id}}", image],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        image_id = completed.stdout.strip()
        return image_id or None

    def _tail(self, output: str) -> str:
        encoded = output.encode("utf-8", errors="replace")
        return encoded[-self._settings.output_tail_bytes :].decode("utf-8", errors="replace")

    @staticmethod
    def _read_findings(artifact_directory: Path) -> list[Finding]:
        findings_path = artifact_directory / "findings.json"
        if not findings_path.exists():
            return []
        try:
            payload = json.loads(findings_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("findings.json must contain a JSON list")
            return [Finding.model_validate(finding) for finding in payload]
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise DockerSandboxError(f"verification plugin produced invalid findings: {error}") from error
