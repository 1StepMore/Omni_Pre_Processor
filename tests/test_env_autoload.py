"""Tests for OPP .env auto-load (cli.py: _load_dotenv_for_opp / _load_env_for_opp)."""

import os
import pytest
from pathlib import Path
from opp.cli import _load_dotenv_for_opp


def test_empty_file(tmp_path: Path) -> None:
    """Empty .env file should not crash and set no vars."""
    env_file = tmp_path / ".env"
    env_file.write_text("")
    _load_dotenv_for_opp(env_file)
    # No crash is the pass condition


def test_comments_only(tmp_path: Path) -> None:
    """Only comment lines should be skipped."""
    env_file = tmp_path / ".env"
    env_file.write_text("# this is a comment\n# another one")
    _load_dotenv_for_opp(env_file)
    # No crash


def test_simple_key_value(tmp_path: Path, monkeypatch) -> None:
    """Simple KEY=value sets the env var."""
    env_file = tmp_path / ".env"
    env_file.write_text("MY_KEY=my_value")
    monkeypatch.delenv("MY_KEY", raising=False)
    _load_dotenv_for_opp(env_file)
    assert os.environ.get("MY_KEY") == "my_value"


def test_quoted_value(tmp_path: Path, monkeypatch) -> None:
    """Double-quoted values should be stripped of quotes."""
    env_file = tmp_path / ".env"
    env_file.write_text('KEY="val with spaces"')
    monkeypatch.delenv("KEY", raising=False)
    _load_dotenv_for_opp(env_file)
    assert os.environ.get("KEY") == "val with spaces"


def test_single_quoted_value(tmp_path: Path, monkeypatch) -> None:
    """Single-quoted values should be stripped of quotes."""
    env_file = tmp_path / ".env"
    env_file.write_text("KEY='single quoted'")
    monkeypatch.delenv("KEY", raising=False)
    _load_dotenv_for_opp(env_file)
    assert os.environ.get("KEY") == "single quoted"


def test_missing_equals(tmp_path: Path) -> None:
    """Line without '=' should be skipped without crash."""
    env_file = tmp_path / ".env"
    env_file.write_text("NOEQUALS")
    _load_dotenv_for_opp(env_file)


def test_blank_lines(tmp_path: Path, monkeypatch) -> None:
    """Blank lines should be skipped, but valid lines parsed."""
    env_file = tmp_path / ".env"
    env_file.write_text("\n\nKEY=val\n\n")
    monkeypatch.delenv("KEY", raising=False)
    _load_dotenv_for_opp(env_file)
    assert os.environ.get("KEY") == "val"


def test_missing_value(tmp_path: Path) -> None:
    """KEY= (empty value) should be skipped."""
    env_file = tmp_path / ".env"
    env_file.write_text("EMPTY=\nKEY=val")
    _load_dotenv_for_opp(env_file)
    # EMPTY should not be set, but it should not crash


def test_no_key(tmp_path: Path) -> None:
    """=value (no key) should be skipped."""
    env_file = tmp_path / ".env"
    env_file.write_text("=orphan_value\nKEY=val")
    _load_dotenv_for_opp(env_file)
    # No crash


def test_export_prefix(tmp_path: Path, monkeypatch) -> None:
    """'export KEY=val' should set KEY, not 'export KEY'."""
    env_file = tmp_path / ".env"
    env_file.write_text("export MY_EXPORT_KEY=exported_value\nNORMAL_KEY=normal")
    monkeypatch.delenv("MY_EXPORT_KEY", raising=False)
    monkeypatch.delenv("NORMAL_KEY", raising=False)
    _load_dotenv_for_opp(env_file)
    assert os.environ.get("MY_EXPORT_KEY") == "exported_value", (
        f"Got: {os.environ.get('MY_EXPORT_KEY')}"
    )
    assert os.environ.get("NORMAL_KEY") == "normal"


def test_unicode(tmp_path: Path, monkeypatch) -> None:
    """Unicode characters in values should be preserved."""
    env_file = tmp_path / ".env"
    env_file.write_text("CAFE=café")
    monkeypatch.delenv("CAFE", raising=False)
    _load_dotenv_for_opp(env_file)
    assert os.environ.get("CAFE") == "café"


def test_permission_denied(tmp_path: Path) -> None:
    """Unreadable .env should log a warning, not crash."""
    env_file = tmp_path / ".env"
    env_file.write_text("KEY=val")
    env_file.chmod(0o000)
    try:
        _load_dotenv_for_opp(env_file)
    finally:
        env_file.chmod(0o644)


def test_setdefault_precedence(tmp_path: Path, monkeypatch) -> None:
    """Existing env vars should NOT be overwritten by .env."""
    monkeypatch.setenv("EXISTING_KEY", "existing_value")
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING_KEY=should_not_override")
    _load_dotenv_for_opp(env_file)
    assert os.environ.get("EXISTING_KEY") == "existing_value"


def test_multiple_entries(tmp_path: Path, monkeypatch) -> None:
    """Multiple env vars should all be set correctly."""
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\nB=2\nC=3")
    for k in ("A", "B", "C"):
        monkeypatch.delenv(k, raising=False)
    _load_dotenv_for_opp(env_file)
    assert os.environ["A"] == "1"
    assert os.environ["B"] == "2"
    assert os.environ["C"] == "3"
