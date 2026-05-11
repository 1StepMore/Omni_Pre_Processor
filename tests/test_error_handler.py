from datetime import datetime

import pytest

from opp.error_handler import (
    ErrorContext,
    ErrorHandler,
    DetectionError,
    ExtractionError,
    ResourceError,
    ExportError,
)
from opp.utils.exceptions import OPPError


class TestErrorHandler:
    def test_exception_hierarchy_detection_error(self):
        """DetectionError should inherit from OPPError."""
        assert issubclass(DetectionError, OPPError)

    def test_exception_hierarchy_extraction_error(self):
        """ExtractionError should inherit from OPPError."""
        assert issubclass(ExtractionError, OPPError)

    def test_exception_hierarchy_resource_error(self):
        """ResourceError should inherit from OPPError."""
        assert issubclass(ResourceError, OPPError)

    def test_exception_hierarchy_export_error(self):
        """ExportError should inherit from OPPError."""
        assert issubclass(ExportError, OPPError)

    def test_add_error_records_to_errors_list(self):
        """add_error() should append ErrorContext to _errors list."""
        handler = ErrorHandler()
        ctx = ErrorContext(
            file_path="test.txt",
            error_type="TestError",
            timestamp=datetime.now(),
            details="Test details",
        )
        handler.add_error(ctx)
        assert len(handler._errors) == 1
        assert handler._errors[0] == ctx

    def test_add_warning_records_to_warnings_list(self):
        """add_warning() should append ErrorContext to _warnings list."""
        handler = ErrorHandler()
        ctx = ErrorContext(
            file_path="test.txt",
            error_type="TestWarning",
            timestamp=datetime.now(),
            details="Test warning details",
        )
        handler.add_warning(ctx)
        assert len(handler._warnings) == 1
        assert handler._warnings[0] == ctx

    def test_get_stats_returns_error_and_warning_counts(self):
        """get_stats() should return dict with errors and warnings counts."""
        handler = ErrorHandler()
        handler.add_error(
            ErrorContext(
                file_path="a.txt",
                error_type="Err1",
                timestamp=datetime.now(),
                details="",
            )
        )
        handler.add_warning(
            ErrorContext(
                file_path="b.txt",
                error_type="Warn1",
                timestamp=datetime.now(),
                details="",
            )
        )
        handler.add_warning(
            ErrorContext(
                file_path="c.txt",
                error_type="Warn2",
                timestamp=datetime.now(),
                details="",
            )
        )
        stats = handler.get_stats()
        assert stats == {"errors": 1, "warnings": 2}

    def test_has_errors_returns_true_when_errors_exist(self):
        """has_errors() should return True when _errors is not empty."""
        handler = ErrorHandler()
        assert handler.has_errors() is False
        handler.add_error(
            ErrorContext(
                file_path="test.txt",
                error_type="Err",
                timestamp=datetime.now(),
                details="",
            )
        )
        assert handler.has_errors() is True

    def test_has_errors_returns_false_when_no_errors(self):
        """has_errors() should return False when _errors is empty."""
        handler = ErrorHandler()
        assert handler.has_errors() is False

    def test_generate_html_report_contains_doctype(self):
        """HTML report should contain DOCTYPE declaration."""
        handler = ErrorHandler()
        report = handler.generate_html_report()
        assert "<!DOCTYPE html>" in report

    def test_generate_html_report_contains_error_count(self):
        """HTML report should contain error count."""
        handler = ErrorHandler()
        handler.add_error(
            ErrorContext(
                file_path="test.txt",
                error_type="Err",
                timestamp=datetime.now(),
                details="details",
            )
        )
        report = handler.generate_html_report()
        assert 'error-count">1</span>' in report

    def test_generate_html_report_contains_warning_count(self):
        """HTML report should contain warning count."""
        handler = ErrorHandler()
        handler.add_warning(
            ErrorContext(
                file_path="test.txt",
                error_type="Warn",
                timestamp=datetime.now(),
                details="details",
            )
        )
        report = handler.generate_html_report()
        assert 'warning-count">1</span>' in report

    def test_generate_html_report_contains_timestamp(self):
        """HTML report should contain timestamp."""
        handler = ErrorHandler()
        report = handler.generate_html_report()
        # Timestamp format: YYYY-MM-DD HH:MM:SS
        assert any(char.isdigit() for char in report)

    def test_generate_text_report_contains_error_details(self):
        """Text report should contain error type and details."""
        handler = ErrorHandler()
        handler.add_error(
            ErrorContext(
                file_path="test.txt",
                error_type="ExtractionError",
                timestamp=datetime.now(),
                details="Failed to extract content",
            )
        )
        report = handler.generate_text_report()
        assert "ExtractionError" in report
        assert "Failed to extract content" in report
        assert "test.txt" in report

    def test_generate_text_report_contains_no_html_tags(self):
        """Text report should not contain HTML tags."""
        handler = ErrorHandler()
        handler.add_error(
            ErrorContext(
                file_path="test.txt",
                error_type="Err",
                timestamp=datetime.now(),
                details="details",
            )
        )
        report = handler.generate_text_report()
        assert "<" not in report
        assert ">" not in report
        assert "DOCTYPE" not in report

    def test_generate_text_report_contains_timestamp(self):
        """Text report should contain timestamp."""
        handler = ErrorHandler()
        report = handler.generate_text_report()
        # Timestamp format: YYYY-MM-DD HH:MM:SS
        assert any(char.isdigit() for char in report)

    def test_generate_text_report_empty_handler(self):
        """Text report for empty handler should show zero counts."""
        handler = ErrorHandler()
        report = handler.generate_text_report()
        assert "Errors: 0" in report
        assert "Warnings: 0" in report

    def test_generate_html_report_empty_handler(self):
        """HTML report for empty handler should show zero counts."""
        handler = ErrorHandler()
        report = handler.generate_html_report()
        assert 'error-count">0</span>' in report
        assert 'warning-count">0</span>' in report

class TestErrorHandlerEdgeCases:
    """Edge case tests for ErrorHandler report generation and statistics."""

    def test_generate_html_report_with_errors_and_warnings(self):
        """HTML report contains both errors and warnings formatted correctly."""
        handler = ErrorHandler()
        handler.add_error(
            ErrorContext(
                file_path="/path/to/file1.docx",
                error_type="ExtractionError",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                details="Failed to extract text from document",
            )
        )
        handler.add_warning(
            ErrorContext(
                file_path="/path/to/file2.pdf",
                error_type="ExtractionWarning",
                timestamp=datetime(2024, 1, 15, 10, 31, 0),
                details="Image extraction skipped",
            )
        )
        report = handler.generate_html_report(file_count=5)

        assert "<!DOCTYPE html>" in report
        assert 'error-count">1</span>' in report
        assert 'warning-count">1</span>' in report
        assert "ExtractionError" in report
        assert "Failed to extract text from document" in report
        assert "ExtractionWarning" in report
        assert "Image extraction skipped" in report
        assert "file1.docx" in report
        assert "file2.pdf" in report

    def test_generate_text_report_with_warnings_only(self):
        """Text report with only warnings shows correct counts."""
        handler = ErrorHandler()
        handler.add_warning(
            ErrorContext(
                file_path="/path/to/file.docx",
                error_type="FormatWarning",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                details="Non-standard format detected",
            )
        )
        handler.add_warning(
            ErrorContext(
                file_path="/path/to/other.pdf",
                error_type="ResourceWarning",
                timestamp=datetime(2024, 1, 15, 10, 31, 0),
                details="Large image resized",
            )
        )
        report = handler.generate_text_report(file_count=2)

        assert "Errors: 0" in report
        assert "Warnings: 2" in report
        assert "FormatWarning" in report
        assert "ResourceWarning" in report
        assert "<" not in report  # No HTML

    def test_get_stats_with_no_errors_or_warnings(self):
        """Stats returns zeros when no errors or warnings recorded."""
        handler = ErrorHandler()
        stats = handler.get_stats()

        assert stats == {"errors": 0, "warnings": 0}
        assert handler.has_errors() is False

    def test_get_stats_with_multiple_error_types(self):
        """Stats correctly counts multiple different error types."""
        handler = ErrorHandler()
        error_types = [
            ("ExtractionError", "File1"),
            ("DetectionError", "File2"),
            ("ResourceError", "File3"),
            ("ExportError", "File4"),
            ("ExtractionError", "File5"),
        ]
        for err_type, path in error_types:
            handler.add_error(
                ErrorContext(
                    file_path=f"/path/{path}",
                    error_type=err_type,
                    timestamp=datetime.now(),
                    details="Test error",
                )
            )
        stats = handler.get_stats()

        assert stats["errors"] == 5
        assert stats["warnings"] == 0

    def test_get_errors_returns_copy(self):
        """get_errors() returns a copy, not the original list."""
        handler = ErrorHandler()
        ctx = ErrorContext(
            file_path="test.txt",
            error_type="Err",
            timestamp=datetime.now(),
            details="Test",
        )
        handler.add_error(ctx)
        errors = handler.get_errors()
        errors.clear()

        assert len(handler._errors) == 1  # Original unchanged

    def test_get_warnings_returns_copy(self):
        """get_warnings() returns a copy, not the original list."""
        handler = ErrorHandler()
        ctx = ErrorContext(
            file_path="test.txt",
            error_type="Warn",
            timestamp=datetime.now(),
            details="Test",
        )
        handler.add_warning(ctx)
        warnings = handler.get_warnings()
        warnings.clear()

        assert len(handler._warnings) == 1  # Original unchanged

    def test_generate_html_report_custom_template(self):
        """HTML report uses custom template when provided."""
        handler = ErrorHandler()
        handler.add_error(
            ErrorContext(
                file_path="test.txt",
                error_type="Err",
                timestamp=datetime.now(),
                details="Error details",
            )
        )
        custom_template = "<html><body>Custom: {error_count} errors, {warning_count} warnings</body></html>"
        report = handler.generate_html_report(template=custom_template)

        assert "Custom: 1 errors, 0 warnings" in report

    def test_generate_text_report_custom_template(self):
        """Text report uses custom template when provided."""
        handler = ErrorHandler()
        handler.add_warning(
            ErrorContext(
                file_path="test.txt",
                error_type="Warn",
                timestamp=datetime.now(),
                details="Warning details",
            )
        )
        custom_template = "Custom Report\nErrors: {error_count}\nWarnings: {warning_count}"
        report = handler.generate_text_report(template=custom_template)

        assert "Custom Report" in report
        assert "Errors: 0" in report
        assert "Warnings: 1" in report
