@echo off
chcp 65001 >nul 2>&1

REM OPP XLIFF Conversion - Quick Convert to .xlf for translation
REM Usage: xliff.bat "file.docx" [target-lang] [flags]
REM Supports drag-drop of files and folders

if "%~1"=="" (
    echo OPP XLIFF Converter
    echo.
    echo Usage: xliff.bat "file.docx" [target-lang] [flags]
    echo         xliff.bat "folder" [target-lang] [flags]
    echo.
    echo Converts document to XLIFF format for translation.
    echo.
    echo Arguments:
    echo   target-lang          Target language code ^(e.g., zh, ja, fr^) ^(^default: zh^)
    echo.
    echo Flags:
    echo   --output-dir ./output  Output directory
    echo   -v                       Verbose logging
    echo.
    echo Example:
    echo   xliff.bat "document.docx" zh
    echo   xliff.bat "folder" ja --output-dir ./out
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

REM Determine target lang from second arg, default to zh
set TARGET_LANG=zh
if not "%~2"=="" set TARGET_LANG=%~2

REM Build command line: file + any flags after target-lang
set "EXTRA_FLAGS="
:parse_args
shift
if "%~1"=="" goto run_opp
set "EXTRA_FLAGS=%EXTRA_FLAGS% %~1"
goto parse_args

:run_opp
python -m opp --target-format=xlf --target-lang=%TARGET_LANG% "%~1"%EXTRA_FLAGS%

echo.
echo Done! Logs saved to logs\ directory.
pause >nul
