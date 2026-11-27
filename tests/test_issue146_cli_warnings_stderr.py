"""Regression tests for issue #146: CLI must surface degradation warnings.

Extractors record degradations (e.g. a missing optional dependency
downgrading HTML→Markdown to raw passthrough) in
``ExtractionResult.warnings`` and the manifest JSON, but the CLI used to
exit 0 with empty stdout/stderr, so the user only discovered the bad
output by opening the file. The warnings now go to stderr (never stdout —
scripts parse stdout for output paths), the exit code is unchanged
(degradation is not an error), and a no-warning run stays silent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from opp.cli import main


def _html(tmp_path: Path) -> Path:
    f = tmp_path / "sample.html"
    f.write_text(
        "<!DOCTYPE html><html><body><h1>Test</h1>"
        "<p>Hello, world.</p></body></html>",
        encoding="utf-8",
    )
    return f


class TestWarningsOnStderr:
    def test_degraded_run_warns_on_stderr(self, tmp_path: Path, monkeypatch, capsys):
        monkeypatch.setattr("opp.extractors.html.MARKDOWNIFY_AVAILABLE", False)
        out_dir = tmp_path / "out"

        rc = main([
            "--target-format", "md",
            "--output-dir", str(out_dir),
            str(_html(tmp_path)),
        ])
        captured = capsys.readouterr()

        assert rc == 0, "degradation is a warning, not an error"
        assert captured.out == "", "stdout must stay parseable for output paths"
        assert "WARNING: markdownify不可用" in captured.err
        manifest_hint = [l for l in captured.err.splitlines() if "Full degradation record" in l]
        assert manifest_hint, captured.err
        assert str(out_dir / "sample_manifest.json") in manifest_hint[0]

    def test_healthy_run_stays_silent(self, tmp_path: Path, capsys):
        # A plain DOCX produces no degradation warnings, so the CLI must
        # stay as quiet as before #146 (stderr empty, stdout empty).
        from docx import Document

        docx_path = tmp_path / "plain.docx"
        doc = Document()
        doc.add_paragraph("hello world")
        doc.save(str(docx_path))

        rc = main([
            "--target-format", "md",
            "--output-dir", str(tmp_path / "out"),
            str(docx_path),
        ])
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.out == ""
        assert captured.err == ""

    def test_json_mode_still_carries_warnings(self, tmp_path: Path, monkeypatch, capsys):
        monkeypatch.setattr("opp.extractors.html.MARKDOWNIFY_AVAILABLE", False)

        rc = main([
            "--target-format", "md",
            "--output-dir", str(tmp_path / "out"),
            "--json",
            str(_html(tmp_path)),
        ])
        captured = capsys.readouterr()

        assert rc == 0
        assert '"warnings"' in captured.out
        assert "WARNING: markdownify不可用" in captured.err


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
