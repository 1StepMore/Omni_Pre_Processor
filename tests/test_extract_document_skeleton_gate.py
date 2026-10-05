"""Regression: the MCP extract_document skeleton gate must not test
`.skeleton` alone.

`OPPPipeline.save_skeleton` decides per format which field holds the skeleton:
DOCX/PPTX/EPUB/XLSX use `.skeleton` (bytes), HTML uses `.skeleton_html` (str)
and gets packaged into a zip. The MCP tool used to gate on `.skeleton` only, so
for HTML the branch never ran and no `skeleton_path` was returned.

That made the XLIFF channel work on the CLI path while failing on the MCP path
for the same input — `html -> html` passed via CLI and failed via MCP with
"OPP MCP: 未返回 skeleton_path". The gate must therefore defer to
save_skeleton instead of re-deciding which field matters.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from opp.utils.dataclasses import ExtractionResult, ParagraphData


def _tool_module():
    """Import the tool MODULE, not the function re-exported by its package.

    `opp.mcp.tools` re-exports `extract_document` as a function, which shadows
    the submodule of the same name, so a plain `import ... as` yields the
    function and `.extract_document` on it raises AttributeError.
    """
    import importlib

    return importlib.import_module("opp.mcp.tools.extract_document")


class _StubPipeline:
    """Feeds a canned ProcessingResult and records save_skeleton calls.

    `extract_document` reaches the skeleton branch only after
    `_pipeline.process_file()` returns, so the stub has to stand in for the whole
    extraction, not just save_skeleton.
    """

    def __init__(self, extraction_result, skeleton_path: Path | None):
        self._extraction_result = extraction_result
        self._skeleton_path = skeleton_path
        self.calls: list[ExtractionResult] = []

    def process_file(self, path: Path):
        return SimpleNamespace(
            extraction_result=self._extraction_result,
            format_type=SimpleNamespace(value=self._extraction_result.metadata.format_type),
            warnings=[],
        )

    def save_skeleton(self, extraction_result, stem, out_dir):
        self.calls.append(extraction_result)
        return self._skeleton_path


class _StubSerializer:
    def serialize(self, result, include_base64=False, resource_dir=None):
        return {"success": True, "format_type": "html"}


def _ctx(pipeline, allowed_dirs=None):
    """Minimal stand-in for `opp.mcp.common`, exposing every attribute the
    tool touches: _config, _pipeline, _validator, _serializer,
    _suggest_pipeline, _safe_temp_output, _safe_unlink, _tempfiles."""
    import contextlib

    return SimpleNamespace(
        _config=SimpleNamespace(output_dir=None, allowed_directories=allowed_dirs or []),
        _pipeline=pipeline,
        _validator=SimpleNamespace(
            validate_path=lambda _p: SimpleNamespace(success=True, error=None)
        ),
        _serializer=_StubSerializer(),
        _suggest_pipeline=lambda *_: "md_only",
        _safe_temp_output=lambda *_a, **_k: contextlib.nullcontext(),
        _safe_unlink=lambda _p: None,
        _tempfiles=[],
    )


def _result_with_only_skeleton_html() -> ExtractionResult:
    """An HTML-shaped result: no `.skeleton`, but `.skeleton_html` present."""
    return ExtractionResult(
        paragraphs=[ParagraphData(text="Hello, world.", level=0, style=None)],
        tables=[],
        images=[],
        metadata=SimpleNamespace(format_type="html"),
        skeleton=None,
        skeleton_html="<html><body><p>Hello, world.</p></body></html>",
    )


@pytest.fixture
def skeleton_saved(tmp_path, monkeypatch):
    """Patch the MCP tool's context so save_skeleton is observable."""
    saved = tmp_path / "doc.skeleton.zip"

    class _Config:
        output_dir = str(tmp_path)

    tool_mod = _tool_module()

    pipeline = _StubPipeline(_result_with_only_skeleton_html(), saved)
    monkeypatch.setattr(tool_mod, "_c", _ctx(pipeline), raising=False)
    return pipeline, saved, tool_mod


def test_gate_admits_skeleton_only_html(skeleton_saved, tmp_path):
    """The regression: `.skeleton` is None but `.skeleton_html` is set."""
    pipeline, saved, tool_mod = skeleton_saved
    src = tmp_path / "page.html"
    src.write_text("<html><body><p>Hello, world.</p></body></html>")

    response = asyncio.run(tool_mod.extract_document(str(src)))

    assert pipeline.calls, "save_skeleton was never reached for an HTML result"
    # The tool wraps its payload: response["content"]["skeleton_path"].
    assert response["content"].get("skeleton_path") == str(saved)


def test_gate_still_admits_plain_skeleton(tmp_path, monkeypatch):
    """DOCX/PPTX/EPUB/XLSX results must keep working — no regression."""
    tool_mod = _tool_module()

    saved = tmp_path / "doc.skeleton.zip"
    res = _result_with_only_skeleton_html()
    res.skeleton = b"PK\x03\x04fake"
    pipeline = _StubPipeline(res, saved)
    monkeypatch.setattr(tool_mod, "_c", _ctx(pipeline), raising=False)

    src = tmp_path / "doc.docx"
    src.write_bytes(b"PK\x03\x04")

    response = asyncio.run(tool_mod.extract_document(str(src)))

    assert pipeline.calls, "save_skeleton was not reached for a bytes skeleton"
    assert response["content"].get("skeleton_path") == str(saved)
