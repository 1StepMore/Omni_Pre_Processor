@echo off
chcp 65001 >nul 2>&1

REM OPP XLIFF Converter - Chinese to English (zh→en)
REM Usage: cn2en_xliff.bat "file.docx" [flags]
REM Supports drag-drop of files and folders

if "%~1"=="" (
    echo OPP XLIFF Converter - Chinese to English
    echo.
    echo Usage: cn2en_xliff.bat "file.docx" [flags]
    echo.
    echo Converts Chinese document to XLIFF format for translation to English.
    echo.
    echo Arguments:
    echo   file               Input file ^(DOCX, PDF, HTML, etc.^)
    echo   flags               Optional flags like --output-dir ./output
    echo.
    echo Examples:
    echo   cn2en_xliff.bat "文档.docx"
    echo   cn2en_xliff.bat "folder" --output-dir ./output
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

REM Run OPP with Chinese source, English target
python -m opp --target-format=xlf --source-lang=zh --target-lang=en "%~1" %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9

echo.
echo Done! Logs saved to logs\ directory.
pause >nul
