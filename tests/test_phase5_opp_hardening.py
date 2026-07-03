"""Tests for Phase 5 OPP hardening (P5-T1, P5-T2, P5-T3).

- P5-T1: CLI help text should be in English (no Chinese characters)
- P5-T2: Health server must have an atexit shutdown hook
- P5-T3: Rate limiter should use per-tool buckets; ping exempt
"""
from __future__ import annotations

import re
from pathlib import Path


def test_p5_t1_cli_help_is_in_english():
    """P5-T1: --max-file-size and --log-format help text should not contain Chinese."""
    p = Path(__file__).resolve().parent.parent / "src" / "opp" / "cli.py"
    content = p.read_text(encoding="utf-8")
    # Chinese characters are in the range U+4E00 to U+9FFF
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", content)
    assert len(chinese_chars) == 0, (
        f"cli.py contains {len(chinese_chars)} Chinese characters. "
        f"Help text should be in English. Found: {''.join(chinese_chars[:30])}"
    )


def test_p5_t2_health_server_has_shutdown_hook():
    """P5-T2: Health server must have an atexit import and registration."""
    p = Path(__file__).resolve().parent.parent / "src" / "opp" / "mcp" / "health.py"
    content = p.read_text(encoding="utf-8")
    assert "import atexit" in content, (
        "health.py does not import atexit. "
        "Health server has no shutdown hook for clean exit."
    )
    assert "atexit.register" in content, (
        "health.py does not register an atexit hook for clean shutdown."
    )


def test_p5_t3_ping_exempt_from_rate_limit():
    """P5-T3: ping tool should be exempt from rate limiting."""
    from importlib import reload
    from unittest.mock import patch

    with patch.dict(
        "os.environ",
        {"OMNI_RATE_LIMIT_RPM": "1", "OMNI_RATE_LIMIT_BURST": "1"},
        clear=False,
    ):
        from opp.mcp import rate_limiter
        reload(rate_limiter)

        # First call consumes the single token
        ok1, _ = rate_limiter.check_rate_limit(tool_name="ping")
        assert ok1, "First ping call should succeed"

        # Second call — if ping is exempt, still ok; otherwise would be rate-limited
        ok2, _ = rate_limiter.check_rate_limit(tool_name="ping")
        assert ok2, "ping should be exempt from rate limiting (second call failed)"

        # Third for good measure
        ok3, _ = rate_limiter.check_rate_limit(tool_name="ping")
        assert ok3, "ping should be exempt from rate limiting (third call failed)"


def test_p5_t3_per_tool_buckets():
    """P5-T3: Different tools should have independent rate limit buckets."""
    from importlib import reload
    from unittest.mock import patch

    with patch.dict(
        "os.environ",
        {"OMNI_RATE_LIMIT_RPM": "60", "OMNI_RATE_LIMIT_BURST": "2"},
        clear=False,
    ):
        from opp.mcp import rate_limiter
        reload(rate_limiter)

        # Exhaust tool_A's bucket
        ok1, _ = rate_limiter.check_rate_limit(tool_name="tool_a")
        ok2, _ = rate_limiter.check_rate_limit(tool_name="tool_a")
        assert ok1 and ok2, "tool_a should get 2 tokens (burst=2)"
        ok3, _ = rate_limiter.check_rate_limit(tool_name="tool_a")
        assert not ok3, "tool_a should be rate-limited after burst"

        # tool_B should still have its own independent bucket
        ok4, _ = rate_limiter.check_rate_limit(tool_name="tool_b")
        assert ok4, (
            "tool_b should NOT be rate-limited by tool_a's exhaustion. "
            "Per-tool buckets are not implemented."
        )


def test_p5_t3_backward_compat_no_tool_name():
    """P5-T3: check_rate_limit() with no args should still work (backward compat)."""
    from opp.mcp.rate_limiter import check_rate_limit

    # Calling with no tool_name should not raise
    ok, err = check_rate_limit()
    assert isinstance(ok, bool)
    assert err is None or isinstance(err, str)
