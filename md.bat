@echo off
chcp 65001 >nul 2>&1

REM OPP Markdown Conversion - Quick Convert to .md
REM Usage: md.bat "file.docx" [flags]
REM No target-lang needed for Markdown output

if "%~1"=="" (
    echo OPP Markdown Converter
    echo.
    echo Usage: md.bat "file.docx" [flags]
    echo.
    echo Converts document to Markdown format.
    echo.
    echo Flags:
    echo   --source-lang en        Source language ^(default: en^)
    echo   --output-dir ./output    Output directory
    echo   --batch                 Enable batch mode
    echo.
    echo Example:
    echo   md.bat "document.docx"
    echo   md.bat "file.pdf" --output-dir ./output
    echo   md.bat "*.docx" --batch --output-dir ./out
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

REM Run OPP with Markdown target, pass all args after file
python -m opp --target-format=md "%~1" %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9

echo.
echo Done! .md file created.
pause >nul
