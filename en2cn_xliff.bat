@echo off
chcp 65001 >nul 2>&1

REM OPP XLIFF Converter - English to Chinese (en→zh)
REM Usage: en2cn_xliff.bat "file.docx" [flags]
REM Supports drag-drop of files and folders

if "%~1"=="" (
    echo OPP XLIFF Converter - English to Chinese
    echo.
    echo Usage: en2cn_xliff.bat "file.docx" [flags]
    echo.
    echo Converts English document to XLIFF format for translation to Chinese.
    echo.
    echo Arguments:
    echo   file               Input file ^(DOCX, PDF, HTML, etc.^)
    echo   flags               Optional flags like --output-dir ./output
    echo.
    echo Examples:
    echo   en2cn_xliff.bat "document.docx"
    echo   en2cn_xliff.bat "folder" --output-dir ./output
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

REM Run OPP with English source, Chinese target
python -m opp --target-format=xlf --source-lang=en --target-lang=zh "%~1" %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9

echo.
echo Done! Logs saved to logs\ directory.
pause >nul
