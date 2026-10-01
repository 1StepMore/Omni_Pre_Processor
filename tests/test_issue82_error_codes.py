"""Issue #82 — MCP error codes and the CLI catch-all must not leak or misclassify.

Two defects fixed here:

- Defect 1: the CLI ``__main__`` catch-all handed ``str(exc)`` — raw
  exception text (internal paths, implementation detail) — to the caller
  as the ``--json`` error ``message``. It must keep logging the full
  traceback server-side and return only a fixed, generic message with the
  stable ``OPP_INTERNAL_ERROR`` code and exit code 1.
- Defect 2: five MCP tools raised ``OPP_INTERNAL_ERROR`` for an
  uninitialized server context. A missing/uninitialized server config is
  a CONFIG problem, not an internal error: an agent uses the error code
  as its only signal for what to do next (configure vs fix input vs give
  up). Those guards now emit ``OPP_NOT_INITIALIZED`` with a static, safe
  message.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from opp.mcp import common as _c
from opp.mcp import rate_limiter as _rate_limiter

_PATH_LIKE = re.compile(r"(?:[A-Za-z]:\\|\\\\|/(?:home|tmp|usr|var|etc|opt|mnt|Users)/)")

GENERIC_MESSAGE = "Internal error; see server logs for details."
SAFE_TOOL_MESSAGE = (
    "MCP server is not initialized; call the initialize/config path first"
)

# The five issue-#82 files expose six tool functions (generate.py holds two).
# (tool module, tool function, minimal valid kwargs reaching the guard)
_UNINITIALIZED_CASES = [
    ("opp.mcp.tools.extract_document", "extract_document", {"file_path": "x.docx"}),
    ("opp.mcp.tools.batch_extract", "batch_extract", {"file_paths": ["x.docx"]}),
    ("opp.mcp.tools.detect_format", "detect_format_tool", {"file_path": "x.docx"}),
    ("opp.mcp.tools.generate", "generate_xliff", {"file_path": "x.docx"}),
    ("opp.mcp.tools.generate", "generate_markdown", {"file_path": "x.docx"}),
    ("opp.mcp.tools.save_skeleton", "save_skeleton", {"file_path": "x.docx"}),
]


@pytest.fixture
def uninitialized_server(monkeypatch):
    """Force the MCP shared state into its uninitialized state.

    Also resets the rate-limit buckets with rpm=0 (consume-always) and
    disables shared-secret auth so the ONLY guard that can fail the call
    under test is the server-initialization check.
    """
    monkeypatch.setattr(_c, "_validator", None)
    monkeypatch.setattr(_c, "_pipeline", None)
    monkeypatch.setattr(_c, "_config", None)
    monkeypatch.setattr(_rate_limiter, "_buckets", {})
    monkeypatch.setenv("OMNI_RATE_LIMIT_RPM", "0")
    monkeypatch.delenv("MCP_SHARED_SECRET", raising=False)


# ── Defect 2: uninitialized server → OPP_NOT_INITIALIZED ─────────────


@pytest.mark.parametrize(("module_path", "tool_name", "kwargs"), _UNINITIALIZED_CASES)
@pytest.mark.asyncio
async def test_uninitialized_server_reports_not_initialized(
    uninitialized_server, module_path, tool_name, kwargs
):
    """Each of the 5 tools must return the NEW code, not OPP_INTERNAL_ERROR,
    with a message free of tracebacks, filesystem paths, and exception reprs.
    """
    tool = getattr(importlib.import_module(module_path), tool_name)
    result = await tool(**kwargs)

    assert result["success"] is False
    assert result["error"]["code"] == "OPP_NOT_INITIALIZED"
    assert result["error_code"] == "OPP_NOT_INITIALIZED"

    message = result["error"]["message"]
    assert message == SAFE_TOOL_MESSAGE  # static, no traceback / path / repr
    assert "Traceback" not in message
    # Match absolute/relative filesystem paths and Windows drive paths rather
    # than any "/" — the safe message legitimately contains "initialize/config".
    assert not _PATH_LIKE.search(message), f"message leaks a path: {message!r}"
    assert "McpError" not in message and "Exception" not in message

    # Registry wiring: the recovery hint travels with the envelope.
    assert result["recovery"]["strategy"] == "configure_environment"


class TestNotInitializedRegistry:
    """Local pin of the R-09 registry contract for the new code."""

    def test_code_is_declared(self):
        from opp.mcp._errors import DECLARED_ERROR_CODES

        assert "OPP_NOT_INITIALIZED" in DECLARED_ERROR_CODES

    def test_code_has_static_recovery_hint(self):
        from opp.mcp._errors import RECOVERY_HINTS, recovery_for

        assert "OPP_NOT_INITIALIZED" in RECOVERY_HINTS
        rec = recovery_for("OPP_NOT_INITIALIZED")
        assert rec["strategy"] == "configure_environment"
        assert len(rec["hint"]) >= 15
        assert "{" not in rec["hint"] and "}" not in rec["hint"]


# ── Defect 1: CLI catch-all — real subprocess surface ────────────────


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    return subprocess.run(
        [sys.executable, "-m", "opp.cli", *args],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
    )


class TestCliCatchAllJson:
    """`python -m opp.cli` drives the real ``__main__`` guard."""

    def test_unexpected_exception_json_is_generic_and_exits_1(self, tmp_path):
        # A missing --xliff-file raises FileNotFoundError OUTSIDE any typed
        # handler in main(), so it reaches the __main__ catch-all. The path
        # acts as the sentinel: the raw exception text must not reach stdout.
        sentinel = f"MISSING_82_SENTINEL_{tmp_path.name}"
        missing = tmp_path / f"{sentinel}.xlf"

        proc = _run_cli("--validate-xliff", "--xliff-file", str(missing), "--json")

        # Exit code unchanged: 1 for an uncaught exception.
        assert proc.returncode == 1, f"stderr: {proc.stderr[-800:]}"

        # stdout is exactly one parseable JSON object.
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        assert len(lines) == 1
        payload = json.loads(lines[0])

        assert payload["success"] is False
        assert payload["error"]["code"] == "OPP_INTERNAL_ERROR"
        assert payload["error"]["message"] == GENERIC_MESSAGE

        # The sentinel (path) and raw exception text must be ABSENT.
        assert sentinel not in proc.stdout
        assert "No such file" not in proc.stdout
        assert "Traceback" not in proc.stdout

    def test_typed_invalid_args_keeps_specific_code(self, tmp_path):
        """Regression: the catch-all must not collapse typed errors.

        ``--target-format xlf`` without ``--target-lang`` is handled by
        main() itself and keeps its OPP_INVALID_ARGS code + exit 2.
        """
        docx = tmp_path / "t.docx"
        docx.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00")

        proc = _run_cli("--target-format", "xlf", str(docx), "--json")

        assert proc.returncode == 2
        payload = json.loads(proc.stdout.strip())
        assert payload["error"]["code"] == "OPP_INVALID_ARGS"

    def test_no_input_keeps_specific_code(self):
        """Regression: OPP_NO_INPUT must keep its own code + exit 1."""
        proc = _run_cli("--json")

        assert proc.returncode == 1
        payload = json.loads(proc.stdout.strip())
        assert payload["error"]["code"] == "OPP_NO_INPUT"
        assert payload["error"]["message"] == "No supported files found"


class TestCliCatchAllUnit:
    """In-process: the guard logs everything server-side, leaks nothing."""

    def test_guard_returns_1_logs_full_traceback_leaks_nothing(
        self, monkeypatch, caplog, capsys
    ):
        import opp.cli as opp_cli

        sentinel = "GUARD_SENTINEL_82_secret_internal_detail"

        def _boom():
            raise RuntimeError(sentinel)

        monkeypatch.setattr(opp_cli, "main", _boom)
        monkeypatch.setattr(sys, "argv", ["opp", "--json"])

        with caplog.at_level(logging.ERROR):
            rc = opp_cli._run_main_with_guard()

        # Exit code unchanged.
        assert rc == 1

        # Diagnostics preserved server-side: the sentinel IS in the log.
        assert "Uncaught exception in main" in caplog.text
        assert sentinel in caplog.text

        # ...but stdout carries only the fixed, generic envelope.
        out = capsys.readouterr().out
        payload = json.loads(out.strip())
        assert payload["error"]["code"] == "OPP_INTERNAL_ERROR"
        assert payload["error"]["message"] == GENERIC_MESSAGE
        assert sentinel not in out

    def test_guard_without_json_flag_prints_nothing(self, monkeypatch, capsys):
        import opp.cli as opp_cli

        monkeypatch.setattr(
            opp_cli, "main",
            lambda: (_ for _ in ()).throw(RuntimeError("no json")),
        )
        monkeypatch.setattr(sys, "argv", ["opp"])

        assert opp_cli._run_main_with_guard() == 1
        assert capsys.readouterr().out == ""
