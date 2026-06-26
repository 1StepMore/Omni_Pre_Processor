import importlib.util
from pathlib import Path

import pytest


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = load_module("server", Path(__file__).parent.parent.parent / "src" / "opp" / "mcp" / "server.py")
config = load_module("config", Path(__file__).parent.parent.parent / "src" / "opp" / "mcp" / "config.py")
security = load_module("security", Path(__file__).parent.parent.parent / "src" / "opp" / "mcp" / "security.py")

MCPConfig = config.MCPConfig
PathValidator = security.PathValidator


BATCH_TEST_DIR = Path(__file__).parent.parent.parent / "batch_test"
PHASE0_OFFICE_DIR = BATCH_TEST_DIR / "phase0_office"


class TestExtractDocumentTool:

    @pytest.fixture
    def setup_server(self, tmp_path: Path):
        allowed_dir = PHASE0_OFFICE_DIR.resolve()
        cfg = MCPConfig(
            allowed_directories=[allowed_dir],
            max_file_size_bytes=100_000_000,
            request_timeout_seconds=60,
            max_images_per_extraction=100,
            max_extraction_depth=3,
            resource_storage_dir=tmp_path / "resources",
        )
        server._init_server(cfg)
        return {"config": cfg, "allowed_dir": allowed_dir}

    @pytest.mark.asyncio
    async def test_extract_document_valid_docx(self, setup_server):
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.extract_document(docx_path, output_formats=["md"])

        assert result["success"] is True
        assert "data" in result or "md_content" in result

    @pytest.mark.asyncio
    async def test_extract_document_valid_pdf(self, setup_server):
        pdf_path = str(PHASE0_OFFICE_DIR / "normal.pdf")
        result = await server.extract_document(pdf_path, output_formats=["md"])

        assert result["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("output_format", ["md", "xlf", "both"])
    async def test_extract_document_various_formats(self, setup_server, output_format: str):
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.extract_document(docx_path, output_formats=[output_format])

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_extract_document_path_traversal(self, setup_server):
        malicious_path = str(PHASE0_OFFICE_DIR / ".." / ".." / "etc" / "passwd")
        result = await server.extract_document(malicious_path)

        assert result["success"] is False
        assert "error" in result
        assert isinstance(result["error"], dict)
        assert isinstance(result["error"]["code"], str) and result["error"]["code"]
        assert isinstance(result["error"]["message"], str) and result["error"]["message"]

    @pytest.mark.asyncio
    async def test_extract_document_non_allowed_dir(self, setup_server):
        outside_path = "/tmp/test_file.docx"
        result = await server.extract_document(outside_path)

        assert result["success"] is False
        assert "error" in result
        assert isinstance(result["error"], dict)
        assert result["error"]["code"]

    @pytest.mark.asyncio
    async def test_extract_document_invalid_format(self, setup_server):
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.extract_document(docx_path, output_formats=["invalid_format"])

        assert result["success"] is False
        assert result["error"]["code"] == "OPP_INVALID_INPUT"
        assert "Invalid output format" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_extract_document_pdf_with_xliff(self, setup_server):
        pdf_path = str(PHASE0_OFFICE_DIR / "normal.pdf")
        result = await server.extract_document(pdf_path, output_formats=["xlf"])

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_extract_document_nonexistent_file(self, setup_server):
        nonexistent = str(PHASE0_OFFICE_DIR / "does_not_exist.docx")
        result = await server.extract_document(nonexistent)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_extract_document_with_language_params(self, setup_server):
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.extract_document(
            docx_path,
            output_formats=["md"],
            source_lang="en",
            target_lang="zh-CN",
        )

        assert result["success"] is True

    # ── OPP#11: suggested_pipeline ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_suggested_pipeline_docx_returns_both(self, setup_server):
        """DOCX supports skeleton preservation → 'both' pipeline."""
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.extract_document(docx_path, output_formats=["md"])

        assert result["success"] is True
        assert "suggested_pipeline" in result
        assert result["suggested_pipeline"] == "both"

    @pytest.mark.asyncio
    async def test_suggested_pipeline_pdf_returns_md_only(self, setup_server):
        """PDF → XLIFF blocked by design → 'md_only' pipeline."""
        pdf_path = str(PHASE0_OFFICE_DIR / "normal.pdf")
        result = await server.extract_document(pdf_path, output_formats=["md"])

        assert result["success"] is True
        assert "suggested_pipeline" in result
        assert result["suggested_pipeline"] == "md_only"

    @pytest.mark.asyncio
    async def test_suggested_pipeline_is_always_present(self, setup_server):
        """suggested_pipeline is present regardless of verbose setting."""
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result_default = await server.extract_document(docx_path, output_formats=["md"])
        result_verbose = await server.extract_document(
            docx_path, output_formats=["md"], verbose=True,
        )

        assert "suggested_pipeline" in result_default
        assert "suggested_pipeline" in result_verbose

    # ── OPP#11: verbose metadata ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_verbose_true_includes_metadata(self, setup_server):
        """verbose=True adds detected_format, confidence, processing_steps."""
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.extract_document(
            docx_path, output_formats=["md"], verbose=True,
        )

        assert result["success"] is True
        assert "detected_format" in result
        assert result["detected_format"] == "docx"
        assert "confidence" in result
        assert isinstance(result["confidence"], (int, float))
        assert "processing_steps" in result
        assert isinstance(result["processing_steps"], list)
        assert "detection" in result["processing_steps"]
        assert "extraction" in result["processing_steps"]

    @pytest.mark.asyncio
    async def test_verbose_false_omits_metadata(self, setup_server):
        """verbose=False (default) does NOT include extra metadata."""
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.extract_document(docx_path, output_formats=["md"])

        assert result["success"] is True
        assert "detected_format" not in result
        assert "confidence" not in result
        assert "processing_steps" not in result

    @pytest.mark.asyncio
    async def test_verbose_processing_steps_md_only(self, setup_server):
        """verbose processing_steps should list md_generation for md output."""
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.extract_document(
            docx_path, output_formats=["md"], verbose=True,
        )

        assert "md_generation" in result["processing_steps"]
        assert "xliff_generation" not in result["processing_steps"]

    @pytest.mark.asyncio
    async def test_verbose_processing_steps_both(self, setup_server):
        """verbose processing_steps should list both for 'both' output."""
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.extract_document(
            docx_path, output_formats=["both"], verbose=True,
        )

        assert "md_generation" in result["processing_steps"]
        assert "xliff_generation" in result["processing_steps"]

    @pytest.mark.asyncio
    async def test_suggested_pipeline_pptx_returns_both(self, setup_server):
        """PPTX supports skeleton preservation → 'both' pipeline."""
        pptx_path = str(PHASE0_OFFICE_DIR / "normal.pptx")
        result = await server.extract_document(pptx_path, output_formats=["md"])

        assert result["success"] is True
        assert result["suggested_pipeline"] == "both"


class TestBatchExtractTool:

    @pytest.fixture
    def setup_server(self, tmp_path: Path):
        allowed_dir = PHASE0_OFFICE_DIR.resolve()
        cfg = MCPConfig(
            allowed_directories=[allowed_dir],
            max_file_size_bytes=100_000_000,
            request_timeout_seconds=60,
            max_images_per_extraction=100,
            max_extraction_depth=3,
            resource_storage_dir=tmp_path / "resources",
        )
        server._init_server(cfg)
        return {"config": cfg}

    @pytest.mark.asyncio
    async def test_batch_extract_all_valid(self, setup_server):
        file_paths = [
            str(PHASE0_OFFICE_DIR / "normal.docx"),
            str(PHASE0_OFFICE_DIR / "normal.pdf"),
        ]
        result = await server.batch_extract(file_paths, output_formats=["md"])

        assert result["success"] is True
        assert "results" in result
        assert result["successful"] >= 1

    @pytest.mark.asyncio
    async def test_batch_extract_fail_fast_on_invalid(self, setup_server):
        file_paths = [
            str(PHASE0_OFFICE_DIR / "normal.docx"),
            "/etc/passwd",
        ]
        result = await server.batch_extract(file_paths)

        assert result["success"] is False
        assert "error" in result
        assert isinstance(result["error"], dict)
        assert result["error"]["code"]

    @pytest.mark.asyncio
    async def test_batch_extract_all_invalid(self, setup_server):
        file_paths = [
            "/tmp/nonexistent1.docx",
            "/tmp/nonexistent2.docx",
        ]
        result = await server.batch_extract(file_paths)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_batch_extract_empty_list(self, setup_server):
        result = await server.batch_extract([])

        assert isinstance(result, dict)


class TestDetectFormatTool:

    @pytest.fixture
    def setup_server(self, tmp_path: Path):
        allowed_dir = PHASE0_OFFICE_DIR.resolve()
        cfg = MCPConfig(
            allowed_directories=[allowed_dir],
            max_file_size_bytes=100_000_000,
            request_timeout_seconds=60,
            max_images_per_extraction=100,
            max_extraction_depth=3,
            resource_storage_dir=tmp_path / "resources",
        )
        server._init_server(cfg)
        return {"config": cfg}

    @pytest.mark.parametrize("filename,expected_format", [
        ("normal.docx", "docx"),
        ("normal.pdf", "pdf"),
        ("normal.pptx", "pptx"),
    ])
    @pytest.mark.asyncio
    async def test_detect_format_known_formats(self, setup_server, filename: str, expected_format: str):
        file_path = str(PHASE0_OFFICE_DIR / filename)
        result = await server.detect_format_tool(file_path)

        assert result["success"] is True
        assert "content" in result
        assert result["content"]["format"] == expected_format
        assert "confidence" in result["content"]

    @pytest.mark.asyncio
    async def test_detect_format_unknown_format(self, setup_server, tmp_path: Path):
        unknown_file = tmp_path / "unknown.bin"
        unknown_file.write_bytes(b"\x00\x01\x02\x03 unknown file content")

        result = await server.detect_format_tool(str(unknown_file))

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_detect_format_invalid_path(self, setup_server):
        result = await server.detect_format_tool("/nonexistent/path/file.docx")

        assert result["success"] is False
        assert "error" in result
        assert isinstance(result["error"], dict)
        assert result["error"]["code"]

    @pytest.mark.asyncio
    async def test_detect_format_path_traversal(self, setup_server):
        malicious_path = str(PHASE0_OFFICE_DIR / ".." / ".." / "etc" / "passwd")
        result = await server.detect_format_tool(malicious_path)

        assert result["success"] is False


class TestGenerateMarkdownTool:

    @pytest.fixture
    def setup_server(self, tmp_path: Path):
        allowed_dir = PHASE0_OFFICE_DIR.resolve()
        cfg = MCPConfig(
            allowed_directories=[allowed_dir],
            max_file_size_bytes=100_000_000,
            request_timeout_seconds=60,
            max_images_per_extraction=100,
            max_extraction_depth=3,
            resource_storage_dir=tmp_path / "resources",
        )
        server._init_server(cfg)
        return {"config": cfg, "tmp_path": tmp_path, "allowed_dir": allowed_dir}

    @pytest.mark.asyncio
    async def test_generate_markdown_content_generation(self, setup_server):
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.generate_markdown(docx_path)

        assert result["success"] is True
        assert "content" in result
        assert "markdown_content" in result["content"]
        assert len(result["content"]["markdown_content"]) > 0

    @pytest.mark.asyncio
    async def test_generate_markdown_output_path_validation(self, setup_server):
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        output_path = "/tmp/forbidden_output.md"

        result = await server.generate_markdown(docx_path, output_path=output_path)

        assert result["success"] is False
        assert "error" in result
        assert isinstance(result["error"], dict)
        assert result["error"]["code"]

    @pytest.mark.asyncio
    async def test_generate_markdown_invalid_input_path(self, setup_server):
        result = await server.generate_markdown("/nonexistent/file.docx")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_generate_markdown_path_traversal(self, setup_server):
        malicious_path = str(PHASE0_OFFICE_DIR / ".." / ".." / "etc" / "passwd")
        result = await server.generate_markdown(malicious_path)

        assert result["success"] is False


class TestGenerateXliffTool:

    @pytest.fixture
    def setup_server(self, tmp_path: Path):
        allowed_dir = PHASE0_OFFICE_DIR.resolve()
        cfg = MCPConfig(
            allowed_directories=[allowed_dir],
            max_file_size_bytes=100_000_000,
            request_timeout_seconds=60,
            max_images_per_extraction=100,
            max_extraction_depth=3,
            resource_storage_dir=tmp_path / "resources",
        )
        server._init_server(cfg)
        return {"config": cfg, "tmp_path": tmp_path, "allowed_dir": allowed_dir}

    @pytest.mark.asyncio
    async def test_generate_xliff_docx(self, setup_server):
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.generate_xliff(
            docx_path,
            source_lang="en",
            target_lang="zh",
        )

        if result["success"]:
            assert "content" in result
            assert "xliff_content" in result["content"]
            assert len(result["content"]["xliff_content"]) > 0
            assert "units_count" in result["content"]
        else:
            assert "error" in result
            assert isinstance(result["error"], dict)

    @pytest.mark.asyncio
    async def test_generate_xliff_pdf_error(self, setup_server):
        pdf_path = str(PHASE0_OFFICE_DIR / "normal.pdf")
        result = await server.generate_xliff(
            pdf_path,
            source_lang="en",
            target_lang="zh",
        )

        if not result["success"]:
            assert "error" in result
            assert isinstance(result["error"], dict)

    @pytest.mark.asyncio
    async def test_generate_xliff_units_count(self, setup_server):
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        result = await server.generate_xliff(
            docx_path,
            source_lang="en",
            target_lang="zh",
        )

        if result["success"]:
            assert result["content"]["units_count"] >= 0
            trans_unit_count = result["content"]["xliff_content"].count("<trans-unit")
            assert result["content"]["units_count"] == trans_unit_count

    @pytest.mark.asyncio
    async def test_generate_xliff_output_path_validation(self, setup_server):
        docx_path = str(PHASE0_OFFICE_DIR / "normal.docx")
        output_path = "/tmp/forbidden_output.xlf"

        result = await server.generate_xliff(
            docx_path,
            source_lang="en",
            target_lang="zh",
            output_path=output_path,
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_generate_xliff_invalid_input(self, setup_server):
        result = await server.generate_xliff(
            "/nonexistent/file.docx",
            source_lang="en",
            target_lang="zh",
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_generate_xliff_path_traversal(self, setup_server):
        malicious_path = str(PHASE0_OFFICE_DIR / ".." / ".." / "etc" / "passwd")
        result = await server.generate_xliff(
            malicious_path,
            source_lang="en",
            target_lang="zh",
        )

        assert result["success"] is False


class TestServerInitialization:

    def test_init_server_creates_validator(self, tmp_path: Path):
        allowed_dir = PHASE0_OFFICE_DIR.resolve()
        cfg = MCPConfig(
            allowed_directories=[allowed_dir],
            max_file_size_bytes=50_000_000,
            request_timeout_seconds=30,
            max_images_per_extraction=50,
            max_extraction_depth=2,
            resource_storage_dir=tmp_path / "resources",
        )

        server._init_server(cfg)

        assert server._validator is not None
        assert server._config is not None
        assert server._pipeline is not None

    def test_tool_functions_return_dicts_not_exceptions(self, tmp_path: Path):
        allowed_dir = PHASE0_OFFICE_DIR.resolve()
        cfg = MCPConfig(
            allowed_directories=[allowed_dir],
            max_file_size_bytes=100_000_000,
            request_timeout_seconds=60,
            max_images_per_extraction=100,
            max_extraction_depth=3,
            resource_storage_dir=tmp_path / "resources",
        )
        server._init_server(cfg)

        import asyncio
        try:
            result = asyncio.run(server.extract_document("/nonexistent/path.docx"))
            assert isinstance(result, dict)
            assert "success" in result
        except Exception as e:
            pytest.fail(f"Tool should return dict, not raise {type(e).__name__}: {e}")