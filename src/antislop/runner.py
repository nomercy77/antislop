"""Boundary for a future sandboxed execution service.

The API only persists queue intent. A production implementation must clone the
pinned commit and execute the run in an ephemeral sandbox outside this process.
"""

from __future__ import annotations

from typing import Protocol

from antislop.models import PluginRun, SourceSnapshot


class IsolatedRunner(Protocol):
    def enqueue(self, source: SourceSnapshot, run: PluginRun) -> None:
        """Accept a planned run without executing it in the API process."""
