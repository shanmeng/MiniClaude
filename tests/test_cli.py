"""Smoke tests for the CLI skeleton."""

import pytest

from miniclaude import __version__
from miniclaude.cli import main


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_args_prints_help_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: miniclaude" in capsys.readouterr().out
