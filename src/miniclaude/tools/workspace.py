"""Workspace-root confinement for file tools (AD7), independent of the permission policy."""

from __future__ import annotations

from pathlib import Path


class OutsideWorkspaceError(ValueError):
    """Raised when a path resolves to a location outside the workspace root."""


def resolve_in_workspace(root: Path, path: str) -> Path:
    """Resolve `path` against `root` (following symlinks) and refuse anything outside it."""
    resolved_root = root.resolve()
    # Joining an absolute path replaces the root, so absolute paths are checked the same way.
    resolved = (resolved_root / path).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise OutsideWorkspaceError(f"Path is outside the workspace root: {path}")
    return resolved
