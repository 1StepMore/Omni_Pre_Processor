from dataclasses import dataclass
from datetime import datetime
from opp.utils.exceptions import OPPError


_DEFAULT_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OPP Error Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        .summary {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .summary div {{ display: inline-block; margin-right: 30px; font-size: 16px; }}
        .summary .label {{ color: #666; }}
        .summary .value {{ font-weight: bold; color: #333; }}
        .error-count {{ color: #dc3545; }}
        .warning-count {{ color: #ffc107; }}
        .error-list {{ margin-top: 20px; }}
        .error-item {{ background: #fff; border-left: 4px solid #dc3545; padding: 12px; margin-bottom: 10px; border-radius: 4px; }}
        .warning-item {{ border-left-color: #ffc107; }}
        .error-item .header {{ font-weight: bold; color: #333; margin-bottom: 5px; }}
        .error-item .meta {{ color: #666; font-size: 12px; margin-bottom: 5px; }}
        .error-item .details {{ color: #555; font-family: monospace; background: #f8f9fa; padding: 8px; border-radius: 4px; }}
        .timestamp {{ color: #888; font-size: 12px; margin-top: 20px; }}
        .no-errors {{ color: #28a745; font-size: 18px; text-align: center; padding: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OPP Error Report</h1>
        <div class="summary">
            <div><span class="label">Files Processed:</span> <span class="value">{file_count}</span></div>
            <div><span class="label">Errors:</span> <span class="value error-count">{error_count}</span></div>
            <div><span class="label">Warnings:</span> <span class="value warning-count">{warning_count}</span></div>
            <div><span class="label">Timestamp:</span> <span class="value">{timestamp}</span></div>
        </div>
        {error_list}
        <div class="timestamp">Report generated: {timestamp}</div>
    </div>
</body>
</html>"""

_DEFAULT_TEXT_TEMPLATE = """OPP Error Report
================

Files Processed: {file_count}
Errors: {error_count}
Warnings: {warning_count}
Timestamp: {timestamp}

Errors and Warnings:
--------------------
{error_list}

Report generated: {timestamp}"""


class DetectionError(OPPError):
    pass


class ExtractionError(OPPError):
    pass


class ResourceError(OPPError):
    pass


class ExportError(OPPError):
    pass


@dataclass
class ErrorContext:
    file_path: str
    error_type: str
    timestamp: datetime
    details: str


class ErrorHandler:
    def __init__(self) -> None:
        self._errors: list[ErrorContext] = []
        self._warnings: list[ErrorContext] = []

    def add_error(self, ctx: ErrorContext) -> None:
        self._errors.append(ctx)

    def add_warning(self, ctx: ErrorContext) -> None:
        self._warnings.append(ctx)

    def get_stats(self) -> dict[str, int]:
        return {"errors": len(self._errors), "warnings": len(self._warnings)}

    def has_errors(self) -> bool:
        return len(self._errors) > 0

    def get_errors(self) -> list[ErrorContext]:
        return self._errors.copy()

    def get_warnings(self) -> list[ErrorContext]:
        return self._warnings.copy()

    def _format_error_items_html(self) -> str:
        """Format error/warning items as HTML list."""
        items = []
        for err in self._errors:
            items.append(
                f'<div class="error-item">'
                f'<div class="header">Error: {err.error_type}</div>'
                f'<div class="meta">File: {err.file_path} | Time: {err.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</div>'
                f'<div class="details">{err.details}</div>'
                f'</div>'
            )
        for warn in self._warnings:
            items.append(
                f'<div class="error-item warning-item">'
                f'<div class="header">Warning: {warn.error_type}</div>'
                f'<div class="meta">File: {warn.file_path} | Time: {warn.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</div>'
                f'<div class="details">{warn.details}</div>'
                f'</div>'
            )
        return "\n".join(items) if items else '<div class="no-errors">No errors or warnings recorded.</div>'

    def _format_error_items_text(self) -> str:
        """Format error/warning items as plain text."""
        items = []
        for err in self._errors:
            items.append(
                f"[ERROR] {err.error_type}\n"
                f"  File: {err.file_path}\n"
                f"  Time: {err.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Details: {err.details}\n"
            )
        for warn in self._warnings:
            items.append(
                f"[WARNING] {warn.error_type}\n"
                f"  File: {warn.file_path}\n"
                f"  Time: {warn.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Details: {warn.details}\n"
            )
        return "\n".join(items) if items else "No errors or warnings recorded."

    def generate_html_report(self, file_count: int = 0, template: str | None = None) -> str:
        """Generate HTML report of errors and warnings.

        Args:
            file_count: Number of files processed.
            template: Optional custom HTML template. If None, uses default template.

        Returns:
            Complete HTML document string with DOCTYPE.
        """
        stats = self.get_stats()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_list_html = self._format_error_items_html()

        html_template = template if template is not None else _DEFAULT_HTML_TEMPLATE

        return html_template.format(
            file_count=file_count,
            error_count=stats["errors"],
            warning_count=stats["warnings"],
            timestamp=timestamp,
            error_list=error_list_html
        )

    def generate_text_report(self, file_count: int = 0, template: str | None = None) -> str:
        """Generate plain text report of errors and warnings.

        Args:
            file_count: Number of files processed.
            template: Optional custom text template. If None, uses default template.

        Returns:
            Plain text report string.
        """
        stats = self.get_stats()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_list_text = self._format_error_items_text()

        text_template = template if template is not None else _DEFAULT_TEXT_TEMPLATE

        return text_template.format(
            file_count=file_count,
            error_count=stats["errors"],
            warning_count=stats["warnings"],
            timestamp=timestamp,
            error_list=error_list_text
        )
