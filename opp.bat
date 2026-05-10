@echo off
chcp 65001 >nul 2>&1

REM OPP - Omni Pre-Processor Batch Entry Point
REM Location: bat\opp.bat
REM Usage: Drag a file/folder onto this batch, or run from command line with optional flags

REM If no arguments, show help
if "%~1"=="" (
    echo OPP - Omni Pre-Processor
    echo.
    echo Usage:
    echo   Drag a file onto this batch to convert
    echo   Or: opp.bat "file.docx" [flags]
    echo.
    echo Flags:
    echo   --target-format md      Convert to Markdown ^(default^)
    echo   --target-format xlf     Convert to XLIFF for translation
    echo   --target-format both    Generate both MD and XLF
    echo   --source-lang en        Source language ^(default: en^)
    echo   --target-lang zh        Target language ^(required for xlf/both^)
    echo   --output-dir ./output   Output directory
    echo   --batch                 Enable batch processing mode
    echo.
    echo Example:
    echo   opp.bat "document.docx" --target-format md --output-dir ./output
    echo   opp.bat "file.pdf" --target-format xlf --source-lang en --target-lang zh
    pause
    exit /b 1
)

REM Get the absolute path of the first argument
for %%i in ("%~1") do set "OPP_FILE=%%~fi"

REM Activate virtual environment if it exists
if exist "%~dp0..\.venv\Scripts\activate.bat" (
    call "%~dp0..\.venv\Scripts\activate.bat"
) else if exist "%~dp0..\.venv312\Scripts\activate.bat" (
    call "%~dp0..\.venv312\Scripts\activate.bat"
)

REM Change to project directory (parent of bat/)
cd /d "%~dp0.."

REM Run OPP CLI with all arguments passed through
python -m opp %*

REM Show completion message
echo.
echo Done! Output files are in the specified directory or next to input files.
pause >nul
