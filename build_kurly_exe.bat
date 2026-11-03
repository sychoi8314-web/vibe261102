@echo off
rem Build script for Kurly Review Analyzer (.exe)
rem Output: dist\KurlyReviewAnalyzer.exe
cd /d "%~dp0"

echo [1/2] Installing required packages...
python -m pip install --upgrade pyinstaller PyQt6 requests pandas matplotlib openpyxl || goto :error

echo [2/2] Building executable...
rem --onefile  : bundle everything into a single exe
rem --windowed : no console window (GUI app)
rem --clean    : clear PyInstaller cache before building
rem --exclude-module : PySide6 is also installed and would clash with PyQt6;
rem                    the rest are unused and only make the exe bigger
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name KurlyReviewAnalyzer ^
    --exclude-module PySide6 --exclude-module PyQt5 --exclude-module PySide2 ^
    --exclude-module tkinter --exclude-module scipy --exclude-module IPython ^
    --exclude-module jupyter_client --exclude-module jupyter_core ^
    kurly_review_analyzer\kurly_review_analyzer.py || goto :error

echo.
echo Build complete: %~dp0dist\KurlyReviewAnalyzer.exe
exit /b 0

:error
echo Build failed.
exit /b 1
