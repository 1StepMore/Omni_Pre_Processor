"""OPP CLI smoke: invoke every documented command path against real fixtures.

This file spawns the OPP CLI as a real subprocess (not in-process CliRunner),
so it exercises the same code path users hit from the shell. All LLM/AI seams
are bypassed via OMNI_TEST_FAKE_LLM=1 (or are non-applicable to OPP, which
performs deterministic parsing only).

Run with:
    cd /mnt/d/贯维/Omni_Suite/Omni_Pre_Processor
    OMNI_TEST_FAKE_LLM=1 pytest tests/test_cli_smoke.py -v --tb=short

Goals:
    1. `--help` works.
    2. `--target-format md` extracts non-empty markdown from 6+ formats.
    3. `--target-format xlf` produces non-empty XLIFF (requires --target-lang).
    4. `--target-format both` produces both.
    5. `--detect-format` + `--report text` complete.
    6. `--batch` accepts multiple files.
    7. OPP writes a manifest.json + skeleton.zip alongside the .md / .xlf.

Format coverage (6+ of the 15 supported formats):
    DOCX, PPTX, HTML, CSV, EPUB, XLSX, JSON
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest


VENV_PY = "/mnt/d/贯维/Omni_Suite/.venv_ol/bin/python"
OPP_DIR = Path("/mnt/d/贯维/Omni_Suite/Omni_Pre_Processor")
REPO_ROOT = Path("/mnt/d/贯维/Omni_Suite")

HAIER_DOCX = REPO_ROOT / "爱上海尔_第二章_全球创牌 - E2E测试专用.docx"
MERIDIAN_PPTX = REPO_ROOT / "Meridian_Q1_Update_E2E.pptx"
MERIDIAN_DOCX = REPO_ROOT / "Meridian_Robotics_Product_Overview_E2E.docx"

# Subprocess env: fake-LLM seam + unbuffered IO + a writable cwd.
_BASE_ENV = {
    **os.environ,
    "OMNI_TEST_FAKE_LLM": "1",
    "PYTHONUNBUFFERED": "1",
    "PYTHONIOENCODING": "utf-8",
}


def run_opp(*args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    """Invoke `python -m opp.cli ...` in OPP_DIR with the venv interpreter."""
    cmd = [VENV_PY, "-m", "opp.cli", *args]
    return subprocess.run(
        cmd,
        cwd=str(OPP_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_BASE_ENV,
    )


@pytest.fixture(scope="module")
def synthetic_formats(tmp_path_factory) -> dict[str, Path]:
    """Build minimal HTML / CSV / EPUB / XLSX fixtures in a temp dir.

    These match what OPP's detector/extractors expect:
      - HTML: starts with `<!DOCTYPE html>` or `<html>`
      - CSV : plain text, comma-separated
      - EPUB: ZIP with `mimetype` and `META-INF/container.xml`
      - XLSX: ZIP with `[Content_Types].xml` and `xl/workbook.xml`
    """
    out = tmp_path_factory.mktemp("opp_synthetic")

    # --- HTML ---
    html = out / "sample.html"
    html.write_text(
        "<!DOCTYPE html>\n"
        "<html><head><meta charset='utf-8'><title>Test</title></head>\n"
        "<body><h1>Hello HTML</h1>"
        "<p>First paragraph about Omni Suite.</p>"
        "<p>Second paragraph with <b>bold</b> and <i>italic</i>.</p>"
        "<table><tr><th>H1</th><th>H2</th></tr>"
        "<tr><td>Cell1</td><td>Cell2</td></tr></table>"
        "</body></html>",
        encoding="utf-8",
    )

    # --- CSV ---
    csv = out / "sample.csv"
    csv.write_text(
        "name,role,note\n"
        "Alice,Engineer,First row\n"
        "Bob,Designer,Second row\n"
        "Carol,Manager,Third row\n",
        encoding="utf-8",
    )

    # --- JSON (records array) ---
    json_path = out / "sample.json"
    json_path.write_text(
        '[\n'
        '  {"title": "User Manual", "chapter": "1", "body": "Welcome to Omni Suite."},\n'
        '  {"title": "User Manual", "chapter": "2", "body": "Second chapter about parsing."}\n'
        ']\n',
        encoding="utf-8",
    )

    # --- EPUB (built with ebooklib so OPP's reader is happy) ---
    from ebooklib import epub as _ebooklib
    book = _ebooklib.EpubBook()
    book.set_identifier("urn:uuid:00000000-0000-0000-0000-000000000001")
    book.set_title("Test Book")
    book.set_language("en")
    book.add_author("Test Author")
    ch1 = _ebooklib.EpubHtml(
        title="Chapter 1", file_name="ch1.xhtml", lang="en",
    )
    ch1.content = (
        '<html><head><title>Ch1</title></head>'
        '<body><h1>Chapter One</h1>'
        '<p>First paragraph of the chapter.</p>'
        '<p>Second paragraph with <em>emphasis</em>.</p>'
        '</body></html>'
    )
    book.add_item(ch1)
    book.toc = ()
    book.add_item(_ebooklib.EpubNcx())
    book.add_item(_ebooklib.EpubNav())
    book.spine = ["nav", ch1]
    epub = out / "sample.epub"
    _ebooklib.write_epub(str(epub), book)

    # --- XLSX (minimal valid XLSX) ---
    xlsx = out / "sample.xlsx"
    with zipfile.ZipFile(xlsx, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        )
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>Name</t></is></c><c r="B1" t="inlineStr"><is><t>Role</t></is></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>Alice</t></is></c><c r="B2" t="inlineStr"><is><t>Engineer</t></is></c></row>'
            '<row r="3"><c r="A3" t="inlineStr"><is><t>Bob</t></is></c><c r="B3" t="inlineStr"><is><t>Designer</t></is></c></row>'
            '</sheetData></worksheet>',
        )

    return {"html": html, "csv": csv, "epub": epub, "xlsx": xlsx, "json": json_path}


# --- Sanity: required real fixtures exist ---------------------------------

@pytest.fixture(scope="module", autouse=True)
def _check_real_fixtures():
    missing = [p for p in (HAIER_DOCX, MERIDIAN_PPTX, MERIDIAN_DOCX) if not p.exists()]
    if missing:
        pytest.skip(f"Real fixtures missing: {missing}")


# --- Tests ------------------------------------------------------------------


class TestCLIBasics:
    def test_help(self):
        proc = run_opp("--help")
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert "OPP" in proc.stdout
        assert "--target-format" in proc.stdout

    def test_help_mentions_every_doc_flag(self):
        proc = run_opp("--help")
        for flag in ("--detect-format", "--output-dir", "--source-lang", "--target-lang",
                     "--resource-dir", "--report", "--batch", "--ocr-engine"):
            assert flag in proc.stdout, f"help missing {flag}"


class TestExtractMarkdown:
    """`opp <file> --target-format md --output-dir <out>` per format."""

    def _assert_md_output(self, proc: subprocess.CompletedProcess, out_dir: Path,
                          expected_stem: str, min_chars: int = 5):
        assert proc.returncode == 0, (
            f"exit={proc.returncode}\nstdout={proc.stdout[:1500]}\nstderr={proc.stderr[:1500]}"
        )
        md_files = list(out_dir.glob(f"{expected_stem}*.md"))
        assert md_files, f"no .md produced in {out_dir} (found: {list(out_dir.iterdir())})"
        # At least one non-empty .md
        assert any(f.stat().st_size > min_chars for f in md_files), \
            f"all .md files under {min_chars} bytes"

    def test_docx_haier(self, tmp_path):
        out = tmp_path / "docx_haier"
        proc = run_opp(
            str(HAIER_DOCX),
            "--target-format", "md",
            "--source-lang", "zh", "--target-lang", "en",
            "--output-dir", str(out),
        )
        self._assert_md_output(proc, out, "爱上海尔_第二章_全球创牌 - E2E测试专用")

    def test_docx_meridian(self, tmp_path):
        out = tmp_path / "docx_meridian"
        proc = run_opp(
            str(MERIDIAN_DOCX),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        self._assert_md_output(proc, out, "Meridian_Robotics_Product_Overview_E2E")

    def test_pptx(self, tmp_path):
        out = tmp_path / "pptx"
        proc = run_opp(
            str(MERIDIAN_PPTX),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        self._assert_md_output(proc, out, "Meridian_Q1_Update_E2E")

    def test_html(self, tmp_path, synthetic_formats):
        out = tmp_path / "html"
        proc = run_opp(
            str(synthetic_formats["html"]),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        self._assert_md_output(proc, out, "sample")

    def test_csv(self, tmp_path, synthetic_formats):
        out = tmp_path / "csv"
        proc = run_opp(
            str(synthetic_formats["csv"]),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        self._assert_md_output(proc, out, "sample")

    def test_epub(self, tmp_path, synthetic_formats):
        out = tmp_path / "epub"
        proc = run_opp(
            str(synthetic_formats["epub"]),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        self._assert_md_output(proc, out, "sample")

    def test_xlsx(self, tmp_path, synthetic_formats):
        out = tmp_path / "xlsx"
        proc = run_opp(
            str(synthetic_formats["xlsx"]),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        self._assert_md_output(proc, out, "sample")

    def test_json(self, tmp_path, synthetic_formats):
        out = tmp_path / "json"
        proc = run_opp(
            str(synthetic_formats["json"]),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        self._assert_md_output(proc, out, "sample")


class TestExtractXLIFF:
    """`opp <file> --target-format xlf --source-lang en --target-lang zh`."""

    def test_docx_xliff_has_trans_units(self, tmp_path):
        out = tmp_path / "xliff"
        proc = run_opp(
            str(HAIER_DOCX),
            "--target-format", "xlf",
            "--source-lang", "zh", "--target-lang", "en",
            "--output-dir", str(out),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[:1500]}"
        xlf_files = list(out.glob("*.xlf"))
        assert xlf_files
        content = xlf_files[0].read_text(encoding="utf-8")
        assert "<xliff" in content
        assert "<trans-unit" in content, "no trans-units in XLIFF"
        assert content.count("<trans-unit") > 0


class TestExtractBoth:
    """`--target-format both` should emit .md and .xlf side by side."""

    def test_both_produces_md_and_xlf(self, tmp_path):
        out = tmp_path / "both"
        proc = run_opp(
            str(MERIDIAN_DOCX),
            "--target-format", "both",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[:1500]}"
        assert list(out.glob("*.md")), "missing .md"
        assert list(out.glob("*.xlf")), "missing .xlf"


class TestOutputArtifacts:
    """Every extraction should also write a manifest.json (and skeleton.zip
    for DOCX/PPTX)."""

    def test_manifest_and_skeleton_for_docx(self, tmp_path):
        out = tmp_path / "artifacts"
        proc = run_opp(
            str(MERIDIAN_DOCX),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[:1500]}"
        manifests = list(out.glob("*_manifest.json"))
        assert manifests, f"no manifest.json in {list(out.iterdir())}"
        # DOCX is skeletonizable
        skeletons = list(out.glob("*.skeleton.zip"))
        assert skeletons, "no .skeleton.zip emitted for DOCX"

    def test_manifest_for_html(self, tmp_path, synthetic_formats):
        out = tmp_path / "artifacts_html"
        proc = run_opp(
            str(synthetic_formats["html"]),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[:1500]}"
        assert list(out.glob("*_manifest.json"))


class TestFlags:
    """Misc documented flags."""

    def test_detect_format_flag(self, tmp_path):
        out = tmp_path / "detect"
        proc = run_opp(
            str(MERIDIAN_DOCX),
            "--detect-format", "-v",
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[:1500]}"
        # Verbose mode logs the detected format on stderr (lowercase value).
        assert "Detected" in proc.stderr and "docx" in proc.stderr.lower(), (
            f"expected 'Detected' + format token in stderr; got: {proc.stderr[-800:]}"
        )

    def test_report_text(self, tmp_path):
        out = tmp_path / "report"
        proc = run_opp(
            str(MERIDIAN_DOCX),
            "--report", "text",
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[:1500]}"

    def test_batch_multiple_files(self, tmp_path):
        out = tmp_path / "batch"
        proc = run_opp(
            str(MERIDIAN_DOCX), str(MERIDIAN_PPTX),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[:1500]}"
        stems = {f.stem for f in out.glob("*.md")}
        assert len(stems) >= 2, f"expected 2 stems, got {stems}"

    def test_xlf_requires_target_lang(self, tmp_path):
        """OPP CLI now REQUIRES --target-lang when --target-format is xlf.

        Previously the default was 'en' (truthy) and the check never fired.
        See TestTargetLangFlag.test_target_lang_is_required_for_xlf.
        """
        proc = run_opp(
            str(MERIDIAN_DOCX),
            "--target-format", "xlf",
            "--source-lang", "zh",
            "--output-dir", str(tmp_path),
        )
        assert proc.returncode != 0
        assert "target-lang is required" in proc.stderr.lower()


# --- Module-level timing/diagnostic -----------------------------------------

def test_smoke_total_runtime_under_15_minutes(synthetic_formats, tmp_path):
    """A backstop: all six per-format extractions complete inside 15 min total.

    On a warm venv this is normally <60s. We re-run only the synthetic
    formats (HTML/CSV/EPUB/XLSX) + the two real DOCX/PPTX to keep the
    backstop test fast.
    """
    deadline = time.time() + 15 * 60
    targets = [
        (HAIER_DOCX, "haier"),
        (MERIDIAN_DOCX, "meridian"),
        (MERIDIAN_PPTX, "pptx"),
        (synthetic_formats["html"], "html"),
        (synthetic_formats["csv"], "csv"),
        (synthetic_formats["epub"], "epub"),
        (synthetic_formats["xlsx"], "xlsx"),
        (synthetic_formats["json"], "json"),
    ]
    for path, tag in targets:
        assert time.time() < deadline, f"deadline exceeded before {tag}"
        out = tmp_path / tag
        proc = run_opp(
            str(path),
            "--target-format", "md",
            "--source-lang", "en", "--target-lang", "zh",
            "--output-dir", str(out),
            timeout=300,
        )
        assert proc.returncode == 0, (
            f"{tag} failed: exit={proc.returncode}\n"
            f"stderr(last 800)={proc.stderr[-800:]}"
        )
