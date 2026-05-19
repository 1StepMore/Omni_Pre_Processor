@echo off
REM OPP Agents Installation Script
REM Installs OPP as OpenCode skill and Hermes plugin

echo Installing OPP Agents...

REM Install OPP with MCP support
echo Installing OPP with MCP support...
pip install -e ".[mcp]"

REM Install as OpenCode skill
echo Installing OPP as OpenCode skill...
if not exist "%USERPROFILE%\.config\opencode\skills\" mkdir "%USERPROFILE%\.config\opencode\skills\"
xcopy /E /I /Y src\opp_agent "%USERPROFILE%\.config\opencode\skills\opp_agent\"

REM Install as Hermes plugin
echo Installing OPP as Hermes plugin...
if not exist "%USERPROFILE%\.hermes\plugins\opp\" mkdir "%USERPROFILE%\.hermes\plugins\opp\"
xcopy /E /I /Y src\opp_hermes\* "%USERPROFILE%\.hermes\plugins\opp\"

echo.
echo Installation complete!
echo.
echo Next steps:
echo 1. Set OPP_MCP_ALLOWED_DIRS environment variable:
echo    set OPP_MCP_ALLOWED_DIRS=C:\path\to\documents;C:\path\to\output
echo.
echo 2. Restart OpenCode or Hermes to load the new integration
echo.
echo For OpenCode: Copy %%USERPROFILE%%\.config\opencode\skills\opp_agent\SKILL.md
echo For Hermes: Add OPP to your hermes.yaml mcp_servers configuration
echo.
pause