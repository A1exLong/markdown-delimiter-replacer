@echo off
setlocal
cd /d "%~dp0.."
python -m PyInstaller --clean --noconfirm MarkdownDelimiterReplacer.spec
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Run: python -m pip install -r requirements.txt
    exit /b 1
)
echo.
echo [OK] Build result: dist\MarkdownDelimiterReplacer.exe
endlocal
