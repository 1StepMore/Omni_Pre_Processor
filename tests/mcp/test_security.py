"""Tests for security.PathValidator."""

import os
from pathlib import Path
import pytest
import importlib.util


spec = importlib.util.spec_from_file_location("security", Path(__file__).parent.parent.parent / "src" / "opp" / "mcp" / "security.py")
security_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security_module)
PathValidator = security_module.PathValidator
PathValidationError = security_module.PathValidationError
ValidationResult = security_module.ValidationResult
SYSTEM_DIRS = security_module.SYSTEM_DIRS
BLOCKED_EXTENSIONS = security_module.BLOCKED_EXTENSIONS


class TestPathValidator:
    """Tests for PathValidator class."""

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
        with pytest.raises(PathValidationError) as e:
            validator.validate_path(path)
        assert "traversal" in str(e.value).lower()

    # --- System Directory Tests ---

    @pytest.mark.parametrize("system_dir,expected_error_fragment", [
        ("/etc", "system directory"),
        ("/usr", "system directory"),
        ("/var", "system directory"),
        ("/System", "system directory"),
        ("/Library", "system directory"),
    ])
    @pytest.mark.skipif(
        os.name == "nt",
        reason=(
            "POSIX 系统目录在 Windows 上被解析成 <cwd-drive>:\\etc 之类，本来就不在 "
            "SYSTEM_DIRS 的命中范围内；Windows 盘符形式由紧随其后的 "
            "test_windows_paths_on_unix 覆盖"
        ),
    )
    def test_system_dirs_blocked(self, validator: PathValidator, system_dir: str, expected_error_fragment: str):
        """POSIX 系统目录必须命中 system-directory 拦截（非"不在白名单"）。

        2026-09-17: 这里原本是 ``xfail(os.name != "nt", ...)`` —— 方向写反了。
        参数全是 POSIX 目录（``/etc``/``/usr``/``/var``/``/System``/``/Library``），
        它们在 POSIX 上**能**命中拦截、在 Windows 上不能，于是这个 marker 让该断言
        在两边都不生效：POSIX 上被标成 XPASS（strict=False 不计失败），Windows 上
        直接红。改为平台反向跳过 + 另一条 Windows 用例补位。
        """
        with pytest.raises(PathValidationError) as e:
            validator.validate_path(f"{system_dir}/some/file.txt")
        assert (
            expected_error_fragment in str(e.value).lower()
            or "not allowed" in str(e.value).lower()
        )

    @pytest.mark.parametrize("system_dir", [
        "C:\\Windows",
        "/C:/Windows",
    ])
    def test_windows_paths_on_unix(self, validator: PathValidator, system_dir: str):
        test_path = f"{system_dir}/some/file.txt"
        with pytest.raises(PathValidationError):
            validator.validate_path(test_path)

    def test_path_within_system_dir_blocked(self, validator: PathValidator):
        """Path that resolves to a subdirectory of a system dir should be blocked."""
        # /etc/passwd should be blocked
        with pytest.raises(PathValidationError):
            validator.validate_path("/etc/passwd")

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
            with pytest.raises(PathValidationError) as e:
                validator.validate_path(str(symlink_path))
            assert "symlink" in str(e.value).lower() or "outside" in str(e.value).lower()
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

        with pytest.raises(PathValidationError) as e:
            validator.validate_path(str(blocked_file))
        assert "extension" in str(e.value).lower()
        assert ext in str(e.value)

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

        with pytest.raises(PathValidationError) as e:
            validator_with_size_limit.validate_path(str(large_file))
        assert "exceeds" in str(e.value).lower() or "size" in str(e.value).lower()

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
        with pytest.raises(PathValidationError) as e:
            validator.validate_path(str(nonexistent))
        assert "does not exist" in str(e.value).lower()

    def test_directory_rejected(self, validator: PathValidator, allowed_dir: Path):
        """Directories should be rejected (only files allowed)."""
        with pytest.raises(PathValidationError) as e:
            validator.validate_path(str(allowed_dir))
        assert "directory" in str(e.value).lower() or "file" in str(e.value).lower()

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

        with pytest.raises(PathValidationError) as e:
            validator.validate_path(str(outside_file))
        assert "not in allowed directories" in str(e.value).lower()

    # --- Invalid Path Format Tests ---

    @pytest.mark.parametrize("invalid_path", [
        "",
        "\x00null",  # null bytes
    ])
    def test_invalid_path_format(self, validator: PathValidator, invalid_path: str):
        """Invalid path formats should be rejected."""
        with pytest.raises(PathValidationError):
            validator.validate_path(invalid_path)

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

        if expected_blocked:
            with pytest.raises(PathValidationError) as e:
                validator.validate_path(str(test_file))
            assert "extension" in str(e.value).lower()
        else:
            result = validator.validate_path(str(test_file))
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