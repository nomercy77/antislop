"""Versioned verification-plugin registry."""

from __future__ import annotations

from antislop.models import Capability, Language, PluginManifest


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, PluginManifest] = {}

    def register(self, manifest: PluginManifest) -> None:
        if manifest.id in self._plugins:
            raise ValueError(f"plugin already registered: {manifest.id}")
        self._plugins[manifest.id] = manifest

    def list(self) -> list[PluginManifest]:
        return sorted(self._plugins.values(), key=lambda plugin: plugin.id)

    def resolve(self, language: Language, capability: Capability) -> PluginManifest | None:
        matches = [
            plugin
            for plugin in self._plugins.values()
            if language in plugin.languages and capability in plugin.capabilities
        ]
        return sorted(matches, key=lambda plugin: plugin.id)[0] if matches else None
