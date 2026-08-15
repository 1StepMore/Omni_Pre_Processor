"""opp validate-xliff — Validate an XLIFF 1.2 file.

Companion CLI to the OPP MCP validate_xliff tool. Accepts either an
inline XLIFF string or a file path. Prints structured validation result
(is_valid, schema_valid, trans_units_valid, errors, warnings).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer

from cli._shared import ExitCode


def validate_xliff(
    xliff_content: Optional[str] = typer.Option(
        None, "--content", "-c",
        help="Inline XLIFF XML. Takes precedence over --file if both are given."
    ),
    file_path: Optional[str] = typer.Option(
        None, "--file", "-f",
        help="Path to .xlf/.xliff file. Used only if --content is not given."
    ),
) -> None:
    """Validate an XLIFF 1.2 file (schema + trans-unit content rules)."""
    if not xliff_content and not file_path:
        typer.echo(
            "Error: provide either --content <xml> or --file <path>",
            err=True,
        )
        raise typer.Exit(code=ExitCode.CLI_USAGE_ERROR)

    try:
        from opp.mcp.tools.validate_xliff import validate_xliff as _impl
        result = asyncio.run(_impl(
            xliff_content=xliff_content,
            file_path=file_path,
        ))
    except Exception as e:  # expected: convert validation failure to CLI exit
        typer.echo(f"Error: validation failed: {e}", err=True)
        raise typer.Exit(code=ExitCode.PIPELINE_ERROR)

    if not result.get("success"):
        typer.echo(json.dumps(result, indent=2), err=True)
        raise typer.Exit(code=ExitCode.CLI_USAGE_ERROR)

    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    raise typer.Exit(code=ExitCode.SUCCESS)
