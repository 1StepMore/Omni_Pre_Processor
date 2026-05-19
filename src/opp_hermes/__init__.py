"""OPP plugin for Hermes Agent."""

import os
import sys

_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

from opp_tool import OPP_SCHEMA, check_opp_requirements, opp_handler


def register(ctx):
    """Register the OPP tool with Hermes."""
    ctx.register_tool(
        name="opp_extract",
        toolset="opp",
        schema=OPP_SCHEMA,
        handler=opp_handler,
        check_fn=check_opp_requirements,
        requires_env=[],
        is_async=False,
        description="Extract content from documents (DOCX, PPTX, PDF, etc.)",
        emoji="📄",
    )