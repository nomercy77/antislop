"""The initial capability catalog. Plugins are descriptors until workers are added."""

from antislop.models import Capability, Language, PluginManifest
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
        )
    )
    registry.register(
        PluginManifest(
            id="builtin.tests",
            version="0.1.0",
            languages=ALL_LANGUAGES,
            capabilities={Capability.TESTS},
        )
    )
    registry.register(
        PluginManifest(
            id="builtin.static-analysis",
            version="0.1.0",
            languages=ALL_LANGUAGES,
            capabilities={Capability.STATIC_ANALYSIS},
        )
    )
    registry.register(
        PluginManifest(
            id="builtin.ast-cfg",
            version="0.1.0",
            languages=ALL_LANGUAGES,
            capabilities={Capability.AST_CFG},
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
            config_schema={
                "bounds": "required for formal.bounded; recorded with all formal runs",
                "assumptions": "optional list of explicit assumptions",
            },
        )
    )
    registry.register(
        PluginManifest(
            id="builtin.agent-review",
            version="0.1.0",
            languages=ALL_LANGUAGES,
            capabilities={Capability.AGENT_REVIEW},
        )
    )
    return registry
