"""The initial capability catalog. Plugins are descriptors until workers are added."""

from antislop.models import Capability, Language, PluginManifest
from antislop.models import PluginState
from antislop.plugins.registry import PluginRegistry


ALL_LANGUAGES = {Language.PYTHON, Language.JAVASCRIPT}


def built_in_registry() -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(
        PluginManifest(
            id="builtin.syntax",
            version="0.1.0",
            languages=ALL_LANGUAGES,
            capabilities={Capability.SYNTAX},
            state=PluginState.READY,
        )
    )
    registry.register(
        PluginManifest(
            id="builtin.tests",
            version="0.1.0",
            languages=ALL_LANGUAGES,
            capabilities={Capability.TESTS},
            state=PluginState.READY,
        )
    )
    registry.register(
        PluginManifest(
            id="builtin.static-analysis",
            version="0.1.0",
            languages=ALL_LANGUAGES,
            capabilities={Capability.STATIC_ANALYSIS},
            state=PluginState.READY,
        )
    )
    registry.register(
        PluginManifest(
            id="builtin.ast-cfg",
            version="0.1.0",
            languages=ALL_LANGUAGES,
            capabilities={Capability.AST_CFG},
            state=PluginState.READY,
        )
    )
    registry.register(
        PluginManifest(
            id="builtin.formal",
            version="0.1.0",
            languages=ALL_LANGUAGES,
            capabilities={
                Capability.FORMAL_TYPE_SAFETY,
                Capability.FORMAL_BOUNDED,
                Capability.FORMAL_CONTRACTS,
            },
            state=PluginState.READY,
            config_schema={
                "formal.contract_path": "repository-relative JSON contract file",
                "formal.max_cases": "maximum generated or explicit cases to execute",
            },
        )
    )
    registry.register(
        PluginManifest(
            id="builtin.agent-review",
            version="0.1.0",
            languages=ALL_LANGUAGES,
            capabilities={Capability.AGENT_REVIEW},
            state=PluginState.READY,
            config_schema={
                "provider": "configured trusted agent-review provider",
            },
        )
    )
    return registry
