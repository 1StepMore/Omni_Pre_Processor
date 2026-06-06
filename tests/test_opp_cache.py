"""A6 cache tests for OPP CLI.

Tests the OPP CLI's content-addressed cache at ~/.omni_cache/opp/<sha256>.xlf.
The cache root is overridden in tests via OMNI_CACHE_DIR env var (set by
``fake_cache_dir`` fixture) so tests do not touch the real user cache.

TDD discipline: these tests are written FIRST (before the production code).
They exercise the cache plumbing without depending on the OPPPipeline's
real extraction logic (we mock ``process_single_file`` to a deterministic
counter so we can assert "cache hit means no pipeline work").
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import opp.cli as opp_cli


@pytest.fixture
def fake_cache_dir(tmp_path, monkeypatch):
    """Override OMNI_CACHE_DIR to a tmp path for testing.

    The production cache helpers must read this env var at import-time or
    at call-time; the fixture sets it before each test so the OPP module
    resolves the cache root to ``tmp_path / "omni_cache"``.
    """
    cache_root = tmp_path / "omni_cache"
    monkeypatch.setenv("OMNI_CACHE_DIR", str(cache_root))
    yield cache_root


@pytest.fixture
def sample_input(tmp_path):
    """Create a minimal input file for OPP."""
    f = tmp_path / "input.txt"
    f.write_text("hello world", encoding="utf-8")
    return f


def _make_fake_process_single_file(call_counter, xlf_content="xlf output v1"):
    """Returns a fake ``process_single_file`` that writes a known xlf and counts calls.

    Real ``process_single_file`` is expensive (it instantiates a full OPP
    pipeline and runs DOCX/PPTX/PDF extraction). For cache tests we only
    care that the OPP CLI calls the pipeline on a cache miss and does NOT
    call it on a cache hit. This fake gives us that signal without
    invoking real extractors.
    """
    def fake_process_single_file(file_path, args, pipeline, stats, error_handler):
        call_counter["n"] += 1
        output_dir = args.output_dir if args.output_dir else file_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{file_path.stem}.xlf").write_text(xlf_content, encoding="utf-8")
        return True
    return fake_process_single_file


def _run_opp(input_path, output_dir, extra_args=None):
    """Run ``opp.cli.main`` with the given args. Returns the exit code."""
    args = [
        "--target-format=xlf", "--source-lang=en", "--target-lang=zh",
        "--output-dir", str(output_dir),
    ]
    if extra_args:
        args.extend(extra_args)
    args.append(str(input_path))
    return opp_cli.main(args)


def test_opp_cache_hit_returns_cached_output(fake_cache_dir, sample_input, tmp_path):
    """Run OPP twice on same input; second run is a cache hit (process_single_file not called)."""
    counter = {"n": 0}
    fake_psf = _make_fake_process_single_file(counter, "xlf content v1")

    # First run: cache miss → process_single_file is called
    out1 = tmp_path / "out1"
    with patch("opp.cli.process_single_file", side_effect=fake_psf), \
         patch("opp.cli.OPPPipeline"):
        rc1 = _run_opp(sample_input, out1)
    assert rc1 == 0, f"first run failed (rc={rc1})"
    assert counter["n"] == 1
    xlf1 = out1 / f"{sample_input.stem}.xlf"
    assert xlf1.exists()
    assert xlf1.read_text() == "xlf content v1"

    # Second run: cache hit → process_single_file MUST NOT be called again
    counter["n"] = 0
    out2 = tmp_path / "out2"
    with patch("opp.cli.process_single_file", side_effect=fake_psf), \
         patch("opp.cli.OPPPipeline"):
        rc2 = _run_opp(sample_input, out2)
    assert rc2 == 0, f"second run failed (rc={rc2})"
    assert counter["n"] == 0, "cache hit expected: process_single_file should not be called"
    xlf2 = out2 / f"{sample_input.stem}.xlf"
    assert xlf2.exists()
    # Identical output across runs
    assert xlf2.read_text() == xlf1.read_text()


def test_opp_cache_miss_on_input_change(fake_cache_dir, tmp_path):
    """Modify input; assert cache miss (process_single_file called twice)."""
    counter = {"n": 0}
    fake_psf = _make_fake_process_single_file(counter, "xlf v1")

    # First run with input1
    input1 = tmp_path / "in1.txt"
    input1.write_text("original content", encoding="utf-8")
    out1 = tmp_path / "out1"
    with patch("opp.cli.process_single_file", side_effect=fake_psf), \
         patch("opp.cli.OPPPipeline"):
        _run_opp(input1, out1)
    assert counter["n"] == 1

    # Second run with a different input (same args, different bytes)
    input2 = tmp_path / "in2.txt"
    input2.write_text("MODIFIED content", encoding="utf-8")
    out2 = tmp_path / "out2"
    with patch("opp.cli.process_single_file", side_effect=fake_psf), \
         patch("opp.cli.OPPPipeline"):
        _run_opp(input2, out2)
    assert counter["n"] == 2, "cache miss expected on input change"


def test_opp_cache_invalidation_on_config_change(fake_cache_dir, sample_input, tmp_path):
    """Change config; assert cache miss (process_single_file called twice)."""
    counter = {"n": 0}
    fake_psf = _make_fake_process_single_file(counter, "xlf v1")

    # First run with config1
    config1 = tmp_path / "config1.yaml"
    config1.write_text("model: foo\n", encoding="utf-8")
    out1 = tmp_path / "out1"
    with patch("opp.cli.process_single_file", side_effect=fake_psf), \
         patch("opp.cli.OPPPipeline"):
        _run_opp(sample_input, out1, extra_args=["--config", str(config1)])
    assert counter["n"] == 1

    # Second run with config2 (different content → different cache key)
    config2 = tmp_path / "config2.yaml"
    config2.write_text("model: bar\n", encoding="utf-8")
    out2 = tmp_path / "out2"
    with patch("opp.cli.process_single_file", side_effect=fake_psf), \
         patch("opp.cli.OPPPipeline"):
        _run_opp(sample_input, out2, extra_args=["--config", str(config2)])
    assert counter["n"] == 2, "cache miss expected on config change"


def test_opp_cache_directory_created_with_correct_permissions(fake_cache_dir, sample_input, tmp_path):
    """Cache dir exists and is mode 0o700 (protects any sensitive cached content)."""
    counter = {"n": 0}
    fake_psf = _make_fake_process_single_file(counter, "xlf v1")
    out1 = tmp_path / "out1"
    with patch("opp.cli.process_single_file", side_effect=fake_psf), \
         patch("opp.cli.OPPPipeline"):
        _run_opp(sample_input, out1)

    cache_root = Path(os.environ["OMNI_CACHE_DIR"])
    opp_cache = cache_root / "opp"
    assert opp_cache.exists(), f"expected cache dir at {opp_cache}"
    assert opp_cache.is_dir()
    mode = opp_cache.stat().st_mode & 0o777
    assert mode == 0o700, f"expected mode 0o700, got {oct(mode)}"
