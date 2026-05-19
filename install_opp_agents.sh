#!/bin/bash
# OPP Agents Installation Script
# Installs OPP as OpenCode skill and Hermes plugin

set -e

echo "Installing OPP Agents..."

# Install OPP with MCP support
echo "Installing OPP with MCP support..."
pip install -e ".[mcp]"

# Install as OpenCode skill
echo "Installing OPP as OpenCode skill..."
mkdir -p ~/.config/opencode/skills/
cp -r src/opp_agent ~/.config/opencode/skills/

# Install as Hermes plugin
echo "Installing OPP as Hermes plugin..."
mkdir -p ~/.hermes/plugins/opp
cp -r src/opp_hermes/* ~/.hermes/plugins/opp/

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Set OPP_MCP_ALLOWED_DIRS environment variable:"
echo "   export OPP_MCP_ALLOWED_DIRS=\"/path/to/documents:/path/to/output\""
echo ""
echo "2. Restart OpenCode or Hermes to load the new integration"
echo ""
echo "For OpenCode: Copy ~/.config/opencode/skills/opp_agent/SKILL.md"
echo "For Hermes: Add OPP to your hermes.yaml mcp_servers configuration"