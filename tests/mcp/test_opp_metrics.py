"""Phase 4.5 — OPP per-module Prometheus metrics.

Verifies that:
- ``opp.mcp.metrics`` exposes the required counters and histogram with
  the correct names and label sets.
- ``record_request`` and ``record_extraction`` increment the
  corresponding metrics.
- The Prometheus textfile is written to ``OMNI_METRICS_DIR`` (default
  ``/tmp/omni-metrics/opp.prom``) with valid text format.
- The call_tool dispatcher records success/error/rate_limited/
  auth_failed/unknown_tool status correctly.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


OPP_SRC = Path(__file__).resolve().parents[2] / "src"
OPP_PKG = OPP_SRC / "opp"


def _load(name: str, path: Path, register: bool = False):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if register:
        sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def metrics_dir(tmp_path, monkeypatch):
    out = tmp_path / "omni-metrics"
    monkeypatch.setenv("OMNI_METRICS_DIR", str(out))
    return out


@pytest.fixture
def metrics(metrics_dir):
    return _load("opp_metrics_under_test", OPP_SRC / "opp" / "mcp" / "metrics.py")


class TestMetricRegistration:
    def test_opp_requests_total_emitted_name(self, metrics, metrics_dir):
        metrics.record_request("t", metrics.STATUS_SUCCESS, 0.001)
        body = (metrics_dir / "opp.prom").read_text(encoding="utf-8")
        assert "opp_requests_total" in body
        assert "# TYPE opp_requests_total counter" in body

    def test_opp_request_duration_seconds_buckets(self, metrics):
        assert tuple(metrics.OPP_REQUEST_DURATION_SECONDS._upper_bounds)[:-1] == (
            0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
        )

    def test_label_sets(self, metrics):
        assert sorted(metrics.OPP_REQUESTS_TOTAL._labelnames) == ["status", "tool_name"]
        assert sorted(metrics.OPP_EXTRACTIONS_TOTAL._labelnames) == ["format", "status"]
        assert sorted(metrics.OPP_REQUEST_DURATION_SECONDS._labelnames) == ["tool_name"]


class TestStatusConstants:
    @pytest.mark.parametrize(
        "label",
        ["success", "error", "rate_limited", "auth_failed"],
    )
    def test_status_constant_present(self, metrics, label):
        assert label in {
            metrics.STATUS_SUCCESS,
            metrics.STATUS_ERROR,
            metrics.STATUS_RATE_LIMITED,
            metrics.STATUS_AUTH_FAILED,
        }


class TestRecordRequest:
    def test_increments_counter_and_observes_histogram(self, metrics):
        before = metrics.OPP_REQUESTS_TOTAL.labels(
            tool_name="extract_document", status="success",
        )._value.get()
        metrics.record_request("extract_document", metrics.STATUS_SUCCESS, 0.123)
        after = metrics.OPP_REQUESTS_TOTAL.labels(
            tool_name="extract_document", status="success",
        )._value.get()
        assert after == before + 1
        total = metrics.OPP_REQUEST_DURATION_SECONDS.labels(
            tool_name="extract_document",
        )._sum.get()
        assert total > 0

    def test_writes_prom_textfile(self, metrics, metrics_dir):
        metrics.record_request("extract_document", metrics.STATUS_SUCCESS, 0.01)
        out = metrics_dir / "opp.prom"
        assert out.exists()
        body = out.read_text(encoding="utf-8")
        assert "# TYPE opp_requests_total counter" in body
        assert "# TYPE opp_request_duration_seconds histogram" in body
        assert 'tool_name="extract_document"' in body


class TestRecordExtraction:
    def test_classify_format_from_path(self, metrics):
        assert metrics.classify_format_from_path("/x/y.docx") == "docx"
        assert metrics.classify_format_from_path("/x/y.pdf") == "pdf"
        assert metrics.classify_format_from_path("/x/y.json") == "json"
        assert metrics.classify_format_from_path("/x/y.unknown") == "unknown"
        assert metrics.classify_format_from_path(None) == "unknown"
        assert metrics.classify_format_from_path("") == "unknown"

    def test_record_extraction_increments(self, metrics):
        before = metrics.OPP_EXTRACTIONS_TOTAL.labels(
            format="docx", status="success",
        )._value.get()
        metrics.record_extraction("docx", metrics.STATUS_SUCCESS)
        after = metrics.OPP_EXTRACTIONS_TOTAL.labels(
            format="docx", status="success",
        )._value.get()
        assert after == before + 1


class TestDispatcherWiring:
    """Verify the call_tool dispatcher emits metrics for the four
    status values (success, error, rate_limited, auth_failed,
    unknown_tool)."""

    @pytest.fixture
    def server(self, metrics, metrics_dir):
        _register_shared_metrics_module(metrics)
        return _load(
            "opp_server_under_test", OPP_SRC / "opp" / "mcp" / "server.py",
        )


def _register_shared_metrics_module(metrics) -> None:
    import types
    pkg = types.ModuleType("opp")
    pkg.__path__ = [str(OPP_PKG)]
    sys.modules["opp"] = pkg
    sys.modules["opp.mcp"] = types.ModuleType("opp.mcp")
    sys.modules["opp.mcp"].__path__ = [str(OPP_PKG / "mcp")]
    sys.modules["opp.mcp.metrics"] = metrics

    @pytest.mark.asyncio
    async def test_dispatcher_unknown_tool_records_error(self, server, metrics):
        result = await server._handle_call_tool("nope_does_not_exist", {})
        assert isinstance(result, list)
        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert parsed["error_code"] == "OPP_UNKNOWN_TOOL"
        val = metrics.OPP_REQUESTS_TOTAL.labels(
            tool_name="nope_does_not_exist", status="error",
        )._value.get()
        assert val >= 1

    @pytest.mark.asyncio
    async def test_dispatcher_internal_error_records_error(self, server, metrics):
        async def boom(**_):
            raise RuntimeError("kaboom")
        server._TOOL_DISPATCH["boom_tool"] = boom
        try:
            result = await server._handle_call_tool("boom_tool", {})
            parsed = json.loads(result[0].text)
            assert parsed["success"] is False
            assert parsed["error_code"] == "OPP_INTERNAL_ERROR"
            val = metrics.OPP_REQUESTS_TOTAL.labels(
                tool_name="boom_tool", status="error",
            )._value.get()
            assert val >= 1
        finally:
            server._TOOL_DISPATCH.pop("boom_tool", None)
