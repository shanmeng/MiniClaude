"""Command-line entry point for MiniClaude."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from miniclaude import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(prog="miniclaude", description=__doc__)
    parser.add_argument("--version", action="version", version=f"miniclaude {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the requested command; returns a process exit code."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
