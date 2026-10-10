"""Content-addressed evidence attestations for completed verification runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from antislop.models import EvidenceAttestation, PluginRun, RunEvidence, SourceSnapshot, SubmissionCreate


def _json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def attest(source: SourceSnapshot, request: SubmissionCreate, run: PluginRun, evidence: RunEvidence) -> EvidenceAttestation:
    """Bind evidence to immutable inputs and every file emitted by the plugin run."""
    artifacts: dict[str, str] = {}
    if evidence.log_path:
        root = Path(evidence.log_path).parent
        if root.exists():
            artifacts = {
                path.relative_to(root).as_posix(): _file_hash(path)
                for path in sorted(root.rglob("*"))
                if path.is_file()
            }
    verification_config = {
        "languages": sorted(str(language) for language in request.languages),
        "capabilities": sorted(str(capability) for capability in request.capabilities),
        "paths_in_scope": request.paths_in_scope,
        "build_commands": request.build_commands,
        "test_commands": request.test_commands,
        "formal": request.formal.model_dump(mode="json") if request.formal else None,
    }
    facts = {
        "schema_version": "v1",
        "source_commit_sha": source.commit_sha,
        "plugin_id": run.plugin_id,
        "plugin_version": run.plugin_version,
        "command_sha256": _json_hash(evidence.command),
        "policy_sha256": _json_hash(run.policy.model_dump(mode="json")),
        "verification_config_sha256": _json_hash(verification_config),
        "findings_sha256": _json_hash([item.model_dump(mode="json") for item in evidence.findings]),
        "artifact_sha256": artifacts,
        "runner_image": evidence.runner_image,
        "runner_image_id": evidence.runner_image_id,
    }
    return EvidenceAttestation(**facts, integrity_sha256=_json_hash(facts))
