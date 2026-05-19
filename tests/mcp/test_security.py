"""Tests for security.PathValidator."""

import os
import sys
from pathlib import Path
import pytest
import importlib.util


spec = importlib.util.spec_from_file_location("security", Path(__file__).parent.parent.parent / "src" / "opp" / "mcp" / "security.py")
security_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security_module)
PathValidator = security_module.PathValidator
ValidationResult = security_module.ValidationResult
SYSTEM_DIRS = security_module.SYSTEM_DIRS
BLOCKED_EXTENSIONS = security_module.BLOCKED_EXTENSIONS


class TestPathValidator:
    """Tests for PathValidator class."""

    @pytest.fixture
    def allowed_dir(self, tmp_path: Path) -> Path:
        """Create a temporary allowed directory."""
        return tmp_path

    @pytest.fixture
    def allowed_dir(self, tmp_path: Path) -> Path:
        nested = tmp_path / "allowed"
        nested.mkdir()
        return nested

    @pytest.fixture
    def validator(self, allowed_dir: Path) -> PathValidator:
        return PathValidator([allowed_dir])

    @pytest.fixture
    def validator_with_size_limit(self, allowed_dir: Path) -> PathValidator:
        """Create a PathValidator with 1MB size limit."""
        return PathValidator([allowed_dir], max_file_size_bytes=1_000_000)

    # --- Path Traversal Tests ---

    @pytest.mark.parametrize("path", [
        "../etc/passwd",
        "foo/../bar",
        "foo/../../etc/passwd",
        "./../secret",
        "foo/./../bar",
    ])
    def test_path_traversal_blocked(self, validator: PathValidator, allowed_dir: Path, path: str):
        """Path traversal attempts (.. components) should be blocked."""
        result = validator.validate_path(path)
        assert result.success is False
        assert "traversal" in result.error.lower()

    # --- System Directory Tests ---

    @pytest.mark.parametrize("system_dir,expected_error_fragment", [
        ("/etc", "system directory"),
        ("/usr", "system directory"),
        ("/var", "system directory"),
        ("/System", "system directory"),
        ("/Library", "system directory"),
    ])
    @pytest.mark.skipif(os.name != "nt", reason="Windows-specific paths only on Windows")
    def test_system_dirs_blocked(self, validator: PathValidator, system_dir: str, expected_error_fragment: str):
        test_path = f"{system_dir}/some/file.txt"
        result = validator.validate_path(test_path)
        assert result.success is False
        assert expected_error_fragment in result.error.lower() or "not allowed" in result.error.lower()

    @pytest.mark.parametrize("system_dir", [
        "C:\\Windows",
        "/C:/Windows",
    ])
    def test_windows_paths_on_unix(self, validator: PathValidator, system_dir: str):
        test_path = f"{system_dir}/some/file.txt"
        result = validator.validate_path(test_path)
        assert result.success is False

    def test_path_within_system_dir_blocked(self, validator: PathValidator):
        """Path that resolves to a subdirectory of a system dir should be blocked."""
        # /etc/passwd should be blocked
        result = validator.validate_path("/etc/passwd")
        assert result.success is False

    # --- Symlink Tests ---

    def test_symlink_to_outside_blocked(self, validator: PathValidator, allowed_dir: Path):
        allowed_target = allowed_dir / "target.txt"
        allowed_target.write_text("content")

        outside_root = Path("/tmp") / "test_symlink_outside_opp"
        outside_root.mkdir(exist_ok=True)
        outside_file = outside_root / "outside_target.txt"
        outside_file.write_text("outside content")

        symlink_path = allowed_dir / "link_to_outside.txt"
        try:
            symlink_path.symlink_to(outside_file)
            result = validator.validate_path(str(symlink_path))
            assert result.success is False
            assert "symlink" in result.error.lower() or "outside" in result.error.lower()
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

    def test_symlink_within_allowed_ok(self, validator: PathValidator, allowed_dir: Path):
        """Symlinks within allowed directories should be allowed if target is also allowed."""
        # Create a file and a symlink to it, both within allowed_dir
        target = allowed_dir / "target.txt"
        target.write_text("content")

        link = allowed_dir / "link.txt"
        try:
            link.symlink_to(target)

            result = validator.validate_path(str(link))
            # Both the symlink path and target are within allowed directories
            assert result.success is True
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

    # --- Blocked Extension Tests ---

    @pytest.mark.parametrize("ext", list(BLOCKED_EXTENSIONS))
    def test_blocked_extensions(self, validator: PathValidator, allowed_dir: Path, ext: str):
        """Files with blocked extensions should be rejected."""
        # Create a file with blocked extension
        blocked_file = allowed_dir / f"script{ext}"
        blocked_file.write_text("malicious code")

        result = validator.validate_path(str(blocked_file))
        assert result.success is False
        assert "extension" in result.error.lower()
        assert ext in result.error

    # --- File Size Limit Tests ---

    def test_file_within_size_limit(self, validator_with_size_limit: PathValidator, allowed_dir: Path):
        """Files within size limit should be accepted."""
        small_file = allowed_dir / "small.txt"
        small_file.write_text("x" * 500_000)  # 500KB, under 1MB limit

        result = validator_with_size_limit.validate_path(str(small_file))
        assert result.success is True

    def test_file_exceeds_size_limit(self, validator_with_size_limit: PathValidator, allowed_dir: Path):
        """Files exceeding size limit should be rejected."""
        large_file = allowed_dir / "large.txt"
        large_file.write_text("x" * 1_500_000)  # 1.5MB, over 1MB limit

        result = validator_with_size_limit.validate_path(str(large_file))
        assert result.success is False
        assert "exceeds" in result.error.lower() or "size" in result.error.lower()

    def test_default_size_limit(self, validator: PathValidator, allowed_dir: Path):
        """Files under default 100MB limit should be accepted."""
        # Create a file slightly under 100MB
        medium_file = allowed_dir / "medium.txt"
        medium_file.write_text("x" * 50_000_000)  # 50MB

        result = validator.validate_path(str(medium_file))
        assert result.success is True

    # --- File Existence and Type Tests ---

    def test_nonexistent_file_rejected(self, validator: PathValidator, allowed_dir: Path):
        """Non-existent files should be rejected."""
        nonexistent = allowed_dir / "does_not_exist.txt"
        result = validator.validate_path(str(nonexistent))
        assert result.success is False
        assert "does not exist" in result.error.lower()

    def test_directory_rejected(self, validator: PathValidator, allowed_dir: Path):
        """Directories should be rejected (only files allowed)."""
        result = validator.validate_path(str(allowed_dir))
        assert result.success is False
        assert "directory" in result.error.lower() or "file" in result.error.lower()

    # --- Valid Path Tests ---

    def test_valid_file_path(self, validator: PathValidator, allowed_dir: Path):
        """Valid file paths within allowed directories should be accepted."""
        valid_file = allowed_dir / "valid.txt"
        valid_file.write_text("hello world")

        result = validator.validate_path(str(valid_file))
        assert result.success is True
        assert result.resolved_path is not None
        assert result.resolved_path == valid_file.resolve()

    def test_valid_nested_path(self, validator: PathValidator, allowed_dir: Path):
        """Files in nested directories within allowed_dir should be accepted."""
        nested_dir = allowed_dir / "subdir" / "deeper"
        nested_dir.mkdir(parents=True)
        nested_file = nested_dir / "nested.txt"
        nested_file.write_text("nested content")

        result = validator.validate_path(str(nested_file))
        assert result.success is True

    # --- Path Not in Allowed Directory Tests ---

    def test_path_outside_allowed_dir(self, validator: PathValidator):
        outside_root = Path("/tmp") / "test_outside_opp"
        outside_root.mkdir(exist_ok=True)
        outside_dir = outside_root / "outside"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "outside.txt"
        outside_file.write_text("outside content")

        result = validator.validate_path(str(outside_file))
        assert result.success is False
        assert "not within allowed directories" in result.error.lower()

    # --- Invalid Path Format Tests ---

    @pytest.mark.parametrize("invalid_path", [
        "",
        "\x00null",  # null bytes
    ])
    def test_invalid_path_format(self, validator: PathValidator, invalid_path: str):
        """Invalid path formats should be rejected."""
        result = validator.validate_path(invalid_path)
        assert result.success is False
        assert "invalid" in result.error.lower() or "resolve" in result.error.lower()

    # --- Case Sensitivity Tests ---

    @pytest.mark.parametrize("ext,expected_blocked", [
        (".EXE", True),
        (".Bat", True),
        (".Ps1", True),
        (".TXT", False),
        (".Pdf", False),
    ])
    def test_extension_case_insensitive(self, validator: PathValidator, allowed_dir: Path, ext: str, expected_blocked: bool):
        """Extension checks should be case-insensitive."""
        test_file = allowed_dir / f"script{ext}"
        test_file.write_text("content")

        result = validator.validate_path(str(test_file))
        if expected_blocked:
            assert result.success is False
            assert "extension" in result.error.lower()
        else:
            assert result.success is True

    # --- Multiple Allowed Directories Tests ---

    def test_multiple_allowed_directories(self, tmp_path: Path):
        """Validator should accept paths in any allowed directory."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        validator = PathValidator([dir1, dir2])

        file1 = dir1 / "file1.txt"
        file1.write_text("in dir1")

        file2 = dir2 / "file2.txt"
        file2.write_text("in dir2")

        assert validator.validate_path(str(file1)).success is True
        assert validator.validate_path(str(file2)).success is True

    # --- ValidationResult Dataclass Tests ---

    def test_validation_result_success(self):
        """ValidationResult should store success correctly."""
        result = ValidationResult(success=True, resolved_path=Path("/some/path"))
        assert result.success is True
        assert result.error is None
        assert result.resolved_path == Path("/some/path")

    def test_validation_result_failure(self):
        """ValidationResult should store error message on failure."""
        result = ValidationResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.resolved_path is None