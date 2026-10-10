"""Resolve requested capabilities into reproducible plugin runs."""

from __future__ import annotations

from antislop.models import ExecutionPolicy, PluginRun, PluginState, SubmissionCreate, VerificationPlan
from antislop.plugins.registry import PluginRegistry
from antislop.services.assurance import planned_claim


class UnsupportedCapabilityError(ValueError):
    pass


class PluginNotReadyError(ValueError):
    pass


class VerificationPlanner:
    def __init__(self, registry: PluginRegistry, policy: ExecutionPolicy | None = None) -> None:
        self._registry = registry
        self._policy = policy or ExecutionPolicy()

    def create_plan(self, request: SubmissionCreate) -> VerificationPlan:
        runs: list[PluginRun] = []
        for language in sorted(request.languages, key=str):
            for capability in sorted(request.capabilities, key=str):
                plugin = self._registry.resolve(language, capability)
                if plugin is None:
                    raise UnsupportedCapabilityError(
                        f"no plugin supports capability '{capability}' for language '{language}'"
                    )
                if plugin.state is not PluginState.READY:
                    raise PluginNotReadyError(
                        f"capability '{capability}' is planned but has no executable plugin yet"
                    )
                runs.append(
                    PluginRun(
                        plugin_id=plugin.id,
                        plugin_version=plugin.version,
                        language=language,
                        capability=capability,
                        policy=self._policy.model_copy(deep=True),
                        claim=planned_claim(capability),
                    )
                )
        return VerificationPlan(source=request.source, runs=runs)
