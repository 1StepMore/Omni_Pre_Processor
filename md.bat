@echo off
chcp 65001 >nul 2>&1

REM OPP Markdown Conversion - Quick Convert to .md
REM Usage: md.bat "file.docx" [flags]
REM Supports drag-drop of files and folders

if "%~1"=="" (
    echo OPP Markdown Converter
    echo.
    echo Usage: md.bat "file.docx" [flags]
    echo         md.bat "folder" [flags]
    echo.
    echo Converts document to Markdown format.
    echo.
    echo Flags:
    echo   --output-dir ./output    Output directory
    echo   -v                       Verbose logging
    echo.
    echo Example:
    echo   md.bat "document.docx"
    echo   md.bat "folder" --output-dir ./output
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0.venv312\Scripts\activate.bat" (
    call "%~dp0.venv312\Scripts\activate.bat"
)

REM Change to project directory
cd /d "%~dp0"

REM Run OPP with Markdown target
python -m opp --target-format=md "%~1" %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9

echo.
echo Done! Logs saved to logs\ directory.
pause >nul
